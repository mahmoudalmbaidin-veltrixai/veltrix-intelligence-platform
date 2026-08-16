"""Recurring pipeline-run scheduler.

Claims due ``PipelineSchedule`` rows with ``FOR UPDATE SKIP LOCKED`` and advances
``next_run_at`` inside the claim transaction, so concurrent schedulers and
re-ticks never double-fire a slot. Each claimed slot becomes a
``PipelineScheduleRun`` plus a real ``PipelineRun`` created under the schedule
creator's rebuilt authorization context — execution then flows through the
existing pipeline worker (which polls ``pipeline_runs``). No second queue.

Execution-identity policy: a scheduled run executes as the schedule's
``created_by_user_id``; if that user's org/workspace membership was revoked the
run is recorded failed (``PIPELINE_ACCESS_REVOKED``), mirroring the interactive
run path's live-membership enforcement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vip_api.auth.models import utc_now
from vip_api.core.config import Settings
from vip_api.dashboard_delivery.scheduling import advance_next_run
from vip_api.database.session import Database
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import resolve_authorization_context
from vip_api.pipelines.models import Pipeline, PipelineSchedule, PipelineScheduleRun
from vip_api.pipelines.services import create_run
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.models import MembershipStatus, OrganizationMembership, WorkspaceMembership

logger = logging.getLogger("vip_api.pipelines.scheduler")


@dataclass(frozen=True, slots=True)
class _ClaimedSlot:
    schedule_run_id: UUID
    schedule_id: UUID
    organization_id: UUID
    workspace_id: UUID
    pipeline_id: UUID
    pipeline_version_id: UUID | None
    created_by_user_id: UUID


async def _claim_due(db: AsyncSession, *, now: datetime, limit: int) -> list[_ClaimedSlot]:
    # Defense-in-depth lifecycle guard: only claim schedules whose pipeline still
    # exists and is not archived. Schedules are also disabled when a pipeline is
    # archived, but this correlated EXISTS makes the scheduler safe against any
    # legacy/orphan enabled rows without a second round-trip and without adding the
    # pipelines table to the FOR UPDATE lock (only pipeline_schedules is locked).
    live_pipeline = (
        select(Pipeline.id)
        .where(
            Pipeline.organization_id == PipelineSchedule.organization_id,
            Pipeline.workspace_id == PipelineSchedule.workspace_id,
            Pipeline.id == PipelineSchedule.pipeline_id,
            Pipeline.archived_at.is_(None),
        )
        .exists()
    )
    schedules = list(
        (
            await db.scalars(
                select(PipelineSchedule)
                .where(
                    PipelineSchedule.enabled.is_(True),
                    PipelineSchedule.next_run_at.is_not(None),
                    PipelineSchedule.next_run_at <= now,
                    live_pipeline,
                )
                .order_by(PipelineSchedule.next_run_at)
                .with_for_update(skip_locked=True, of=PipelineSchedule)
                .limit(limit)
            )
        ).all()
    )
    slots: list[_ClaimedSlot] = []
    for schedule in schedules:
        run_record = PipelineScheduleRun(
            organization_id=schedule.organization_id,
            workspace_id=schedule.workspace_id,
            schedule_id=schedule.id,
            status="queued",
        )
        db.add(run_record)
        await db.flush()
        upcoming = advance_next_run(
            schedule_type=schedule.schedule_type,
            schedule_expression=schedule.schedule_expression,
            timezone=schedule.timezone,
            previous_next_run=schedule.next_run_at or now,
            now=now,
        )
        schedule.last_run_at = now
        schedule.next_run_at = upcoming
        if upcoming is None:
            schedule.enabled = False
            schedule.status = "completed"
        else:
            schedule.status = "scheduled"
        schedule.row_version += 1
        # NB: the success audit is deliberately NOT recorded here. Claiming a due
        # schedule is not the same as enqueueing its run — recording "dispatched"
        # before create_run() succeeds produces a false-success audit (VIP-BUG-006).
        # The truthful audit is emitted in _dispatch_slot after enqueue succeeds,
        # and a failure audit is emitted when enqueue/access fails.
        slots.append(
            _ClaimedSlot(
                schedule_run_id=run_record.id,
                schedule_id=schedule.id,
                organization_id=schedule.organization_id,
                workspace_id=schedule.workspace_id,
                pipeline_id=schedule.pipeline_id,
                pipeline_version_id=schedule.pipeline_version_id,
                created_by_user_id=schedule.created_by_user_id,
            )
        )
    await db.commit()
    return slots


async def _actor_context(db: AsyncSession, slot: _ClaimedSlot) -> AuthorizationContext:
    organization_membership = await db.scalar(
        select(OrganizationMembership)
        .options(selectinload(OrganizationMembership.role))
        .where(
            OrganizationMembership.organization_id == slot.organization_id,
            OrganizationMembership.user_id == slot.created_by_user_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    workspace_membership = await db.scalar(
        select(WorkspaceMembership)
        .options(selectinload(WorkspaceMembership.role))
        .where(
            WorkspaceMembership.organization_id == slot.organization_id,
            WorkspaceMembership.workspace_id == slot.workspace_id,
            WorkspaceMembership.user_id == slot.created_by_user_id,
            WorkspaceMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if organization_membership is None or workspace_membership is None:
        raise PermissionError("pipeline schedule creator no longer has active access")
    tenant = TenantContext(
        user_id=slot.created_by_user_id,
        organization_id=slot.organization_id,
        workspace_id=slot.workspace_id,
        organization_membership_id=organization_membership.id,
        workspace_membership_id=workspace_membership.id,
        organization_role=organization_membership.role.key,
        workspace_role=workspace_membership.role.key,
        correlation_id=f"pipeline-schedule-{slot.schedule_id}",
    )
    return await resolve_authorization_context(db, tenant)


async def _mark_failed(database: Database, slot: _ClaimedSlot, code: str, message: str) -> None:
    """Record a truthful failure: mark the schedule-run failed AND emit a failure
    audit in the same transaction. No success audit is ever written on this path."""
    async with database.session_factory() as db:
        run = await db.get(PipelineScheduleRun, slot.schedule_run_id)
        if run is not None:
            run.status = "failed"
            run.safe_error_code = code
            run.safe_error_message = message
            run.completed_at = utc_now()
        await record_audit(
            db,
            "pipeline.schedule.dispatch_failed",
            actor_user_id=slot.created_by_user_id,
            organization_id=slot.organization_id,
            workspace_id=slot.workspace_id,
            outcome="failure",
            reason_code=code,
            resource_type="pipeline",
            resource_id=slot.pipeline_id,
            metadata={
                "schedule_id": str(slot.schedule_id),
                "schedule_run_id": str(slot.schedule_run_id),
            },
        )
        await db.commit()


async def _dispatch_slot(database: Database, settings: Settings, slot: _ClaimedSlot) -> bool:
    try:
        async with database.session_factory() as db:
            context = await _actor_context(db, slot)
    except PermissionError:
        await _mark_failed(
            database,
            slot,
            "PIPELINE_ACCESS_REVOKED",
            "The schedule creator no longer has access to run this pipeline.",
        )
        return False
    try:
        async with database.session_factory() as db:
            run = await create_run(
                db,
                context,
                slot.pipeline_id,
                slot.pipeline_version_id,
                trigger="scheduled",
            )
    except Exception as error:  # safe-code the failure; never leak internals
        logger.warning("Pipeline schedule dispatch failed", exc_info=error)
        await _mark_failed(
            database,
            slot,
            "PIPELINE_SCHEDULE_RUN_FAILED",
            "The scheduled pipeline run could not be enqueued.",
        )
        return False
    # Enqueue succeeded: only now is it truthful to record the run and the
    # success audit, together in one transaction (VIP-BUG-006).
    async with database.session_factory() as db:
        record = await db.get(PipelineScheduleRun, slot.schedule_run_id)
        if record is not None:
            record.run_id = run.id
            record.status = "dispatched"
            record.completed_at = utc_now()
        await record_audit(
            db,
            "pipeline.schedule.dispatched",
            actor_user_id=slot.created_by_user_id,
            organization_id=slot.organization_id,
            workspace_id=slot.workspace_id,
            resource_type="pipeline",
            resource_id=slot.pipeline_id,
            metadata={
                "schedule_id": str(slot.schedule_id),
                "schedule_run_id": str(slot.schedule_run_id),
                "run_id": str(run.id),
            },
        )
        await db.commit()
    return True


async def dispatch_due_pipeline_schedules(
    database: Database, settings: Settings, *, now: datetime | None = None
) -> int:
    """One scheduler tick: claim due schedules and enqueue their pipeline runs."""
    moment = now or datetime.now(UTC)
    async with database.session_factory() as db:
        claimed = await _claim_due(db, now=moment, limit=settings.PIPELINE_SCHEDULER_BATCH)
    dispatched = 0
    for slot in claimed:
        if await _dispatch_slot(database, settings, slot):
            dispatched += 1
    return dispatched
