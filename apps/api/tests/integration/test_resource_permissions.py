"""End-to-end resource-permission engine, groups, and dashboard overlay tests.

Drives the real group and resource-access services against vip_test: group
membership, user/group grants, permission inheritance, explicit-deny precedence,
the dashboard ``_access`` overlay, and permission simulation for another user.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.dashboards.models import Dashboard
from vip_api.dashboards.schemas import DashboardCreate
from vip_api.dashboards.services import _access as dashboard_access
from vip_api.dashboards.services import create_dashboard
from vip_api.database.session import Database
from vip_api.governance import group_service, resource_access_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.seed import seed_system_governance
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)


def _admin_context(user: UUID, org: UUID, ws: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset(
            {
                "dashboard.read",
                "dashboard.create",
                "dashboard.update",
                "dashboard.share",
                "resource.permissions.read",
                "resource.permissions.manage",
                "group.read",
                "group.create",
                "group.members.manage",
            }
        ),
        entitlements=frozenset({"dashboard_studio"}),
        feature_flags={"dashboard_studio": True},
        quotas={},
        correlation_id="resource-perms-test",
    )


def _viewer_context(user: UUID, org: UUID, ws: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_member",
        workspace_role_key="viewer",
        permissions=frozenset({"dashboard.read", "resource.permissions.read"}),
        entitlements=frozenset({"dashboard_studio"}),
        feature_flags={"dashboard_studio": True},
        quotas={},
        correlation_id="resource-perms-test",
    )


async def _role_id(db: AsyncSession, key: str) -> UUID:
    from vip_api.governance.services import get_role

    scope = "organization" if key.startswith("organization") else "workspace"
    role = await get_role(db, key, scope)
    return role.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resource_permission_engine_end_to_end(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    admin_id: UUID | None = None
    member_id: UUID | None = None
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            suffix = uuid4().hex[:8]
            admin = User(
                username=f"perm-admin-{suffix}",
                normalized_username=f"perm-admin-{suffix}",
                email=f"perm-admin-{suffix}@vip.test",
                normalized_email=f"perm-admin-{suffix}@vip.test",
                display_name="Perm Admin",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            member = User(
                username=f"perm-member-{suffix}",
                normalized_username=f"perm-member-{suffix}",
                email=f"perm-member-{suffix}@vip.test",
                normalized_email=f"perm-member-{suffix}@vip.test",
                display_name="Perm Member",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add_all((admin, member))
            await db.flush()
            admin_id, member_id = admin.id, member.id
            org = Organization(
                name="Perm Org",
                slug=f"perm-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=admin.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="Perm WS",
                slug="perm-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=admin.id,
            )
            db.add(ws)
            await db.flush()

            org_admin_role = await _role_id(db, "organization_admin")
            org_member_role = await _role_id(db, "organization_member")
            ws_admin_role = await _role_id(db, "workspace_admin")
            viewer_role = await _role_id(db, "viewer")
            db.add_all(
                (
                    OrganizationMembership(
                        organization_id=org.id,
                        user_id=admin.id,
                        role_id=org_admin_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                    OrganizationMembership(
                        organization_id=org.id,
                        user_id=member.id,
                        role_id=org_member_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                    WorkspaceMembership(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        user_id=admin.id,
                        role_id=ws_admin_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                    WorkspaceMembership(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        user_id=member.id,
                        role_id=viewer_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                )
            )
            await db.commit()

            admin_ctx = _admin_context(admin.id, org.id, ws.id)
            viewer_ctx = _viewer_context(member.id, org.id, ws.id)

            board = await create_dashboard(db, admin_ctx, DashboardCreate(name="Perm Board"))

            # 1. Direct user grant -> effective view.
            await resource_access_service.grant_resource_access(
                db,
                admin_ctx,
                resource_type="dashboard",
                resource_id=board.id,
                subject_type="user",
                subject_id=member.id,
                access_level="view",
            )
            eff = await resource_access_service.effective_access(
                db,
                resource_type="dashboard",
                resource_id=board.id,
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=member.id,
                role_permissions=frozenset(),
            )
            assert eff.level == "view"
            assert eff.allowed_levels == ["view"]

            # 2. Group grant -> inheritance raises to edit.
            group = await group_service.create_group(db, admin_ctx, name="Analysts")
            await group_service.add_member(db, admin_ctx, group.id, member.id)
            await resource_access_service.grant_resource_access(
                db,
                admin_ctx,
                resource_type="dashboard",
                resource_id=board.id,
                subject_type="group",
                subject_id=group.id,
                access_level="edit",
            )
            eff = await resource_access_service.effective_access(
                db,
                resource_type="dashboard",
                resource_id=board.id,
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=member.id,
                role_permissions=frozenset(),
            )
            assert eff.level == "edit"
            assert eff.allowed_levels == ["view", "interact", "edit"]

            # 3. Dashboard `_access` overlay reflects the group edit grant.
            board_row = await db.get(Dashboard, board.id)
            assert board_row is not None
            access = await dashboard_access(db, viewer_ctx, board_row)
            assert access["can_view"] is True
            assert access["can_edit"] is True

            # 4. Explicit deny overrides inherited access.
            await resource_access_service.grant_resource_access(
                db,
                admin_ctx,
                resource_type="dashboard",
                resource_id=board.id,
                subject_type="user",
                subject_id=member.id,
                access_level="view",
                effect="deny",
            )
            eff = await resource_access_service.effective_access(
                db,
                resource_type="dashboard",
                resource_id=board.id,
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=member.id,
                role_permissions=frozenset(),
            )
            assert eff.level is None
            assert eff.reason == "EXPLICIT_DENY"
            access = await dashboard_access(db, viewer_ctx, board_row)
            assert access["can_view"] is False
            assert access["can_edit"] is False

            # 5. Simulation resolves the member's own role-derived + granted access.
            entries = await resource_access_service.list_resource_entries(
                db, admin_ctx, resource_type="dashboard", resource_id=board.id
            )
            deny_entry = next(entry for entry in entries if entry.effect == "deny")
            await resource_access_service.revoke_resource_access(
                db,
                admin_ctx,
                resource_type="dashboard",
                resource_id=board.id,
                entry_id=deny_entry.id,
            )
            simulated = await resource_access_service.effective_access(
                db,
                resource_type="dashboard",
                resource_id=board.id,
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=member.id,
                role_permissions=None,
            )
            assert simulated.level == "edit"
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                await db.execute(delete(Organization).where(Organization.id == org_id))
            for uid in (admin_id, member_id):
                if uid is not None:
                    await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.engine.dispose()
