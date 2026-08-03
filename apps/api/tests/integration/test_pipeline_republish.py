"""Pipeline re-publish state machine (Phase B9.0 critical stabilization).

Proves a pipeline can be published repeatedly: each publish mints the next
sequential immutable version, a saved draft returns the pipeline to ``draft`` so
Publish is available again, prior versions and their runs stay linked to the
version they were created from, optimistic concurrency is enforced, and invalid
graphs cannot be published.
"""

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
from vip_api.governance.models import Role
from vip_api.pipelines.models import PipelineVersion
from vip_api.pipelines.schemas import EdgeInput, NodeInput, PipelineCreate, PipelineEditorSave
from vip_api.pipelines.services import (
    create_pipeline,
    create_run,
    get_editor,
    publish_pipeline,
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
        correlation_id="pipeline-republish-test",
    )


def _valid_payload(name: str, expected_version: int, dataset_id: UUID) -> PipelineEditorSave:
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
                key="source-to-export",
                source="source",
                target="export",
                source_port="out",
                target_port="in",
            )
        ],
    )


async def _seed(db: AsyncSession, suffix: str) -> tuple[UUID, UUID, UUID, UUID]:
    """Seed a tenant plus an active connection + governed dataset so a
    source→export graph passes full publish validation."""
    user = User(
        username=f"republish-{suffix}",
        normalized_username=f"republish-{suffix}",
        email=f"republish-{suffix}@vip.test",
        normalized_email=f"republish-{suffix}@vip.test",
        display_name="Republish",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    org = Organization(
        name=f"Republish Org {suffix}",
        slug=f"republish-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=user.id,
    )
    db.add(org)
    await db.flush()
    ws = Workspace(
        organization_id=org.id,
        name="RP WS",
        slug="rp-ws",
        status=WorkspaceStatus.ACTIVE,
        is_default=True,
        created_by_user_id=user.id,
    )
    db.add(ws)
    await db.flush()
    role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
    db.add(
        OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role_id=role_id,
            status=MembershipStatus.ACTIVE,
        )
    )
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
    db.add_all(
        DatasetField(
            organization_id=org.id,
            workspace_id=ws.id,
            dataset_id=dataset.id,
            source_name=name,
            display_name=name,
            ordinal_position=index,
            physical_data_type=phys,
            normalized_data_type=norm,
            is_nullable=nullable,
        )
        for index, (name, phys, norm, nullable) in enumerate(
            [("id", "bigint", "integer", False), ("amount", "numeric", "number", True)]
        )
    )
    await db.commit()
    return user.id, org.id, ws.id, dataset.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_can_be_published_repeatedly(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id = await _seed(db, suffix)
            org_ids.append(org_id)
            user_ids.append(user_id)
            ctx = _context(user_id, org_id, ws_id)

            created = await create_pipeline(db, ctx, PipelineCreate(name="Republishable"))
            pid = created.pipeline.id

            # Save draft v1 -> status draft.
            saved = await save_editor(
                db,
                ctx,
                pid,
                _valid_payload("Republishable", created.pipeline.row_version, dataset_id),
            )
            assert saved.pipeline.status == "draft"

            # Publish version 1.
            v1 = await publish_pipeline(db, ctx, pid, saved.pipeline.row_version, "first")
            assert v1.version_number == 1
            editor = await get_editor(db, ctx, pid)
            assert editor.pipeline.status == "published"

            # A run created now is linked to version 1.
            run1 = await create_run(db, ctx, pid)
            assert run1.pipeline_version_id == v1.id

            # Editing again returns the pipeline to draft (Publish becomes available).
            edited = await save_editor(
                db,
                ctx,
                pid,
                _valid_payload("Republishable v2", editor.pipeline.row_version, dataset_id),
            )
            assert edited.pipeline.status == "draft"

            # Publish version 2 -> sequential, immutable, new published pointer.
            v2 = await publish_pipeline(db, ctx, pid, edited.pipeline.row_version, "second")
            assert v2.version_number == 2
            assert v2.id != v1.id
            republished = await get_editor(db, ctx, pid)
            assert republished.pipeline.status == "published"

            # Publish version 3 to confirm the sequence continues.
            edited3 = await save_editor(
                db,
                ctx,
                pid,
                _valid_payload("Republishable v3", republished.pipeline.row_version, dataset_id),
            )
            v3 = await publish_pipeline(db, ctx, pid, edited3.pipeline.row_version, "third")
            assert v3.version_number == 3

            # All three immutable versions persist with distinct content hashes.
            versions = list(
                (
                    await db.scalars(
                        select(PipelineVersion)
                        .where(PipelineVersion.pipeline_id == pid)
                        .order_by(PipelineVersion.version_number)
                    )
                ).all()
            )
            assert [v.version_number for v in versions] == [1, 2, 3]

            # The original run remains linked to version 1 (immutable linkage); a new
            # run now targets the latest published version (3).
            still_v1 = await db.scalar(
                select(PipelineVersion.version_number).where(
                    PipelineVersion.id == run1.pipeline_version_id
                )
            )
            assert still_v1 == 1
            run_latest = await create_run(db, ctx, pid)
            assert run_latest.pipeline_version_id == v3.id

            # Optimistic concurrency: publishing with a stale version conflicts.
            with pytest.raises(ApplicationError) as conflict:
                await publish_pipeline(db, ctx, pid, 1, "stale")
            assert conflict.value.code == "VERSION_CONFLICT"
    finally:
        async with database.session_factory() as db:
            for oid in org_ids:
                await db.execute(delete(DatasetField).where(DatasetField.organization_id == oid))
                await db.execute(delete(Dataset).where(Dataset.organization_id == oid))
                await db.execute(delete(Connection).where(Connection.organization_id == oid))
                await db.execute(delete(Organization).where(Organization.id == oid))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_pipeline_cannot_be_published(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id = await _seed(db, suffix)
            org_ids.append(org_id)
            user_ids.append(user_id)
            ctx = _context(user_id, org_id, ws_id)

            created = await create_pipeline(db, ctx, PipelineCreate(name="Invalid"))
            pid = created.pipeline.id
            # A lone source node with no export sink is an incomplete graph.
            incomplete = PipelineEditorSave(
                name="Invalid",
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
                    )
                ],
                edges=[],
            )
            saved = await save_editor(db, ctx, pid, incomplete)
            with pytest.raises(ApplicationError) as invalid:
                await publish_pipeline(db, ctx, pid, saved.pipeline.row_version, "nope")
            assert invalid.value.code == "PIPELINE_INVALID"
    finally:
        async with database.session_factory() as db:
            for oid in org_ids:
                await db.execute(delete(DatasetField).where(DatasetField.organization_id == oid))
                await db.execute(delete(Dataset).where(Dataset.organization_id == oid))
                await db.execute(delete(Connection).where(Connection.organization_id == oid))
                await db.execute(delete(Organization).where(Organization.id == oid))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.engine.dispose()
