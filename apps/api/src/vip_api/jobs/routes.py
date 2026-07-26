"""Governed generic job APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import require_csrf
from vip_api.core.config import Settings
from vip_api.database.session import get_db_session
from vip_api.files.models import FileDownloadToken, FileUpload
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_permission
from vip_api.jobs.models import Job, WorkerHeartbeat
from vip_api.jobs.queue import RedisJobQueue
from vip_api.jobs.schemas import DeadLetterResponse, JobList, JobLogResponse, JobResponse
from vip_api.jobs.services import (
    cancel_job,
    discard_dead_letter,
    get_job,
    job_counts,
    list_dead_letters,
    list_jobs,
    list_logs,
    response,
    retry_job,
)
from vip_api.redis.client import RedisClient

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _queue(request: Request) -> RedisJobQueue:
    settings: Settings = request.app.state.settings
    client: RedisClient = request.app.state.redis
    return RedisJobQueue(client.client, settings.JOB_QUEUE_PREFIX)


@router.get("", response_model=JobList)
async def index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: datetime | None = None,
    status: str | None = None,
) -> JobList:
    return await list_jobs(db, context, limit=limit, before=before, status=status)


@router.get("/metrics")
async def metrics(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.read"))],
) -> dict[str, int]:
    return await job_counts(db, context)


@router.get("/platform-metrics")
async def platform_metrics(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.manage"))],
) -> dict[str, object]:
    if context.workspace_id is None:
        from vip_api.core.errors import ApplicationError

        raise ApplicationError(
            code="TENANT_CONTEXT_REQUIRED",
            message="Workspace context is required.",
            status_code=400,
        )
    settings: Settings = request.app.state.settings
    queue = _queue(request)
    queue_rows = [await queue.metrics(name) for name in settings.JOB_WORKER_QUEUES]
    workers = (
        await db.scalars(select(WorkerHeartbeat).where(WorkerHeartbeat.status == "running"))
    ).all()
    upload_count = int(
        await db.scalar(
            select(func.count())
            .select_from(FileUpload)
            .where(
                FileUpload.organization_id == context.organization_id,
                FileUpload.workspace_id == context.workspace_id,
            )
        )
        or 0
    )
    download_count = int(
        await db.scalar(
            select(func.count())
            .select_from(FileDownloadToken)
            .where(
                FileDownloadToken.organization_id == context.organization_id,
                FileDownloadToken.workspace_id == context.workspace_id,
                FileDownloadToken.used_at.is_not(None),
            )
        )
        or 0
    )
    average_duration = await db.scalar(
        select(func.avg(func.extract("epoch", Job.completed_at - Job.started_at) * 1000)).where(
            Job.organization_id == context.organization_id,
            Job.workspace_id == context.workspace_id,
            Job.completed_at.is_not(None),
            Job.started_at.is_not(None),
        )
    )
    redis_client: RedisClient = request.app.state.redis
    event_key = (
        f"{settings.JOB_QUEUE_PREFIX}:events:{context.organization_id}:{context.workspace_id}"
    )
    event_count = int(await redis_client.client.xlen(event_key))
    return {
        "queues": [
            {"name": row.queue, "ready": row.ready, "delayed": row.delayed} for row in queue_rows
        ],
        "worker_count": len(workers),
        "active_jobs": sum(row.active_jobs for row in workers),
        "worker_concurrency": sum(row.concurrency for row in workers),
        "average_processing_duration_ms": float(average_duration or 0),
        "upload_count": upload_count,
        "download_count": download_count,
        "retained_event_count": event_count,
    }


@router.get("/workers")
async def workers(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _context: Annotated[AuthorizationContext, Depends(require_permission("job.manage"))],
) -> list[dict[str, object]]:
    rows = (
        await db.scalars(
            select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()).limit(100)
        )
    ).all()
    return [
        {
            "worker_id": row.worker_id,
            "queues": row.queue_name.split(","),
            "status": row.status,
            "concurrency": row.concurrency,
            "active_jobs": row.active_jobs,
            "last_seen_at": row.last_seen_at,
        }
        for row in rows
    ]


@router.get("/dead-letters", response_model=list[DeadLetterResponse])
async def dead_letters(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.dead_letter"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[DeadLetterResponse]:
    return await list_dead_letters(db, context, limit)


@router.post(
    "/dead-letters/{dead_letter_id}/discard",
    response_model=DeadLetterResponse,
    dependencies=[Depends(require_csrf)],
)
async def discard(
    dead_letter_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.dead_letter"))],
) -> DeadLetterResponse:
    return await discard_dead_letter(db, context, dead_letter_id)


@router.get("/{job_id}", response_model=JobResponse)
async def show(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.read"))],
) -> JobResponse:
    return response(await get_job(db, context, job_id))


@router.get("/{job_id}/progress", response_model=JobResponse)
async def progress(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.read"))],
) -> JobResponse:
    return response(await get_job(db, context, job_id))


@router.get("/{job_id}/logs", response_model=list[JobLogResponse])
async def logs(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.read"))],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[JobLogResponse]:
    return await list_logs(db, context, job_id, limit)


@router.post("/{job_id}/cancel", response_model=JobResponse, dependencies=[Depends(require_csrf)])
async def cancel(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.cancel"))],
) -> JobResponse:
    return await cancel_job(db, context, job_id)


@router.post("/{job_id}/retry", response_model=JobResponse, dependencies=[Depends(require_csrf)])
async def retry(
    job_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("job.retry"))],
) -> JobResponse:
    return await retry_job(db, context, job_id, _queue(request))
