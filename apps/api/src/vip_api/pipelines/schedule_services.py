"""Pipeline run-schedule CRUD (create/list/update/pause/resume/delete + history).

Authorization is resource-level: reads require ``viewer`` and mutations require
``operator`` on the target pipeline (the same level that may run it). Every
mutation emits a governance audit event. Enqueueing runs is handled by
``pipelines.scheduler``; this module only manages schedule definitions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.errors import ApplicationError
from vip_api.dashboard_delivery.scheduling import next_cron, next_interval
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.pipelines.models import PipelineSchedule, PipelineScheduleRun
from vip_api.pipelines.schemas import (
    PipelineScheduleCreate,
    PipelineScheduleResponse,
    PipelineScheduleRunResponse,
    PipelineScheduleUpdate,
)
from vip_api.pipelines.services import _scope, require_pipeline_access


def _invalid(message: str) -> ApplicationError:
    return ApplicationError(code="PIPELINE_SCHEDULE_INVALID", message=message, status_code=422)


def _initial_next_run(
    schedule_type: str,
    schedule_expression: str | None,
    timezone: str,
    run_at: datetime | None,
    *,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(UTC)
    if schedule_type == "one_time":
        if run_at is None:
            raise _invalid("A one-time schedule requires run_at.")
        moment = run_at.astimezone(UTC)
        if moment <= current:
            raise _invalid("run_at must be in the future.")
        return moment
    if schedule_type == "cron":
        if not schedule_expression:
            raise _invalid("A cron schedule requires schedule_expression.")
        try:
            return next_cron(schedule_expression, timezone, after=current)
        except ValueError as error:
            raise _invalid(f"Invalid cron expression: {error}") from error
    return next_interval(schedule_type, timezone, anchor=current, after=current)


def _serialize(schedule: PipelineSchedule) -> PipelineScheduleResponse:
    return PipelineScheduleResponse.model_validate(schedule)


async def _get(
    db: AsyncSession, context: AuthorizationContext, schedule_id: UUID, *, lock: bool = False
) -> PipelineSchedule:
    org, ws = _scope(context)
    query = select(PipelineSchedule).where(
        PipelineSchedule.id == schedule_id,
        PipelineSchedule.organization_id == org,
        PipelineSchedule.workspace_id == ws,
    )
    if lock:
        query = query.with_for_update()
    schedule = await db.scalar(query)
    if schedule is None:
        raise ApplicationError(
            code="PIPELINE_SCHEDULE_NOT_FOUND",
            message="The requested schedule was not found.",
            status_code=404,
        )
    return schedule


async def create_schedule(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    payload: PipelineScheduleCreate,
) -> PipelineScheduleResponse:
    pipeline = await require_pipeline_access(db, context, pipeline_id, "operator")
    if payload.enabled and pipeline.published_version_id is None:
        raise ApplicationError(
            code="PIPELINE_NOT_PUBLISHED",
            message="Publish the pipeline before enabling a schedule.",
            status_code=422,
        )
    org, ws = _scope(context)
    next_run = (
        _initial_next_run(
            payload.schedule_type, payload.schedule_expression, payload.timezone, payload.run_at
        )
        if payload.enabled
        else None
    )
    schedule = PipelineSchedule(
        organization_id=org,
        workspace_id=ws,
        pipeline_id=pipeline.id,
        pipeline_version_id=payload.pipeline_version_id,
        name=payload.name,
        schedule_type=payload.schedule_type,
        schedule_expression=payload.schedule_expression,
        timezone=payload.timezone,
        enabled=payload.enabled,
        status="scheduled" if payload.enabled else "paused",
        created_by_user_id=context.user_id,
        next_run_at=next_run,
    )
    db.add(schedule)
    await db.flush()
    await record_audit(
        db,
        "pipeline.schedule.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="pipeline",
        resource_id=pipeline.id,
        metadata={"schedule_id": str(schedule.id), "schedule_type": payload.schedule_type},
    )
    await db.commit()
    await db.refresh(schedule)
    return _serialize(schedule)


async def list_schedules(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID
) -> list[PipelineScheduleResponse]:
    await require_pipeline_access(db, context, pipeline_id, "viewer")
    org, ws = _scope(context)
    rows = (
        await db.scalars(
            select(PipelineSchedule)
            .where(
                PipelineSchedule.organization_id == org,
                PipelineSchedule.workspace_id == ws,
                PipelineSchedule.pipeline_id == pipeline_id,
            )
            .order_by(PipelineSchedule.created_at.desc())
            .limit(100)
        )
    ).all()
    return [_serialize(row) for row in rows]


async def update_schedule(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    schedule_id: UUID,
    payload: PipelineScheduleUpdate,
) -> PipelineScheduleResponse:
    pipeline = await require_pipeline_access(db, context, pipeline_id, "operator")
    schedule = await _get(db, context, schedule_id, lock=True)
    if schedule.pipeline_id != pipeline.id:
        raise ApplicationError(
            code="PIPELINE_SCHEDULE_NOT_FOUND",
            message="The requested schedule was not found.",
            status_code=404,
        )
    if schedule.row_version != payload.expected_version:
        raise ApplicationError(
            code="PIPELINE_SCHEDULE_VERSION_CONFLICT",
            message="The schedule was changed by another request.",
            status_code=409,
        )
    was_enabled = schedule.enabled
    for field in ("name", "schedule_type", "schedule_expression", "timezone"):
        value = getattr(payload, field)
        if value is not None:
            setattr(schedule, field, value)
    if payload.pipeline_version_id is not None:
        schedule.pipeline_version_id = payload.pipeline_version_id
    if payload.enabled is not None:
        schedule.enabled = payload.enabled
    if schedule.enabled and pipeline.published_version_id is None:
        raise ApplicationError(
            code="PIPELINE_NOT_PUBLISHED",
            message="Publish the pipeline before enabling a schedule.",
            status_code=422,
        )
    if schedule.enabled:
        schedule.status = "scheduled"
        schedule.next_run_at = _initial_next_run(
            schedule.schedule_type,
            schedule.schedule_expression,
            schedule.timezone,
            payload.run_at,
        )
    else:
        schedule.status = "paused"
        schedule.next_run_at = None
    schedule.row_version += 1
    org, ws = _scope(context)
    if payload.enabled is not None and payload.enabled != was_enabled:
        event = "pipeline.schedule.resumed" if payload.enabled else "pipeline.schedule.paused"
    else:
        event = "pipeline.schedule.updated"
    await record_audit(
        db,
        event,
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="pipeline",
        resource_id=pipeline.id,
        metadata={"schedule_id": str(schedule.id)},
    )
    await db.commit()
    await db.refresh(schedule)
    return _serialize(schedule)


async def delete_schedule(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    schedule_id: UUID,
    expected_version: int,
) -> None:
    pipeline = await require_pipeline_access(db, context, pipeline_id, "operator")
    schedule = await _get(db, context, schedule_id, lock=True)
    if schedule.pipeline_id != pipeline.id:
        raise ApplicationError(
            code="PIPELINE_SCHEDULE_NOT_FOUND",
            message="The requested schedule was not found.",
            status_code=404,
        )
    if schedule.row_version != expected_version:
        raise ApplicationError(
            code="PIPELINE_SCHEDULE_VERSION_CONFLICT",
            message="The schedule was changed by another request.",
            status_code=409,
        )
    # Soft cancel: keep the row + its run history for audit.
    schedule.enabled = False
    schedule.status = "cancelled"
    schedule.next_run_at = None
    schedule.row_version += 1
    org, ws = _scope(context)
    await record_audit(
        db,
        "pipeline.schedule.cancelled",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="pipeline",
        resource_id=pipeline.id,
        metadata={"schedule_id": str(schedule.id)},
    )
    await db.commit()


async def list_schedule_runs(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, schedule_id: UUID
) -> list[PipelineScheduleRunResponse]:
    await require_pipeline_access(db, context, pipeline_id, "viewer")
    schedule = await _get(db, context, schedule_id)
    org, ws = _scope(context)
    rows = (
        await db.scalars(
            select(PipelineScheduleRun)
            .where(
                PipelineScheduleRun.organization_id == org,
                PipelineScheduleRun.workspace_id == ws,
                PipelineScheduleRun.schedule_id == schedule.id,
            )
            .order_by(PipelineScheduleRun.created_at.desc())
            .limit(100)
        )
    ).all()
    return [PipelineScheduleRunResponse.model_validate(row) for row in rows]
