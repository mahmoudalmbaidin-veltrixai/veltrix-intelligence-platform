"""Tenant-safe generic job commands and queries."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.jobs.models import DeadLetterJob, Job, JobLog, JobPayload
from vip_api.jobs.queue import JobQueue
from vip_api.jobs.registry import JobHandlerRegistry
from vip_api.jobs.schemas import (
    DeadLetterResponse,
    JobCreate,
    JobList,
    JobLogResponse,
    JobResponse,
    ProgressResponse,
)

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "timed_out", "dead_letter"})
logger = logging.getLogger(__name__)
_SENSITIVE_PAYLOAD_KEYS = frozenset(
    {"authorization", "cookie", "credential", "password", "secret", "token"}
)


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in _SENSITIVE_PAYLOAD_KEYS):
                return True
            if _contains_sensitive_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def response(item: Job) -> JobResponse:
    return JobResponse(
        id=item.id,
        type=item.job_type,
        name=item.name,
        status=item.status,
        queue=item.queue_name,
        priority=item.priority,
        attempt=item.current_attempt,
        max_attempts=item.max_attempts,
        progress=ProgressResponse(
            percent=item.progress_percent,
            completed_steps=item.progress_step,
            total_steps=item.progress_total_steps,
            stage=item.progress_stage,
            message=item.progress_message,
            estimated_completion_at=item.estimated_completion_at,
        ),
        created_at=item.created_at,
        updated_at=item.updated_at,
        started_at=item.started_at,
        completed_at=item.completed_at,
        cancellation_requested=item.cancellation_requested,
    )


def _workspace(context: AuthorizationContext) -> UUID:
    if context.workspace_id is None:
        raise ApplicationError(
            code="TENANT_CONTEXT_REQUIRED",
            message="Workspace context is required.",
            status_code=400,
        )
    return context.workspace_id


async def create_job(
    db: AsyncSession,
    context: AuthorizationContext,
    payload: JobCreate,
    settings: Settings,
    queue: JobQueue,
    registry: JobHandlerRegistry,
    *,
    queue_name: str | None = None,
) -> JobResponse:
    workspace_id = _workspace(context)
    registry.get(payload.handler)
    if _contains_sensitive_key(payload.payload):
        raise ApplicationError(
            code="JOB_PAYLOAD_CONTAINS_SECRET",
            message="Job payloads cannot contain credentials or secrets.",
            status_code=422,
        )
    encoded = json.dumps(
        payload.payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if len(encoded) > settings.JOB_MAX_PAYLOAD_BYTES:
        raise ApplicationError(
            code="JOB_PAYLOAD_TOO_LARGE", message="The job payload is too large.", status_code=413
        )
    existing = await db.scalar(
        select(Job).where(
            Job.organization_id == context.organization_id,
            Job.workspace_id == workspace_id,
            Job.job_type == payload.job_type,
            Job.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return response(existing)
    item = Job(
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        job_type=payload.job_type,
        handler=payload.handler,
        queue_name=queue_name or settings.JOB_DEFAULT_QUEUE,
        name=payload.name,
        priority=payload.priority,
        idempotency_key=payload.idempotency_key,
        correlation_id=context.correlation_id,
        created_by_user_id=context.user_id,
        max_attempts=payload.max_attempts,
        timeout_seconds=payload.timeout_seconds,
    )
    db.add(item)
    await db.flush()
    db.add(
        JobPayload(
            job_id=item.id,
            payload=payload.payload,
            size_bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
        )
    )
    await record_audit(
        db,
        "job.queued",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="job",
        resource_id=item.id,
    )
    await db.commit()
    try:
        await queue.enqueue(item.queue_name, item.id, priority=item.priority)
    except Exception as exc:
        logger.warning(
            "Queue enqueue failed; database fallback will claim job",
            extra={
                "job_id": str(item.id),
                "queue_name": item.queue_name,
                "exception_type": type(exc).__name__,
            },
        )
    await db.refresh(item)
    return response(item)


async def get_job(db: AsyncSession, context: AuthorizationContext, job_id: UUID) -> Job:
    item = await db.scalar(
        select(Job).where(
            Job.id == job_id,
            Job.organization_id == context.organization_id,
            Job.workspace_id == _workspace(context),
        )
    )
    if item is None:
        raise ApplicationError(
            code="JOB_NOT_FOUND", message="The job was not found.", status_code=404
        )
    return item


async def list_jobs(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    limit: int,
    before: datetime | None,
    status: str | None,
) -> JobList:
    statement = select(Job).where(
        Job.organization_id == context.organization_id,
        Job.workspace_id == _workspace(context),
    )
    if before is not None:
        statement = statement.where(Job.created_at < before)
    if status is not None:
        statement = statement.where(Job.status == status)
    items = list(
        (await db.scalars(statement.order_by(Job.created_at.desc()).limit(limit + 1))).all()
    )
    next_cursor = items[limit - 1].created_at if len(items) > limit else None
    return JobList(items=[response(item) for item in items[:limit]], next_cursor=next_cursor)


async def cancel_job(db: AsyncSession, context: AuthorizationContext, job_id: UUID) -> JobResponse:
    item = await get_job(db, context, job_id)
    if item.status in TERMINAL_STATES:
        return response(item)
    item.cancellation_requested = True
    item.cancelled_by_user_id = context.user_id
    if item.status in {"queued", "pending", "retrying", "waiting"}:
        item.status = "cancelled"
        item.cancelled_at = datetime.now(UTC)
        item.completed_at = item.cancelled_at
    item.row_version += 1
    await record_audit(
        db,
        "job.cancel",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="job",
        resource_id=item.id,
    )
    await db.commit()
    await db.refresh(item)
    return response(item)


async def retry_job(
    db: AsyncSession, context: AuthorizationContext, job_id: UUID, queue: JobQueue
) -> JobResponse:
    item = await get_job(db, context, job_id)
    if item.status not in {"failed", "timed_out", "dead_letter", "cancelled"}:
        raise ApplicationError(
            code="JOB_NOT_RETRYABLE", message="The job cannot be retried.", status_code=409
        )
    dead = await db.scalar(select(DeadLetterJob).where(DeadLetterJob.job_id == item.id))
    if dead is not None:
        dead.status = "retried"
        dead.retried_at = datetime.now(UTC)
    item.status = "queued"
    item.cancellation_requested = False
    item.cancelled_at = None
    item.completed_at = None
    item.available_at = datetime.now(UTC)
    item.row_version += 1
    await record_audit(
        db,
        "job.retry",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="job",
        resource_id=item.id,
    )
    await db.commit()
    try:
        await queue.enqueue(item.queue_name, item.id, priority=item.priority)
    except Exception as exc:
        logger.warning(
            "Queue enqueue failed; database fallback will claim retried job",
            extra={
                "job_id": str(item.id),
                "queue_name": item.queue_name,
                "exception_type": type(exc).__name__,
            },
        )
    await db.refresh(item)
    return response(item)


async def list_logs(
    db: AsyncSession, context: AuthorizationContext, job_id: UUID, limit: int
) -> list[JobLogResponse]:
    item = await get_job(db, context, job_id)
    logs = (
        await db.scalars(
            select(JobLog).where(JobLog.job_id == item.id).order_by(JobLog.sequence).limit(limit)
        )
    ).all()
    return [
        JobLogResponse(
            sequence=log.sequence, level=log.level, message=log.message, created_at=log.created_at
        )
        for log in logs
    ]


async def list_dead_letters(
    db: AsyncSession, context: AuthorizationContext, limit: int
) -> list[DeadLetterResponse]:
    items = (
        await db.scalars(
            select(DeadLetterJob)
            .where(
                DeadLetterJob.organization_id == context.organization_id,
                DeadLetterJob.workspace_id == _workspace(context),
            )
            .order_by(DeadLetterJob.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [DeadLetterResponse.model_validate(item, from_attributes=True) for item in items]


async def discard_dead_letter(
    db: AsyncSession, context: AuthorizationContext, dead_letter_id: UUID
) -> DeadLetterResponse:
    item = await db.scalar(
        select(DeadLetterJob).where(
            DeadLetterJob.id == dead_letter_id,
            DeadLetterJob.organization_id == context.organization_id,
            DeadLetterJob.workspace_id == _workspace(context),
        )
    )
    if item is None:
        raise ApplicationError(
            code="DEAD_LETTER_NOT_FOUND",
            message="The dead-letter job was not found.",
            status_code=404,
        )
    if item.status == "active":
        item.status = "discarded"
        item.discarded_at = datetime.now(UTC)
        await record_audit(
            db,
            "job.dead_letter.discard",
            actor_user_id=context.user_id,
            organization_id=context.organization_id,
            workspace_id=_workspace(context),
            resource_type="dead_letter_job",
            resource_id=item.id,
        )
        await db.commit()
    return DeadLetterResponse.model_validate(item, from_attributes=True)


async def job_counts(db: AsyncSession, context: AuthorizationContext) -> dict[str, int]:
    rows = (
        await db.execute(
            select(Job.status, func.count())
            .where(
                Job.organization_id == context.organization_id,
                Job.workspace_id == _workspace(context),
            )
            .group_by(Job.status)
        )
    ).all()
    return {str(status): int(count) for status, count in rows}
