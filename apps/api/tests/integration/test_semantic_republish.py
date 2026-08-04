"""Semantic model re-publish state machine (Phase B9.1C).

Proves a semantic model can be published repeatedly: each publish mints the next
sequential immutable version, editing a published model returns it to ``draft``
so Publish is available again, a clean published model cannot be republished into
a duplicate version, prior published version snapshots stay immutable, and an
unauthorized caller cannot publish. Mirrors the pipeline re-publish guarantees.
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
from vip_api.governance.seed import provision_organization_governance
from vip_api.semantic.models import SemanticModel, SemanticModelVersion
from vip_api.semantic.schemas import (
    DimensionCreate,
    MeasureCreate,
    MetricCreate,
    SemanticModelCreate,
    SemanticModelUpdate,
)
from vip_api.semantic.services import (
    create_dimension,
    create_measure,
    create_metric,
    create_model,
    publish_model,
    update_model,
    validate_model,
)
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
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
            {
                "semantic_model.read",
                "semantic.query",
                "semantic_model.update",
                "semantic_model.publish",
            }
        ),
        entitlements=frozenset({"semantic_layer"}),
        feature_flags={"semantic_layer": True},
        quotas={},
        correlation_id="semantic-republish-test",
    )


async def _seed(db: AsyncSession, suffix: str) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    """Seed a tenant + active connection + governed dataset with two fields so a
    dimension + measure + metric pass full model validation. Returns
    (user_id, org_id, ws_id, dataset_id, category_field_id)."""
    user = User(
        username=f"sem-{suffix}",
        normalized_username=f"sem-{suffix}",
        email=f"sem-{suffix}@vip.test",
        normalized_email=f"sem-{suffix}@vip.test",
        display_name="Semantic Owner",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    org = Organization(
        name=f"Sem Org {suffix}",
        slug=f"sem-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=user.id,
    )
    db.add(org)
    await db.flush()
    await provision_organization_governance(db, org.id)
    ws = Workspace(
        organization_id=org.id,
        name="Sem WS",
        slug="sem-ws",
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
    ctype = ConnectionType(
        key=f"pg-sem-{suffix}",
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
        source_name="orders",
        source_key="public.orders",
        qualified_name="public.orders",
        display_name="Orders",
        source_object_type="table",
        status="active",
        version=1,
    )
    db.add(dataset)
    await db.flush()
    category = DatasetField(
        organization_id=org.id,
        workspace_id=ws.id,
        dataset_id=dataset.id,
        source_name="category",
        display_name="Category",
        ordinal_position=0,
        physical_data_type="varchar",
        normalized_data_type="string",
        is_nullable=True,
    )
    db.add(category)
    db.add(
        DatasetField(
            organization_id=org.id,
            workspace_id=ws.id,
            dataset_id=dataset.id,
            source_name="amount",
            display_name="Amount",
            ordinal_position=1,
            physical_data_type="numeric",
            normalized_data_type="number",
            is_nullable=True,
        )
    )
    await db.commit()
    return user.id, org.id, ws.id, dataset.id, category.id


async def _build_valid_model(
    db: AsyncSession, ctx: AuthorizationContext, dataset_id: UUID, category_field_id: UUID
) -> UUID:
    """Create a model with one dimension + one metric so it validates cleanly."""
    created = await create_model(
        db,
        ctx,
        SemanticModelCreate(key="orders_model", name="Orders", primary_dataset_id=dataset_id),
    )
    mid = created.id
    await create_dimension(
        db,
        ctx,
        mid,
        DimensionCreate(
            dataset_id=dataset_id,
            field_id=category_field_id,
            key="category",
            name="Category",
            dimension_type="categorical",
        ),
    )
    measure = await create_measure(
        db,
        ctx,
        mid,
        MeasureCreate(
            dataset_id=dataset_id, key="order_count", name="Order Count", aggregation="count"
        ),
    )
    await create_metric(
        db,
        ctx,
        mid,
        MetricCreate(
            key="orders", name="Orders", metric_type="measure", base_measure_id=measure.id
        ),
    )
    return mid


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_model_can_be_published_repeatedly(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id, category_id = await _seed(db, suffix)
            org_ids.append(org_id)
            user_ids.append(user_id)
            ctx = _context(user_id, org_id, ws_id)

            mid = await _build_valid_model(db, ctx, dataset_id, category_id)
            assert (await validate_model(db, ctx, mid)).valid is True

            # Publish version 1.
            pub1 = await publish_model(db, ctx, mid)
            assert pub1.status == "published"
            assert pub1.published_version == 1

            # Editing a published model returns it to draft (Publish re-enabled).
            edited1 = await update_model(
                db, ctx, mid, SemanticModelUpdate(name="Orders v2", version=pub1.version)
            )
            assert edited1.status == "draft"

            # Publish version 2 -> sequential, immutable published pointer.
            pub2 = await publish_model(db, ctx, mid)
            assert pub2.status == "published"
            assert pub2.published_version == 2

            # Edit + publish a third time to confirm the sequence continues.
            edited2 = await update_model(
                db, ctx, mid, SemanticModelUpdate(name="Orders v3", version=pub2.version)
            )
            assert edited2.status == "draft"
            pub3 = await publish_model(db, ctx, mid)
            assert pub3.published_version == 3

            # Exactly three immutable version snapshots persist, numbered 1..3.
            versions = list(
                (
                    await db.scalars(
                        select(SemanticModelVersion)
                        .where(SemanticModelVersion.semantic_model_id == mid)
                        .order_by(SemanticModelVersion.version_number)
                    )
                ).all()
            )
            assert [v.version_number for v in versions] == [1, 2, 3]
            # Each version froze its own definition snapshot (immutable).
            assert all(v.definition for v in versions)

            # A clean published model has no unpublished changes -> cannot republish.
            with pytest.raises(ApplicationError) as no_draft:
                await publish_model(db, ctx, mid)
            assert no_draft.value.code == "SEMANTIC_MODEL_NOT_DRAFT"
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthorized_caller_cannot_publish_semantic_model(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id, category_id = await _seed(db, suffix)
            org_ids.append(org_id)
            user_ids.append(user_id)
            ctx = _context(user_id, org_id, ws_id)
            mid = await _build_valid_model(db, ctx, dataset_id, category_id)

            # An outsider with no membership/ACL on this model cannot publish it.
            outsider = User(
                username=f"outsider-{suffix}",
                normalized_username=f"outsider-{suffix}",
                email=f"outsider-{suffix}@vip.test",
                normalized_email=f"outsider-{suffix}@vip.test",
                display_name="Outsider",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add(outsider)
            await db.flush()
            user_ids.append(outsider.id)
            deny_ctx = AuthorizationContext(
                user_id=outsider.id,
                organization_id=org_id,
                workspace_id=ws_id,
                organization_role_key="organization_member",
                workspace_role_key="workspace_viewer",
                permissions=frozenset(),
                entitlements=frozenset({"semantic_layer"}),
                feature_flags={"semantic_layer": True},
                quotas={},
                correlation_id="semantic-republish-deny",
            )
            await db.commit()

            with pytest.raises(ApplicationError) as denied:
                await publish_model(db, deny_ctx, mid)
            assert denied.value.code in {"NOT_FOUND", "FORBIDDEN"}

            # The model was never published as a side effect of the denied attempt.
            leaked = await db.scalar(
                select(SemanticModelVersion).where(SemanticModelVersion.semantic_model_id == mid)
            )
            assert leaked is None
    finally:
        await _cleanup(database, org_ids, user_ids)


async def _cleanup(database: Database, org_ids: list[UUID], user_ids: list[UUID]) -> None:
    async with database.session_factory() as db:
        for oid in org_ids:
            await db.execute(
                delete(SemanticModelVersion).where(SemanticModelVersion.organization_id == oid)
            )
            await db.execute(delete(SemanticModel).where(SemanticModel.organization_id == oid))
            await db.execute(delete(DatasetField).where(DatasetField.organization_id == oid))
            await db.execute(delete(Dataset).where(Dataset.organization_id == oid))
            await db.execute(delete(Connection).where(Connection.organization_id == oid))
            await db.execute(delete(Organization).where(Organization.id == oid))
        for uid in user_ids:
            await db.execute(delete(User).where(User.id == uid))
        await db.commit()
    await database.engine.dispose()
