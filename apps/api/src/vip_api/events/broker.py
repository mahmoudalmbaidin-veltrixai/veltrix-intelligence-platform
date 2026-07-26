"""Transport-neutral real-time event broker with Redis Streams and Pub/Sub."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import TimeoutError as RedisTimeoutError


@dataclass(frozen=True, slots=True)
class PlatformEvent:
    id: str
    event_type: str
    data: dict[str, object]


class EventBroker(Protocol):
    async def publish(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        event_type: str,
        data: dict[str, object],
    ) -> str: ...

    def subscribe(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        last_event_id: str,
        event_types: frozenset[str],
        heartbeat_seconds: int,
    ) -> AsyncIterator[PlatformEvent | None]: ...


class RedisEventBroker:
    """Durable resumable streams plus Pub/Sub fan-out using tenant-qualified keys."""

    def __init__(self, redis: Redis, prefix: str, max_length: int) -> None:
        self._redis = redis
        self._prefix = prefix
        self._max_length = max_length

    def _stream_key(self, organization_id: UUID, workspace_id: UUID) -> str:
        return f"{self._prefix}:events:{organization_id}:{workspace_id}"

    async def publish(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        event_type: str,
        data: dict[str, object],
    ) -> str:
        key = self._stream_key(organization_id, workspace_id)
        body = json.dumps(data, separators=(",", ":"), default=str)
        event_id = await self._redis.xadd(
            key,
            {"event_type": event_type, "data": body},
            maxlen=self._max_length,
            approximate=True,
        )
        await self._redis.publish(key, json.dumps({"id": event_id, "event": event_type}))
        return str(event_id)

    async def _subscribe(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        last_event_id: str,
        event_types: frozenset[str],
        heartbeat_seconds: int,
    ) -> AsyncIterator[PlatformEvent | None]:
        key = self._stream_key(organization_id, workspace_id)
        cursor = last_event_id or "$"
        if cursor == "$":
            latest = await self._redis.xrevrange(key, count=1)
            cursor = str(latest[0][0]) if latest else "0-0"
        else:
            earliest = await self._redis.xrange(key, count=1)
            if earliest and _event_id(str(earliest[0][0])) > _event_id(cursor):
                yield PlatformEvent(
                    cursor,
                    "stream.replay_gap",
                    {
                        "message": (
                            "Some events are no longer retained; refresh affected resources."
                        ),
                        "requested_cursor": cursor,
                    },
                )
        while True:
            try:
                records = await self._redis.xread(
                    {key: cursor}, count=100, block=heartbeat_seconds * 1000
                )
            except RedisTimeoutError:
                # The shared Redis pool intentionally has a short socket timeout
                # for API operations. A blocking XREAD can legitimately outlive
                # that timeout when a tenant has no new events; treat it as a
                # heartbeat boundary and let redis-py reconnect transparently.
                yield None
                continue
            if not records:
                yield None
                continue
            for _stream, entries in records:
                for event_id, fields in entries:
                    cursor = str(event_id)
                    event_type = str(fields["event_type"])
                    if event_types and event_type not in event_types:
                        continue
                    try:
                        parsed = json.loads(str(fields["data"]))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(parsed, dict):
                        yield PlatformEvent(cursor, event_type, parsed)

    def subscribe(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        last_event_id: str,
        event_types: frozenset[str],
        heartbeat_seconds: int,
    ) -> AsyncIterator[PlatformEvent | None]:
        return self._subscribe(
            organization_id, workspace_id, last_event_id, event_types, heartbeat_seconds
        )


def _event_id(value: str) -> tuple[int, int]:
    left, _, right = value.partition("-")
    return int(left), int(right)
