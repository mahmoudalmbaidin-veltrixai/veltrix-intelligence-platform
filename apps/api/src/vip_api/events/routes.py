"""Authenticated, tenant-qualified resumable Server-Sent Events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.events.broker import RedisEventBroker
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_permission
from vip_api.redis.client import RedisClient

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream", response_class=StreamingResponse)
async def stream_events(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("events.subscribe"))],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    cursor: Annotated[str | None, Query(max_length=80)] = None,
    types: Annotated[list[str] | None, Query()] = None,
) -> StreamingResponse:
    if context.workspace_id is None:
        raise ApplicationError(
            code="TENANT_CONTEXT_REQUIRED",
            message="Workspace context is required.",
            status_code=400,
        )
    workspace_id = context.workspace_id
    resume = last_event_id or cursor or "$"
    if resume != "$" and not _valid_event_id(resume):
        raise ApplicationError(
            code="INVALID_EVENT_CURSOR", message="The event cursor is invalid.", status_code=400
        )
    settings: Settings = request.app.state.settings
    redis_client: RedisClient = request.app.state.redis
    broker = RedisEventBroker(
        redis_client.client, settings.JOB_QUEUE_PREFIX, settings.JOB_EVENT_STREAM_MAXLEN
    )
    rate_key = (
        f"{settings.JOB_QUEUE_PREFIX}:rate:events:"
        f"{context.organization_id}:{workspace_id}:{context.user_id}"
    )
    subscription_count = int(await redis_client.client.incr(rate_key))
    if subscription_count == 1:
        await redis_client.client.expire(rate_key, 60)
    if subscription_count > settings.EVENTS_SUBSCRIPTION_RATE_LIMIT_PER_MINUTE:
        raise ApplicationError(
            code="EVENT_SUBSCRIPTION_RATE_LIMITED",
            message="Too many event subscriptions. Please try again later.",
            status_code=429,
        )
    allowed_types = frozenset(types or ())
    await record_audit(
        db,
        "event.subscription",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="event_stream",
    )
    await db.commit()

    async def generate() -> AsyncIterator[str]:
        yield "retry: 3000\n\n"
        async for event in broker.subscribe(
            context.organization_id,
            workspace_id,
            resume,
            allowed_types,
            settings.JOB_EVENT_HEARTBEAT_SECONDS,
        ):
            if await request.is_disconnected():
                return
            if event is None:
                yield ": keepalive\n\n"
                continue
            body = json.dumps(event.data, separators=(",", ":"), default=str)
            yield f"id: {event.id}\nevent: {event.event_type}\ndata: {body}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _valid_event_id(value: str) -> bool:
    left, separator, right = value.partition("-")
    return bool(separator and left.isdigit() and right.isdigit() and len(value) <= 80)
