"""Integration coverage: Select/Rename schema-aware validation against real
seeded DatasetField records, exercising the actual validate_graph service path.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from vip_api.auth.models import User, UserStatus
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.governance.context import AuthorizationContext
from vip_api.pipelines.schemas import EdgeInput, NodeInput
from vip_api.pipelines.validation import validate_graph
from vip_api.tenancy.models import Organization, OrganizationStatus, Workspace, WorkspaceStatus


def _context(user: UUID, org: UUID, ws: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset({"pipeline.read", "pipeline.update"}),
        entitlements=frozenset({"pipeline_studio"}),
        feature_flags={"pipeline_studio": True},
        quotas={},
        correlation_id="schema-validation-test",
    )


def _codes(issues: list) -> list[str]:
    return [issue.code for issue in issues]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_select_rename_validation_against_real_dataset_fields(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    user_id: UUID | None = None
    ctype_id: UUID | None = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user = User(
                username=f"schema-{suffix}",
                normalized_username=f"schema-{suffix}",
                email=f"schema-{suffix}@vip.test",
                normalized_email=f"schema-{suffix}@vip.test",
                display_name="Schema Test",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.flush()
            user_id = user.id
            org = Organization(
                name="Schema Org",
                slug=f"schema-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="Schema WS",
                slug="schema-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=user.id,
            )
            db.add(ws)
            await db.flush()
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
                source_key="public.customers",
                qualified_name="public.customers",
                display_name="Customers",
                source_object_type="table",
                status="active",
                version=1,
            )
            db.add(dataset)
            await db.flush()
            fields = [
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
                    [
                        ("id", "bigint", "integer", False),
                        ("name", "text", "string", True),
                        ("email", "text", "string", True),
                    ]
                )
            ]
            db.add_all(fields)
            await db.commit()

            context = _context(user.id, org.id, ws.id)
            source = NodeInput(
                key="src",
                type="source-dataset",
                title="Source",
                x=0,
                y=0,
                config={"dataset_id": str(dataset.id)},
            )

            def graph(*extra: NodeInput, edges: list[EdgeInput]):
                return [source, *extra], edges

            # (a) Valid select(keep id,email) -> rename(email->email_address)
            nodes, edges = graph(
                NodeInput(
                    key="sel",
                    type="select-columns",
                    title="Select",
                    x=1,
                    y=0,
                    config={"columns": ["id", "email"]},
                ),
                NodeInput(
                    key="ren",
                    type="rename-columns",
                    title="Rename",
                    x=2,
                    y=0,
                    config={"renames": {"email": "email_address"}},
                ),
                edges=[
                    EdgeInput(key="e1", source="src", target="sel"),
                    EdgeInput(key="e2", source="sel", target="ren"),
                ],
            )
            valid = await validate_graph(db, context, nodes, edges)
            assert "PIPELINE_COLUMN_NOT_FOUND" not in _codes(valid.errors)
            assert "PIPELINE_RENAME_COLLISION" not in _codes(valid.errors)

            # (b) Select a column that does not exist in the real dataset fields
            nodes, edges = graph(
                NodeInput(
                    key="sel",
                    type="select-columns",
                    title="Select",
                    x=1,
                    y=0,
                    config={"columns": ["id", "ghost_column"]},
                ),
                edges=[EdgeInput(key="e1", source="src", target="sel")],
            )
            missing = await validate_graph(db, context, nodes, edges)
            assert "PIPELINE_COLUMN_NOT_FOUND" in _codes(missing.errors)
            assert missing.valid is False

            # (c) Rename collision with an untouched real column
            nodes, edges = graph(
                NodeInput(
                    key="ren",
                    type="rename-columns",
                    title="Rename",
                    x=1,
                    y=0,
                    config={"renames": {"name": "email"}},
                ),
                edges=[EdgeInput(key="e1", source="src", target="ren")],
            )
            collision = await validate_graph(db, context, nodes, edges)
            assert "PIPELINE_RENAME_COLLISION" in _codes(collision.errors)

            # (d) Invalid rename target name
            nodes, edges = graph(
                NodeInput(
                    key="ren",
                    type="rename-columns",
                    title="Rename",
                    x=1,
                    y=0,
                    config={"renames": {"name": "bad name!"}},
                ),
                edges=[EdgeInput(key="e1", source="src", target="ren")],
            )
            invalid = await validate_graph(db, context, nodes, edges)
            assert "PIPELINE_INVALID_COLUMN_NAME" in _codes(invalid.errors)
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                # FK-safe order: fields -> datasets -> connections -> org.
                await db.execute(
                    delete(DatasetField).where(DatasetField.organization_id == org_id)
                )
                await db.execute(delete(Dataset).where(Dataset.organization_id == org_id))
                await db.execute(delete(Connection).where(Connection.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
            if ctype_id is not None:
                await db.execute(delete(ConnectionType).where(ConnectionType.id == ctype_id))
            if user_id is not None:
                await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await database.dispose()
