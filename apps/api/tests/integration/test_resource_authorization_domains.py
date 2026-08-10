"""Integration: Dataset / Connection / Semantic resource authorization.

Proves — against the real services and ``vip_test`` — that all three of the
remaining resource domains use the centralized evaluator for elevation, deny,
expiration, collection visibility, sharing authority, and (for semantic) the
execution chokepoint. A resource ACL grant authorizes the capability WITHOUT any
broad ``dataset.* / connection.* / semantic_model.*`` workspace permission; an
explicit deny blocks and hides; a stranger is a non-disclosing 404; and a user
can never EXECUTE a semantic model they cannot access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, select

from vip_api.auth.models import User, UserStatus
from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.services import get_connection, list_connections
from vip_api.core.config import Settings, get_settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset, DatasetQualityEvaluation
from vip_api.datasets.services import get_dataset, list_datasets
from vip_api.governance import resource_access_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Group, GroupMembership, ResourceAccessEntry, Role
from vip_api.pipelines.schemas import EdgeInput, NodeInput, PipelineCreate
from vip_api.pipelines.services import create_pipeline
from vip_api.semantic.models import SemanticModel
from vip_api.semantic.query import execute_query
from vip_api.semantic.schemas import SemanticQueryRequest
from vip_api.semantic.services import list_models
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
        entitlements=frozenset(
            {"dataset_studio", "connection_studio", "semantic_layer", "data_quality"}
        ),
        feature_flags={},
        quotas={},
        correlation_id="resource-auth-test",
    )


def _acl(
    org: UUID,
    ws: UUID,
    resource_type: str,
    resource_id: UUID,
    subject_id: UUID,
    level: str,
    *,
    subject_type: str = "user",
    effect: str = "allow",
    expires_at: datetime | None = None,
) -> ResourceAccessEntry:
    return ResourceAccessEntry(
        organization_id=org,
        workspace_id=ws,
        resource_type=resource_type,
        resource_id=resource_id,
        subject_type=subject_type,
        subject_id=subject_id,
        access_level=level,
        effect=effect,
        expires_at=expires_at,
    )


def _user(suffix: str, tag: str) -> User:
    return User(
        username=f"rad-{tag}-{suffix}",
        normalized_username=f"rad-{tag}-{suffix}",
        email=f"rad-{tag}-{suffix}@vip.test",
        normalized_email=f"rad-{tag}-{suffix}@vip.test",
        display_name=tag.title(),
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resource_authorization_across_domains(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    ctype_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
            assert role_id is not None

            owner = _user(suffix, "owner")  # broad dataset/connection/semantic role
            viewer = _user(suffix, "viewer")  # ACL-only grants
            denied = _user(suffix, "denied")  # explicit deny
            stranger = _user(suffix, "stranger")  # no grant
            group_member = _user(suffix, "group")  # group grant
            everyone = [owner, viewer, denied, stranger, group_member]
            db.add_all(everyone)
            await db.flush()
            user_ids = [u.id for u in everyone]

            org = Organization(
                name="RAD Org",
                slug=f"rad-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=owner.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="RAD WS",
                slug="rad-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=owner.id,
            )
            db.add(ws)
            await db.flush()
            db.add_all(
                OrganizationMembership(
                    organization_id=org.id,
                    user_id=uid,
                    role_id=role_id,
                    status=MembershipStatus.ACTIVE,
                )
                for uid in user_ids
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
            ctype_id = ctype.id
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
                source_key=f"public.customers.{suffix}",
                qualified_name="public.customers",
                display_name="Customers",
                source_object_type="table",
                status="active",
                owner_user_id=owner.id,
                version=1,
            )
            other_dataset = Dataset(
                organization_id=org.id,
                workspace_id=ws.id,
                connection_id=connection.id,
                dataset_type="table",
                source_schema="public",
                source_name="orders",
                source_key=f"public.orders.{suffix}",
                qualified_name="public.orders",
                display_name="Orders",
                source_object_type="table",
                status="active",
                owner_user_id=owner.id,
                version=1,
            )
            db.add_all((dataset, other_dataset))
            await db.flush()
            db.add(
                DatasetQualityEvaluation(
                    organization_id=org.id,
                    workspace_id=ws.id,
                    dataset_id=dataset.id,
                    status="completed",
                    score=96,
                    total_rules=3,
                    passing=3,
                    completed_at=datetime.now(UTC),
                )
            )
            model = SemanticModel(
                organization_id=org.id,
                workspace_id=ws.id,
                key="sales",
                name="Sales",
                primary_dataset_id=dataset.id,
                status="published",
                created_by_user_id=owner.id,
            )
            db.add(model)
            await db.flush()

            devs = Group(
                organization_id=org.id, workspace_id=ws.id, name="Devs", slug=f"rad-devs-{suffix}"
            )
            db.add(devs)
            await db.flush()
            db.add(GroupMembership(group_id=devs.id, user_id=group_member.id))

            # Grants (no broad permissions for the grantees).
            db.add_all(
                (
                    _acl(org.id, ws.id, "dataset", dataset.id, viewer.id, "query"),
                    _acl(org.id, ws.id, "dataset", dataset.id, denied.id, "query"),
                    _acl(org.id, ws.id, "dataset", dataset.id, denied.id, "query", effect="deny"),
                    # A broad-role owner is still subject to an explicit resource
                    # deny; collection visibility must preserve that precedence.
                    _acl(
                        org.id,
                        ws.id,
                        "dataset",
                        other_dataset.id,
                        owner.id,
                        "query",
                        effect="deny",
                    ),
                    _acl(
                        org.id, ws.id, "dataset", dataset.id, devs.id, "edit", subject_type="group"
                    ),
                    _acl(org.id, ws.id, "connection", connection.id, viewer.id, "use"),
                    _acl(org.id, ws.id, "semantic_model", model.id, viewer.id, "query"),
                    _acl(
                        org.id, ws.id, "semantic_model", model.id, denied.id, "view", effect="deny"
                    ),
                )
            )
            await db.commit()

            owner_ctx = _ctx(
                owner.id,
                org.id,
                ws.id,
                frozenset({"dataset.read", "connection.read", "semantic_model.read"}),
            )
            viewer_ctx = _ctx(viewer.id, org.id, ws.id)
            denied_ctx = _ctx(denied.id, org.id, ws.id)
            stranger_ctx = _ctx(stranger.id, org.id, ws.id)
            group_ctx = _ctx(group_member.id, org.id, ws.id)

            # ---- DATASET ----------------------------------------------------
            # Elevation: a query ACL opens the dataset without dataset.read.
            got = await get_dataset(db, viewer_ctx, dataset.id)
            assert got.id == dataset.id
            assert got.access is not None
            assert got.access.allowed_levels == ["query"]
            assert got.access.can_manage_access is False
            # Isolation: stranger gets a non-disclosing 404.
            with pytest.raises(ApplicationError) as ds_stranger:
                await get_dataset(db, stranger_ctx, dataset.id)
            assert ds_stranger.value.status_code == 404
            # Explicit deny -> 403.
            with pytest.raises(ApplicationError) as ds_deny:
                await get_dataset(db, denied_ctx, dataset.id)
            assert ds_deny.value.status_code == 403
            assert ds_deny.value.code == "RESOURCE_ACCESS_DENIED"
            # Group grant elevates (edit implies query).
            assert (await get_dataset(db, group_ctx, dataset.id)).id == dataset.id
            # Collection visibility: viewer sees only the granted dataset.
            query_count = 0

            def count_query(*_args: object) -> None:
                nonlocal query_count
                query_count += 1

            event.listen(database.engine.sync_engine, "before_cursor_execute", count_query)
            try:
                viewer_list = await list_datasets(
                    db, viewer_ctx, page=1, page_size=50, search=None, status=None
                )
            finally:
                event.remove(database.engine.sync_engine, "before_cursor_execute", count_query)
            assert {row.id for row in viewer_list.items} == {dataset.id}
            assert viewer_list.total == 1
            assert viewer_list.items[0].quality_score == 96
            assert query_count == 3  # group visibility + count + one projected page
            # Deny hides it entirely from the list.
            denied_list = await list_datasets(
                db, denied_ctx, page=1, page_size=50, search=None, status=None
            )
            assert denied_list.total == 0
            # Explicit deny still hides a resource from a broad-role owner.
            owner_list = await list_datasets(
                db, owner_ctx, page=1, page_size=50, search=None, status=None
            )
            assert dataset.id in {row.id for row in owner_list.items}
            assert other_dataset.id not in {row.id for row in owner_list.items}

            source_payload = PipelineCreate(
                name="Authorized source",
                nodes=[
                    NodeInput(
                        key="source",
                        type="source-dataset",
                        title="Source",
                        x=0,
                        y=0,
                        config={"dataset_id": str(dataset.id), "dataset_version": 1},
                    ),
                    NodeInput(
                        key="export",
                        type="file-export",
                        title="Export",
                        x=300,
                        y=0,
                        config={"format": "csv", "filename": "result.csv"},
                    ),
                ],
                edges=[EdgeInput(key="flow", source="source", target="export")],
            )
            # A current ACL grant permits the governed source. Removing access
            # or deleting the dataset is rejected deterministically at save.
            allowed_pipeline = await create_pipeline(db, viewer_ctx, source_payload)
            persisted_source = next(node for node in allowed_pipeline.nodes if node.key == "source")
            assert persisted_source.config["dataset_id"] == str(dataset.id)
            with pytest.raises(ApplicationError) as removed_permission:
                await create_pipeline(db, denied_ctx, source_payload)
            assert removed_permission.value.code == "PIPELINE_SOURCE_UNAVAILABLE"
            deleted_payload = source_payload.model_copy(deep=True)
            deleted_payload.nodes[0].config["dataset_id"] = str(uuid4())
            with pytest.raises(ApplicationError) as deleted_source:
                await create_pipeline(db, viewer_ctx, deleted_payload)
            assert deleted_source.value.code == "PIPELINE_SOURCE_UNAVAILABLE"

            # ---- CONNECTION -------------------------------------------------
            conn = await get_connection(db, viewer_ctx, connection.id)
            assert conn.id == connection.id
            assert conn.access is not None and conn.access.allowed_levels == ["use"]
            # Secrets are never present on the response.
            assert conn.credentials_configured is False
            with pytest.raises(ApplicationError) as conn_stranger:
                await get_connection(db, stranger_ctx, connection.id)
            assert conn_stranger.value.status_code == 404
            conn_list = await list_connections(db, viewer_ctx, page=1, page_size=50)
            assert {row.id for row in conn_list.items} == {connection.id}
            assert (await list_connections(db, stranger_ctx, page=1, page_size=50)).total == 0

            # ---- SEMANTIC ---------------------------------------------------
            # Collection visibility: viewer sees only the granted model.
            models = await list_models(db, viewer_ctx)
            assert {m.id for m in models} == {model.id}
            assert await list_models(db, stranger_ctx) == []

            # EXECUTION CHOKEPOINT: a user without model access can never execute.
            request = SemanticQueryRequest(semantic_model_id=model.id, metrics=["revenue"])
            provider = MagicMock()
            with pytest.raises(ApplicationError) as exec_stranger:
                await execute_query(db, stranger_ctx, request, get_settings(), provider)
            assert exec_stranger.value.status_code == 404
            with pytest.raises(ApplicationError) as exec_deny:
                await execute_query(db, denied_ctx, request, get_settings(), provider)
            assert exec_deny.value.status_code == 403
            assert exec_deny.value.code == "RESOURCE_ACCESS_DENIED"
            # The provider is never touched on the denied paths (blocked before data).
            provider.read_secret.assert_not_called()

            # ---- SHARING AUTHORITY -----------------------------------------
            # The broad-role owner (dataset.update? no) — verify manage authority via
            # the manage permission on a fresh admin-like context.
            admin_ctx = _ctx(owner.id, org.id, ws.id, frozenset({"dataset.update"}))
            assert (
                await resource_access_service.can_manage_access(
                    db, admin_ctx, resource_type="dataset", resource_id=dataset.id
                )
                is True
            )
            assert (
                await resource_access_service.can_manage_access(
                    db, viewer_ctx, resource_type="dataset", resource_id=dataset.id
                )
                is False
            )

            # ---- EXPIRATION -------------------------------------------------
            db.add(
                _acl(
                    org.id,
                    ws.id,
                    "dataset",
                    other_dataset.id,
                    viewer.id,
                    "query",
                    expires_at=datetime.now(UTC) - timedelta(hours=1),
                )
            )
            await db.commit()
            with pytest.raises(ApplicationError):
                await get_dataset(db, viewer_ctx, other_dataset.id)
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                await db.execute(
                    delete(ResourceAccessEntry).where(ResourceAccessEntry.organization_id == org_id)
                )
                await db.execute(
                    delete(GroupMembership).where(
                        GroupMembership.group_id.in_(
                            select(Group.id).where(Group.organization_id == org_id)
                        )
                    )
                )
                await db.execute(delete(Group).where(Group.organization_id == org_id))
                await db.execute(
                    delete(SemanticModel).where(SemanticModel.organization_id == org_id)
                )
                await db.execute(delete(Dataset).where(Dataset.organization_id == org_id))
                await db.execute(delete(Connection).where(Connection.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
            if ctype_id is not None:
                await db.execute(delete(ConnectionType).where(ConnectionType.id == ctype_id))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.dispose()
