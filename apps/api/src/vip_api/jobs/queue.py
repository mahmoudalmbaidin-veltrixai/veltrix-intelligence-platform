"""Replaceable priority/delay queue abstraction backed initially by Redis."""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import ceil
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class QueueMetrics:
    queue: str
    ready: int
    delayed: int


class JobQueue(Protocol):
    async def enqueue(
        self, queue: str, job_id: UUID, *, priority: int = 0, delay_seconds: float = 0
    ) -> None: ...

    async def dequeue(self, queue: str) -> UUID | None: ...
    async def metrics(self, queue: str) -> QueueMetrics: ...


class RedisJobQueue:
    """Sorted-set queue; the database remains the authoritative job state."""

    _POP_SCRIPT = """
local item = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
if #item == 0 then return nil end
if tonumber(item[2]) > tonumber(ARGV[1]) then return nil end
if redis.call('ZREM', KEYS[1], item[1]) == 1 then return item[1] end
return nil
"""

    def __init__(self, redis: Redis, prefix: str) -> None:
        self._redis = redis
        self._prefix = prefix

    def _key(self, queue: str) -> str:
        return f"{self._prefix}:queue:{queue}"

    async def enqueue(
        self, queue: str, job_id: UUID, *, priority: int = 0, delay_seconds: float = 0
    ) -> None:
        target = time.time() + max(0, delay_seconds)
        available_second = ceil(target) if delay_seconds > 0 else int(target)
        normalized_priority = max(-100, min(priority, 100))
        score = (available_second * 1000) + (100 - normalized_priority)
        await self._redis.zadd(self._key(queue), {str(job_id): score})

    async def dequeue(self, queue: str) -> UUID | None:
        now_score = (int(time.time()) * 1000) + 200
        value = await self._redis.eval(self._POP_SCRIPT, 1, self._key(queue), str(now_score))  # type: ignore[misc]
        return UUID(str(value)) if value else None

    async def metrics(self, queue: str) -> QueueMetrics:
        key = self._key(queue)
        now_score = (int(time.time()) * 1000) + 200
        ready = int(await self._redis.zcount(key, "-inf", now_score))
        total = int(await self._redis.zcard(key))
        return QueueMetrics(queue, ready, total - ready)
