"""Recurring dashboard-delivery scheduler.

Claims due schedules with ``FOR UPDATE SKIP LOCKED`` and advances ``next_run_at``
inside the claim transaction, so concurrent schedulers and re-ticks never
double-fire a slot. Each claimed slot becomes a ``DashboardDeliveryRun`` plus a
dashboard export created under the schedule creator's authorization context —
delivery execution then flows through the existing ``dashboard.export`` job
handler and email pipeline. This adds no second queue platform.

Execution-identity policy: a future delivery runs as the schedule's
``created_by_user_id``. If that user's org/workspace membership has been revoked,
the actor context cannot be built and the run is recorded as failed
(``DELIVERY_ACCESS_REVOKED``) — future executions therefore respect live tenant
membership and access revocation, exactly like the interactive export path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vip_api.core.config import Settings
from vip_api.core.metrics import metrics
from vip_api.dashboard_delivery.models import DashboardDeliveryRun, DashboardDeliverySchedule
from vip_api.dashboard_delivery.scheduling import advance_next_run
from vip_api.dashboard_delivery.schemas import ExportCreate
from vip_api.dashboard_delivery.services import create_export
from vip_api.database.session import Database
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import resolve_authorization_context
from vip_api.jobs.queue import JobQueue
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.models import MembershipStatus, OrganizationMembership, WorkspaceMembership

logger = logging.getLogger("vip_api.dashboard_delivery.scheduler")


@dataclass(frozen=True, slots=True)
class _ClaimedSlot:
    run_id: UUID
    schedule_id: UUID
    organization_id: UUID
    workspace_id: UUID
    dashboard_id: UUID
    created_by_user_id: UUID
    format: str
    filters: dict[str, object]
    timezone: str


async def _actor_context(db: AsyncSession, slot: _ClaimedSlot) -> AuthorizationContext:
    """Rebuild the schedule creator's authorization context (fails if revoked)."""
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
        raise PermissionError("delivery schedule creator no longer has active access")
    tenant = TenantContext(
        user_id=slot.created_by_user_id,
        organization_id=slot.organization_id,
        workspace_id=slot.workspace_id,
        organization_membership_id=organization_membership.id,
        workspace_membership_id=workspace_membership.id,
        organization_role=organization_membership.role.key,
        workspace_role=workspace_membership.role.key,
        correlation_id=f"delivery-schedule-{slot.schedule_id}",
    )
    return await resolve_authorization_context(db, tenant)


