"""Recurring delivery scheduler integration coverage (Phase B9.1A).

Drives ``dispatch_due_deliveries`` against vip_test: due-schedule claiming,
duplicate prevention, concurrent schedulers, pause, one-time completion, revoked
creator access, and tenant isolation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.dashboard_delivery.models import DashboardDeliveryRun, DashboardDeliverySchedule
from vip_api.dashboard_delivery.scheduler import dispatch_due_deliveries
from vip_api.dashboards.models import Dashboard, DashboardVersion
from vip_api.database.session import Database
from vip_api.governance.seed import provision_organization_governance, seed_system_governance
from vip_api.governance.services import get_role
from vip_api.jobs.queue import QueueMetrics
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


class _QueueStub:
    """Records enqueue calls; the scheduler tolerates enqueue failures either way."""

    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def enqueue(
        self, queue: str, job_id: UUID, *, priority: int = 0, delay_seconds: float = 0
    ) -> None:
        self.enqueued.append(job_id)

    async def dequeue(self, queue: str) -> UUID | None:
        return None

    async def metrics(self, queue: str) -> QueueMetrics:
        return QueueMetrics(queue=queue, ready=0, delayed=0)


@dataclass
class _Seed:
    user_id: UUID
    org_id: UUID
    ws_id: UUID
    dashboard_id: UUID
    version_id: UUID


async def _seed(
    db: AsyncSession,
    suffix: str,
    *,
    schedule_type: str = "daily",
    enabled: bool = True,
    due: bool = True,
) -> tuple[_Seed, UUID]:
    user = User(
        username=f"deliv-{suffix}",
        normalized_username=f"deliv-{suffix}",
        email=f"deliv-{suffix}@vip.test",
        normalized_email=f"deliv-{suffix}@vip.test",
        display_name="Delivery Owner",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    org = Organization(
        name=f"Deliv Org {suffix}",
        slug=f"deliv-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=user.id,
    )
    db.add(org)
    await db.flush()
    await provision_organization_governance(db, org.id)
    ws = Workspace(
        organization_id=org.id,
        name="Deliv WS",
        slug="deliv-ws",
        status=WorkspaceStatus.ACTIVE,
        is_default=True,
        created_by_user_id=user.id,
    )
    db.add(ws)
    await db.flush()
    org_admin = await get_role(db, "organization_admin", "organization")
    ws_admin = await get_role(db, "workspace_admin", "workspace")
    db.add_all(
        (
            OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role_id=org_admin.id,
                status=MembershipStatus.ACTIVE,
            ),
            WorkspaceMembership(
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=user.id,
                role_id=ws_admin.id,
                status=MembershipStatus.ACTIVE,
            ),
        )
    )
    dashboard = Dashboard(
        organization_id=org.id,
        workspace_id=ws.id,
        name=f"Deliv Dashboard {suffix}",
        slug=f"deliv-dash-{suffix}",
        status="published",
        owner_user_id=user.id,
        created_by_user_id=user.id,
    )
    db.add(dashboard)
    await db.flush()
    version = DashboardVersion(
        organization_id=org.id,
        workspace_id=ws.id,
        dashboard_id=dashboard.id,
        version_number=1,
        version_type="published",
        snapshot={"schema_version": 1, "pages": []},
        created_by_user_id=user.id,
    )
    db.add(version)
    await db.flush()
    dashboard.published_version_id = version.id
    schedule = DashboardDeliverySchedule(
        organization_id=org.id,
        workspace_id=ws.id,
        dashboard_id=dashboard.id,
        dashboard_version_id=version.id,
        name=f"Nightly {suffix}",
        recipients=["ops@vip.test"],
        cc=[],
        bcc=[],
        subject="Nightly dashboard",
        format="csv",
        filters={},
        schedule_type=schedule_type,
        timezone="UTC",
        enabled=enabled,
        status="scheduled" if enabled else "paused",
        max_retries=3,
        created_by_user_id=user.id,
        next_run_at=(NOW - timedelta(minutes=5)) if due else (NOW + timedelta(days=1)),
    )
    db.add(schedule)
    await db.flush()
    schedule_id = schedule.id
    await db.commit()
    return _Seed(user.id, org.id, ws.id, dashboard.id, version.id), schedule_id


async def _cleanup(database: Database, org_ids: list[UUID], user_ids: list[UUID]) -> None:
    async with database.session_factory() as db:
        for oid in org_ids:
            await db.execute(delete(Organization).where(Organization.id == oid))
        for uid in user_ids:
            await db.execute(delete(User).where(User.id == uid))
        await db.commit()
    await database.engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_due_schedule_dispatches_and_dedupes(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8])
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)

        dispatched = await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW)
        assert dispatched == 1

        async with database.session_factory() as db:
            runs = list(
                (
                    await db.scalars(
                        select(DashboardDeliveryRun).where(
                            DashboardDeliveryRun.schedule_id == schedule_id
                        )
                    )
                ).all()
            )
            assert len(runs) == 1
            assert runs[0].export_id is not None  # export created + linked
            schedule = await db.get(DashboardDeliverySchedule, schedule_id)
            assert schedule is not None
            # next_run_at advanced into the future — the slot is consumed.
            assert schedule.next_run_at is not None and schedule.next_run_at > NOW

        # A re-tick at the same instant claims nothing (duplicate prevention).
        assert await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW) == 0
        async with database.session_factory() as db:
            count = len(
                list(
                    (
                        await db.scalars(
                            select(DashboardDeliveryRun).where(
                                DashboardDeliveryRun.schedule_id == schedule_id
                            )
                        )
                    ).all()
                )
            )
            assert count == 1
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_paused_and_future_schedules_are_not_claimed(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            paused, _ = await _seed(db, uuid4().hex[:8], enabled=False, due=False)
            org_ids.append(paused.org_id)
            user_ids.append(paused.user_id)
        assert await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW) == 0
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_time_schedule_completes_after_dispatch(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8], schedule_type="one_time")
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)
        assert await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW) == 1
        async with database.session_factory() as db:
            schedule = await db.get(DashboardDeliverySchedule, schedule_id)
            assert schedule is not None
            assert schedule.enabled is False
            assert schedule.next_run_at is None
            assert schedule.status == "completed"
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoked_creator_access_fails_the_run(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8])
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)
        # Revoke the creator's workspace membership before the tick.
        async with database.session_factory() as db:
            await db.execute(
                delete(WorkspaceMembership).where(
                    WorkspaceMembership.user_id == seed.user_id,
                    WorkspaceMembership.workspace_id == seed.ws_id,
                )
            )
            await db.commit()

        await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW)
        async with database.session_factory() as db:
            run = await db.scalar(
                select(DashboardDeliveryRun).where(DashboardDeliveryRun.schedule_id == schedule_id)
            )
            assert run is not None
            assert run.status == "failed"
            assert run.safe_error_code == "DELIVERY_ACCESS_REVOKED"
            assert run.export_id is None
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_schedulers_claim_each_slot_once(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            schedule_ids: list[UUID] = []
            for _ in range(3):
                seed, schedule_id = await _seed(db, uuid4().hex[:8])
                org_ids.append(seed.org_id)
                user_ids.append(seed.user_id)
                schedule_ids.append(schedule_id)

        # Two schedulers tick simultaneously; SKIP LOCKED must prevent double-claim.
        results = await asyncio.gather(
            dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW),
            dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW),
        )
        assert sum(results) == 3
        async with database.session_factory() as db:
            for schedule_id in schedule_ids:
                runs = list(
                    (
                        await db.scalars(
                            select(DashboardDeliveryRun).where(
                                DashboardDeliveryRun.schedule_id == schedule_id
                            )
                        )
                    ).all()
                )
                assert len(runs) == 1  # exactly once, never duplicated
    finally:
        await _cleanup(database, org_ids, user_ids)
