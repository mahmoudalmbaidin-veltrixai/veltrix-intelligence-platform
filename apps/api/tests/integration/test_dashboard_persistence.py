"""Dashboard migration, PostgreSQL persistence, and tenant isolation integration coverage."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.dashboards.models import Dashboard, DashboardShare, DashboardVersion
from vip_api.dashboards.schemas import DashboardCreate, EditorSave
from vip_api.dashboards.services import (
    create_dashboard,
    editor,
    get_dashboard,
    list_dashboards,
    save_editor,
    viewer,
)
from vip_api.database.session import Database
from vip_api.governance.context import AuthorizationContext
from vip_api.tenancy.models import Organization, OrganizationStatus, Workspace, WorkspaceStatus


def context(user_id: UUID, organization_id: UUID, workspace_id: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset({"dashboard.read", "dashboard.create", "dashboard.update"}),
        entitlements=frozenset({"dashboard_studio"}),
        feature_flags={"dashboard_studio": True},
        quotas={},
        correlation_id="dashboard-test",
    )


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.asyncio
async def test_dashboard_tables_persist_and_queries_are_tenant_qualified(
    settings: Settings,
) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            names = set(
                (
                    await db.scalars(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema='public' AND table_name LIKE 'dashboard%'"
                        )
                    )
                ).all()
            )
            assert {
                "dashboards",
                "dashboard_pages",
                "dashboard_widgets",
                "dashboard_filters",
                "dashboard_versions",
                "dashboard_shares",
                "dashboard_snapshots",
                "dashboard_exports",
                "dashboard_delivery_schedules",
                "dashboard_delivery_runs",
            } <= names
            await db.execute(delete(Organization))
            await db.execute(delete(User))
            user = User(
                email="dashboard-admin@vip.test",
                normalized_email="dashboard-admin@vip.test",
                display_name="Dashboard Admin",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            shared_user = User(
                email="dashboard-shared@vip.test",
                normalized_email="dashboard-shared@vip.test",
                display_name="Dashboard Shared User",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add_all((user, shared_user))
            await db.flush()
            alpha = Organization(
                name="Dashboard Alpha",
                slug=f"dash-alpha-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            beta = Organization(
                name="Dashboard Beta",
                slug=f"dash-beta-{uuid4().hex[:8]}",
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
            user_id, shared_user_id = user.id, shared_user.id
            alpha_id, beta_id = alpha.id, beta.id
            alpha_ws_id, beta_ws_id = alpha_ws.id, beta_ws.id
            alpha_context = context(user_id, alpha_id, alpha_ws_id)
            created = await create_dashboard(
                db, alpha_context, DashboardCreate(name="Persisted Dashboard")
            )
            assert created.page_count == 1
            with pytest.raises(ApplicationError) as duplicate_slug:
                await create_dashboard(
                    db, alpha_context, DashboardCreate(name="Persisted Dashboard")
                )
            assert duplicate_slug.value.code == "DASHBOARD_SLUG_CONFLICT"
            assert duplicate_slug.value.status_code == 409
            assert [item.id for item in await list_dashboards(db, alpha_context)] == [created.id]
            beta_context = context(user_id, beta_id, beta_ws_id)
            assert await list_dashboards(db, beta_context) == []
            with pytest.raises(ApplicationError) as hidden:
                await get_dashboard(db, beta_context, created.id)
            assert hidden.value.code == "DASHBOARD_NOT_FOUND"
            assert (
                await db.scalar(select(Dashboard.name).where(Dashboard.id == created.id))
                == "Persisted Dashboard"
            )
            shared_context = AuthorizationContext(
                user_id=shared_user_id,
                organization_id=alpha_id,
                workspace_id=alpha_ws_id,
                organization_role_key="organization_member",
                workspace_role_key=None,
                permissions=frozenset(),
                entitlements=frozenset({"dashboard_studio"}),
                feature_flags={"dashboard_studio": True},
                quotas={},
                correlation_id="dashboard-direct-share-test",
            )
            share = DashboardShare(
                organization_id=alpha_id,
                workspace_id=alpha_ws_id,
                dashboard_id=created.id,
                principal_type="user",
                principal_id=shared_user_id,
                permission_level="view",
                created_by_user_id=user_id,
            )
            db.add(share)
            await db.commit()
            with pytest.raises(ApplicationError) as view_only_editor:
                await editor(db, shared_context, created.id)
            assert view_only_editor.value.code == "DASHBOARD_ACCESS_DENIED"
            share.permission_level = "edit"
            await db.commit()
            shared_editor = await editor(db, shared_context, created.id)
            saved = await save_editor(
                db,
                shared_context,
                created.id,
                EditorSave(
                    expected_version=shared_editor.version,
                    name="Shared editor update",
                    pages=shared_editor.pages,
                    filters=shared_editor.filters,
                ),
            )
            assert saved.dashboard.name == "Shared editor update"
            version = DashboardVersion(
                organization_id=alpha_id,
                workspace_id=alpha_ws_id,
                dashboard_id=created.id,
                version_number=1,
                version_type="published",
                snapshot={"schema_version": 1, "pages": []},
                created_by_user_id=user_id,
                change_summary="Direct-share access test",
            )
            db.add(version)
            await db.flush()
            dashboard = await get_dashboard(db, alpha_context, created.id)
            dashboard.published_version_id = version.id
            dashboard.status = "published"
            await db.commit()
            published = await viewer(db, shared_context, created.id)
            assert published["version"] == 1
            assert published["access"] == {
                "can_view": True,
                "can_interact": True,
                "can_edit": True,
                "can_publish": False,
                "can_manage_sharing": False,
                "can_snapshot": False,
            }
            # This suite shares one integration database. Remove the tenant aggregate
            # we created so later destructive-reset tests are not coupled to test order.
            await db.execute(delete(Organization).where(Organization.id.in_([alpha_id, beta_id])))
            await db.execute(delete(User).where(User.id.in_([user_id, shared_user_id])))
            await db.commit()
    finally:
        await database.dispose()
