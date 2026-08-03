"""Integration: ACL Operator can start/retry/cancel without broad pipeline.execute."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import ResourceAccessEntry, Role
from vip_api.governance.seed import provision_organization_governance
from vip_api.pipelines.models import PipelineRun
from vip_api.pipelines.schemas import EdgeInput, NodeInput, PipelineCreate, PipelineEditorSave
from vip_api.pipelines.services import (
    cancel_run,
    create_pipeline,
    create_run,
    publish_pipeline,
    retry_run,
    save_editor,
)
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)


def _ctx(
    user: UUID, org: UUID, ws: UUID, permissions: frozenset[str] = frozenset()
) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_member",
        workspace_role_key="workspace_member",
        permissions=permissions,
        entitlements=frozenset({"pipeline_studio"}),
        feature_flags={"pipeline_studio": True},
        quotas={},
        correlation_id="pipeline-acl-run-test",
    )


async def _seed(db: AsyncSession, suffix: str) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID]:
    owner = User(
        username=f"por-owner-{suffix}",
        normalized_username=f"por-owner-{suffix}",
        email=f"por-owner-{suffix}@vip.test",
        normalized_email=f"por-owner-{suffix}@vip.test",
        display_name="Owner",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    operator = User(
        username=f"por-op-{suffix}",
        normalized_username=f"por-op-{suffix}",
        email=f"por-op-{suffix}@vip.test",
        normalized_email=f"por-op-{suffix}@vip.test",
        display_name="Operator",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    viewer = User(
        username=f"por-view-{suffix}",
        normalized_username=f"por-view-{suffix}",
        email=f"por-view-{suffix}@vip.test",
        normalized_email=f"por-view-{suffix}@vip.test",
        display_name="Viewer",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add_all((owner, operator, viewer))
    await db.flush()
    org = Organization(
        name=f"ACL Run Org {suffix}",
        slug=f"por-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=owner.id,
    )
    db.add(org)
    await db.flush()
    await provision_organization_governance(db, org.id)
    ws = Workspace(
        organization_id=org.id,
        name="ACL Run WS",
        slug="por-ws",
        status=WorkspaceStatus.ACTIVE,
        is_default=True,
        created_by_user_id=owner.id,
    )
    db.add(ws)
    await db.flush()
    role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
    assert role_id is not None
    for uid in (owner.id, operator.id, viewer.id):
        db.add(
            OrganizationMembership(
                organization_id=org.id,
                user_id=uid,
                role_id=role_id,
                status=MembershipStatus.ACTIVE,
            )
        )
    ctype = ConnectionType(
        key=f"por-pg-{suffix}",
        name="Postgres",
        category="database",
        configuration_schema={},
        secret_schema={},
        capabilities=["discover"],
        test_strategy="noop",
    )
    db.add(ctype)
    await db.flush()
    connection = Connection(
        organization_id=org.id,
        workspace_id=ws.id,
        connection_type_id=ctype.id,
        name="Conn",
        normalized_name="conn",
        configuration={},
        connection_type_version=1,
        status="active",
    )
    db.add(connection)
    await db.flush()
    dataset = Dataset(
        organization_id=org.id,
        workspace_id=ws.id,
        connection_id=connection.id,
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
    db.add(
        DatasetField(
            organization_id=org.id,
            workspace_id=ws.id,
            dataset_id=dataset.id,
            source_name="id",
            display_name="id",
            ordinal_position=0,
            physical_data_type="bigint",
            normalized_data_type="integer",
            is_nullable=False,
        )
    )
    await db.commit()
    return owner.id, operator.id, viewer.id, org.id, ws.id, dataset.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acl_operator_can_run_retry_cancel_without_broad_execute(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            owner_id, operator_id, viewer_id, org_id, ws_id, dataset_id = await _seed(db, suffix)
            user_ids = [owner_id, operator_id, viewer_id]

            owner_ctx = _ctx(
                owner_id,
                org_id,
                ws_id,
                frozenset(
                    {"pipeline.read", "pipeline.create", "pipeline.update", "pipeline.execute"}
                ),
            )
            created = await create_pipeline(db, owner_ctx, PipelineCreate(name="ACL Run Pipeline"))
            pid = created.pipeline.id
            saved = await save_editor(
                db,
                owner_ctx,
                pid,
                PipelineEditorSave(
                    name="ACL Run Pipeline",
                    expected_version=created.pipeline.row_version,
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
                            key="e1",
                            source="source",
                            target="export",
                            source_port="out",
                            target_port="in",
                        )
                    ],
                ),
            )
            await publish_pipeline(
                db, owner_ctx, pid, saved.pipeline.row_version, "ACL operator run fixture"
            )

            db.add_all(
                (
                    ResourceAccessEntry(
                        organization_id=org_id,
                        workspace_id=ws_id,
                        resource_type="pipeline",
                        resource_id=pid,
                        subject_type="user",
                        subject_id=operator_id,
                        access_level="operator",
                        effect="allow",
                    ),
                    ResourceAccessEntry(
                        organization_id=org_id,
                        workspace_id=ws_id,
                        resource_type="pipeline",
                        resource_id=pid,
                        subject_type="user",
                        subject_id=viewer_id,
                        access_level="viewer",
                        effect="allow",
                    ),
                )
            )
            await db.commit()

            # No broad pipeline.execute / pipeline.runs.retry — ACL only.
            operator_ctx = _ctx(operator_id, org_id, ws_id)
            viewer_ctx = _ctx(viewer_id, org_id, ws_id)

            with pytest.raises(ApplicationError) as viewer_exc:
                await create_run(db, viewer_ctx, pid)
            assert viewer_exc.value.status_code == 404

            run = await create_run(db, operator_ctx, pid)
            assert run.status in {"queued", "running", "retrying"}

            # Cancel while queued (operator).
            cancelled = await cancel_run(db, operator_ctx, pid, run.id)
            assert cancelled.status == "cancelled"

            # Force failed so retry can be exercised.
            row = await db.scalar(select(PipelineRun).where(PipelineRun.id == run.id))
            assert row is not None
            row.status = "failed"
            row.current_attempt = 1
            row.max_attempts = 3
            await db.commit()

            retried = await retry_run(db, operator_ctx, pid, run.id)
            assert retried.status == "retrying"

            with pytest.raises(ApplicationError):
                await retry_run(db, viewer_ctx, pid, run.id)
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                await db.execute(
                    delete(ResourceAccessEntry).where(ResourceAccessEntry.organization_id == org_id)
                )
                await db.execute(delete(PipelineRun).where(PipelineRun.organization_id == org_id))
                from vip_api.pipelines.models import Pipeline

                await db.execute(delete(Pipeline).where(Pipeline.organization_id == org_id))
                await db.execute(delete(Dataset).where(Dataset.organization_id == org_id))
                await db.execute(delete(Connection).where(Connection.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.dispose()
