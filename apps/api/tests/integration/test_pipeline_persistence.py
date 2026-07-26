"""B7 tenant isolation, persistence, and optimistic concurrency integration coverage."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, text

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance.context import AuthorizationContext
from vip_api.pipelines.schemas import EdgeInput, NodeInput, PipelineCreate, PipelineEditorSave
from vip_api.pipelines.services import create_pipeline, get_editor, list_pipelines, save_editor
from vip_api.tenancy.models import Organization, OrganizationStatus, Workspace, WorkspaceStatus


def context(user: UUID, organization: UUID, workspace: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=organization,
        workspace_id=workspace,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset({"pipeline.read", "pipeline.create", "pipeline.update"}),
        entitlements=frozenset({"pipeline_studio"}),
        feature_flags={"pipeline_studio": True},
        quotas={},
        correlation_id="pipeline-test",
    )


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.asyncio
async def test_pipeline_tables_tenant_isolation_and_conflict(settings: Settings) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            tables = set(
                (
                    await db.scalars(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema='public' AND table_name LIKE 'pipeline%'"
                        )
                    )
                ).all()
            )
            assert {
                "pipelines",
                "pipeline_nodes",
                "pipeline_edges",
                "pipeline_versions",
                "pipeline_runs",
                "pipeline_run_attempts",
                "pipeline_node_runs",
                "pipeline_run_logs",
                "pipeline_artifacts",
                "pipeline_outbox_events",
            } <= tables
            user = User(
                email=f"pipeline-{uuid4().hex}@vip.test",
                normalized_email=f"pipeline-{uuid4().hex}@vip.test",
                display_name="Pipeline Test",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.flush()
            alpha = Organization(
                name="Pipeline Alpha",
                slug=f"pipe-alpha-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            beta = Organization(
                name="Pipeline Beta",
                slug=f"pipe-beta-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            db.add_all((alpha, beta))
            await db.flush()
            alpha_ws = Workspace(
                organization_id=alpha.id,
                name="Alpha",
                slug="alpha",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=user.id,
            )
            beta_ws = Workspace(
                organization_id=beta.id,
                name="Beta",
                slug="beta",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=user.id,
            )
            db.add_all((alpha_ws, beta_ws))
            await db.commit()
            alpha_context, beta_context = (
                context(user.id, alpha.id, alpha_ws.id),
                context(user.id, beta.id, beta_ws.id),
            )
            created = await create_pipeline(
                db, alpha_context, PipelineCreate(name="Tenant pipeline")
            )
            assert len((await list_pipelines(db, alpha_context)).items) == 1
            assert (await list_pipelines(db, beta_context)).items == []
            payload = PipelineEditorSave(
                name="Saved pipeline",
                expected_version=created.pipeline.row_version,
                canvas={"x": 120, "y": 80, "scale": 1.25, "snapGrid": True},
                nodes=[
                    NodeInput(
                        key="source",
                        type="source-dataset",
                        title="Source",
                        x=10,
                        y=20,
                        config={"dataset_id": str(uuid4())},
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
            saved = await save_editor(db, alpha_context, created.pipeline.id, payload)
            assert saved.pipeline.row_version == 2
            reloaded = await get_editor(db, alpha_context, created.pipeline.id)
            assert len(reloaded.edges) == 1
            assert reloaded.edges[0].source == "source"
            assert reloaded.edges[0].target == "export"
            assert reloaded.canvas["scale"] == 1.25
            with pytest.raises(ApplicationError) as conflict:
                await save_editor(db, alpha_context, created.pipeline.id, payload)
            assert conflict.value.code == "VERSION_CONFLICT"
            await db.execute(delete(Organization).where(Organization.id.in_([alpha.id, beta.id])))
            await db.execute(delete(User).where(User.id == user.id))
            await db.commit()
    finally:
        await database.dispose()