async def _claim_due_schedules(
    db: AsyncSession, *, now: datetime, limit: int
) -> list[_ClaimedSlot]:
    """Atomically claim due schedules: create a run and advance next_run_at."""
    schedules = list(
        (
            await db.scalars(
                select(DashboardDeliverySchedule)
                .where(
                    DashboardDeliverySchedule.enabled.is_(True),
                    DashboardDeliverySchedule.next_run_at.is_not(None),
                    DashboardDeliverySchedule.next_run_at <= now,
                )
                .order_by(DashboardDeliverySchedule.next_run_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
    )
    claimed: list[_ClaimedSlot] = []
    for schedule in schedules:
        run = DashboardDeliveryRun(
            organization_id=schedule.organization_id,
            workspace_id=schedule.workspace_id,
            schedule_id=schedule.id,
            status="queued",
        )
        db.add(run)
        await db.flush()
        assert schedule.next_run_at is not None
        upcoming = advance_next_run(
            schedule_type=schedule.schedule_type,
            schedule_expression=schedule.schedule_expression,
            timezone=schedule.timezone,
            previous_next_run=schedule.next_run_at,
            now=now,
        )
        schedule.next_run_at = upcoming
        if upcoming is None:
            # A one-time schedule does not recur.
            schedule.enabled = False
            schedule.status = "completed"
        else:
            schedule.status = "scheduled"
        schedule.row_version += 1
        await record_audit(
            db,
            "dashboard.delivery.scheduled",
            actor_user_id=schedule.created_by_user_id,
            organization_id=schedule.organization_id,
            workspace_id=schedule.workspace_id,
            resource_type="dashboard_delivery_schedule",
            resource_id=schedule.id,
            metadata={
                "run_id": str(run.id),
                "next_run_at": upcoming.isoformat() if upcoming else None,
            },
        )
        claimed.append(
            _ClaimedSlot(
                run_id=run.id,
                schedule_id=schedule.id,
                organization_id=schedule.organization_id,
                workspace_id=schedule.workspace_id,
                dashboard_id=schedule.dashboard_id,
                created_by_user_id=schedule.created_by_user_id,
                format=schedule.format,
                filters=dict(schedule.filters),
                timezone=schedule.timezone,
            )
        )
    await db.commit()
    return claimed


async def _mark_run_failed(db: AsyncSession, run_id: UUID, code: str, message: str) -> None:
    run = await db.scalar(select(DashboardDeliveryRun).where(DashboardDeliveryRun.id == run_id))
    if run is None:
        return
    run.status = "failed"
    run.safe_error_code = code
    run.safe_error_message = message
    run.completed_at = datetime.now(UTC)
    await db.commit()


async def _dispatch_slot(
    database: Database, settings: Settings, queue: JobQueue, slot: _ClaimedSlot
) -> bool:
    """Create the export for a claimed slot under the creator's identity."""
    async with database.session_factory() as db:
        try:
            context = await _actor_context(db, slot)
        except PermissionError:
            await _mark_run_failed(
                db,
                slot.run_id,
                "DELIVERY_ACCESS_REVOKED",
                "Delivery access is no longer available.",
            )
            metrics.record_delivery_scheduled("access_revoked")
            logger.warning(
                "Skipped delivery for revoked schedule creator",
                extra={"schedule_id": str(slot.schedule_id), "run_id": str(slot.run_id)},
            )
            return False
    async with database.session_factory() as db:
        try:
            export = await create_export(
                db,
                context,
                slot.dashboard_id,
                ExportCreate.model_validate(
                    {"format": slot.format, "filters": slot.filters, "timezone": slot.timezone}
                ),
                settings,
                delivery_run_id=slot.run_id,
                queue=queue,
            )
        except Exception as exc:
            await _mark_run_failed(
                db,
                slot.run_id,
                "DELIVERY_EXPORT_FAILED",
                "The scheduled export could not be started.",
            )
            metrics.record_delivery_scheduled("export_error")
            logger.warning(
                "Scheduled export creation failed",
                extra={
                    "schedule_id": str(slot.schedule_id),
                    "run_id": str(slot.run_id),
                    "exception_type": type(exc).__name__,
                },
            )
            return False
        run = await db.scalar(
            select(DashboardDeliveryRun).where(DashboardDeliveryRun.id == slot.run_id)
        )
        if run is not None:
            run.export_id = export.id
            await db.commit()
    metrics.record_delivery_scheduled("dispatched")
    return True


async def dispatch_due_deliveries(
    database: Database,
    settings: Settings,
    queue: JobQueue,
    *,
    now: datetime | None = None,
) -> int:
    """One scheduler tick: claim due schedules and start their deliveries.

    Returns the number of slots successfully dispatched. Safe to run
    concurrently across workers (per-row SKIP LOCKED claim + next_run advance).
    """
    moment = now or datetime.now(UTC)
    async with database.session_factory() as db:
        claimed = await _claim_due_schedules(
            db, now=moment, limit=settings.DASHBOARD_DELIVERY_SCHEDULER_BATCH
        )
    dispatched = 0
    for slot in claimed:
        if await _dispatch_slot(database, settings, queue, slot):
            dispatched += 1
    if claimed:
        logger.info(
            "Delivery scheduler tick complete",
            extra={"claimed": len(claimed), "dispatched": dispatched},
        )
    return dispatched
