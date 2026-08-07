"""Pipeline run-scheduler integration coverage (post-Core P1).

Seeds a published pipeline + a schedule, then drives the scheduler:
due-dispatch (creates a real PipelineRun + schedule-run, advances next_run, does
not re-fire), paused/future not claimed, and revoked-creator access failing the
run — mirroring the dashboard delivery scheduler guarantees.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Role
from vip_api.governance.seed import provision_organization_governance
from vip_api.pipelines.models import PipelineRun, PipelineSchedule, PipelineScheduleRun
from vip_api.pipelines.scheduler import dispatch_due_pipeline_schedules
from vip_api.pipelines.schemas import EdgeInput, NodeInput, PipelineCreate, PipelineEditorSave
from vip_api.pipelines.services import create_pipeline, publish_pipeline, save_editor
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def _context(user: UUID, org: UUID, ws: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset(
            {"pipeline.read", "pipeline.create", "pipeline.update", "pipeline.execute"}
        ),
        entitlements=frozenset({"pipeline_studio"}),
        feature_flags={"pipeline_studio": True},
        quotas={},
        correlation_id="pipeline-scheduler-test",
    )


def _graph(name: str, expected_version: int, dataset_id: UUID) -> PipelineEditorSave:
    return PipelineEditorSave(
        name=name,
        expected_version=expected_version,
        canvas={"x": 0, "y": 0, "scale": 1, "snapGrid": True},
        nodes=[
            NodeInput(
                key="source",
                type="source-dataset",
                title="Source",
                x=10,
                y=20,
                config={"dataset_id": str(dataset_id)},
            ),
            NodeInput(
                key="export",
                type="file-export",
                title="Export",
                x=300,
                y=20,
                config={"format": "csv", "filename": "result.csv"},
            ),
        ],
        edges=[
            EdgeInput(
                key="s-e",
                source="source",
                target="export",
                source_port="out",
                target_port="in",
            )
        ],
    )


async def _seed(db: AsyncSession, suffix: str) -> tuple[UUID, UUID, UUID, UUID]:
    user = User(
        username=f"sched-{suffix}",
        normalized_username=f"sched-{suffix}",
        email=f"sched-{suffix}@vip.test",
        normalized_email=f"sched-{suffix}@vip.test",
        display_name="Sched",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    org = Organization(
        name=f"Sched Org {suffix}",
        slug=f"sched-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=user.id,
    )
    db.add(org)
    await db.flush()
    ws = Workspace(
        organization_id=org.id,
        name="WS",
        slug="ws",
        status=WorkspaceStatus.ACTIVE,
        is_default=True,
        created_by_user_id=user.id,
    )
    db.add(ws)
    await db.flush()
    org_admin = await db.scalar(select(Role.id).where(Role.key == "organization_admin"))
    ws_admin = await db.scalar(select(Role.id).where(Role.key == "workspace_admin"))
    db.add_all(
        (
            OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role_id=org_admin,
                status=MembershipStatus.ACTIVE,
            ),
            WorkspaceMembership(
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=user.id,
                role_id=ws_admin,
                status=MembershipStatus.ACTIVE,
            ),
        )
    )
    await provision_organization_governance(db, org.id)
    ctype = ConnectionType(
        key=f"pg-{suffix}",
        name="Postgres",
        category="database",
        configuration_schema={},
        secret_schema={},
        capabilities=["discover"],
        test_strategy="noop",
    )
    db.add(ctype)
    await db.flush()
    conn = Connection(
        organization_id=org.id,
        workspace_id=ws.id,
        connection_type_id=ctype.id,
        name="Conn",
        normalized_name="conn",
        configuration={},
        connection_type_version=1,
        status="active",
    )
    db.add(conn)
    await db.flush()
    dataset = Dataset(
        organization_id=org.id,
        workspace_id=ws.id,
        connection_id=conn.id,
        dataset_type="table",
        source_schema="public",
        source_name="customers",
        source_key="public.customers",
        qualified_name="public.customers",
        display_name="Customers",
        source_object_type="table",
        status="active",
        version=1,
    )
    db.add(dataset)
    await db.flush()
    db.add_all(
        DatasetField(
            organization_id=org.id,
            workspace_id=ws.id,
            dataset_id=dataset.id,
            source_name=n,
            display_name=n,
            ordinal_position=i,
            physical_data_type=p,
            normalized_data_type=norm,
            is_nullable=nl,
        )
        for i, (n, p, norm, nl) in enumerate(
            [("id", "bigint", "integer", False), ("amount", "numeric", "number", True)]
        )
    )
    await db.commit()
    return user.id, org.id, ws.id, dataset.id


async def _publish(db: AsyncSession, ctx: AuthorizationContext, dataset_id: UUID) -> UUID:
    created = await create_pipeline(db, ctx, PipelineCreate(name="Scheduled"))
    pid = created.pipeline.id
    saved = await save_editor(
        db, ctx, pid, _graph("Scheduled", created.pipeline.row_version, dataset_id)
    )
    await publish_pipeline(db, ctx, pid, saved.pipeline.row_version, "v1")
    return pid


def _schedule(
    org: UUID, ws: UUID, pid: UUID, user: UUID, *, enabled: bool, due: bool
) -> PipelineSchedule:
    return PipelineSchedule(
        organization_id=org,
        workspace_id=ws,
        pipeline_id=pid,
        name="Nightly",
        schedule_type="daily",
        timezone="UTC",
        enabled=enabled,
        status="scheduled" if enabled else "paused",
        created_by_user_id=user,
        next_run_at=(NOW - timedelta(minutes=5))
        if (enabled and due)
        else ((NOW + timedelta(days=1)) if enabled else None),
    )


async def _cleanup(database: Database, org_id: UUID, user_id: UUID) -> None:
    async with database.session_factory() as db:
        # datasets/connections are RESTRICT to the org; delete them first. Pipeline
        # schedules/runs cascade via pipelines->org, but delete explicitly for order.
        await db.execute(delete(DatasetField).where(DatasetField.organization_id == org_id))
        await db.execute(delete(Dataset).where(Dataset.organization_id == org_id))
        await db.execute(delete(Connection).where(Connection.organization_id == org_id))
        await db.execute(delete(Organization).where(Organization.id == org_id))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()
    await database.engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_due_schedule_dispatches_real_run_and_dedupes(settings: Settings) -> None:
    database = Database(settings)
    org_id = user_id = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id = await _seed(db, suffix)
            ctx = _context(user_id, org_id, ws_id)
            pid = await _publish(db, ctx, dataset_id)
            db.add(_schedule(org_id, ws_id, pid, user_id, enabled=True, due=True))
            await db.commit()

        dispatched = await dispatch_due_pipeline_schedules(database, settings, now=NOW)
        assert dispatched == 1

        async with database.session_factory() as db:
            runs = list(
                (await db.scalars(select(PipelineRun).where(PipelineRun.pipeline_id == pid))).all()
            )
            assert len(runs) == 1 and runs[0].trigger == "scheduled"
            srun = await db.scalar(
                select(PipelineScheduleRun).where(PipelineScheduleRun.organization_id == org_id)
            )
            assert srun is not None and srun.status == "dispatched"
            # The schedule-run links the real PipelineRun the scheduler created.
            assert srun.run_id == runs[0].id
            sched = await db.scalar(
                select(PipelineSchedule).where(PipelineSchedule.organization_id == org_id)
            )
            assert sched is not None and sched.next_run_at is not None and sched.next_run_at > NOW

        # Re-tick: next_run advanced to tomorrow, so nothing is claimed.
        assert await dispatch_due_pipeline_schedules(database, settings, now=NOW) == 0
        async with database.session_factory() as db:
            assert (
                len(
                    list(
                        (
                            await db.scalars(
                                select(PipelineRun).where(PipelineRun.pipeline_id == pid)
                            )
                        ).all()
                    )
                )
                == 1
            )
    finally:
        if org_id and user_id:
            await _cleanup(database, org_id, user_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_paused_and_future_schedules_are_not_claimed(settings: Settings) -> None:
    database = Database(settings)
    org_id = user_id = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id = await _seed(db, suffix)
            ctx = _context(user_id, org_id, ws_id)
            pid = await _publish(db, ctx, dataset_id)
            db.add(_schedule(org_id, ws_id, pid, user_id, enabled=False, due=False))  # paused
            db.add(_schedule(org_id, ws_id, pid, user_id, enabled=True, due=False))  # future
            await db.commit()
        assert await dispatch_due_pipeline_schedules(database, settings, now=NOW) == 0
        async with database.session_factory() as db:
            assert (
                await db.scalar(select(PipelineRun).where(PipelineRun.pipeline_id == pid)) is None
            )
    finally:
        if org_id and user_id:
            await _cleanup(database, org_id, user_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoked_creator_access_fails_the_scheduled_run(settings: Settings) -> None:
    database = Database(settings)
    org_id = user_id = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id = await _seed(db, suffix)
            ctx = _context(user_id, org_id, ws_id)
            pid = await _publish(db, ctx, dataset_id)
            db.add(_schedule(org_id, ws_id, pid, user_id, enabled=True, due=True))
            await db.commit()
            # Revoke the creator's workspace membership.
            await db.execute(
                delete(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == ws_id,
                    WorkspaceMembership.user_id == user_id,
                )
            )
            await db.commit()

        dispatched = await dispatch_due_pipeline_schedules(database, settings, now=NOW)
        assert dispatched == 0
        async with database.session_factory() as db:
            srun = await db.scalar(
                select(PipelineScheduleRun).where(PipelineScheduleRun.organization_id == org_id)
            )
            assert srun is not None
            assert srun.status == "failed" and srun.safe_error_code == "PIPELINE_ACCESS_REVOKED"
            assert srun.run_id is None
            assert (
                await db.scalar(select(PipelineRun).where(PipelineRun.pipeline_id == pid)) is None
            )
    finally:
        if org_id and user_id:
            await _cleanup(database, org_id, user_id)
