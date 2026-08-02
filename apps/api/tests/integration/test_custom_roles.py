"""End-to-end custom roles, assignments, enforcement, and isolation (Phase B/C/K).

Drives the real role and assignment services against vip_test: create/update/
clone/archive/delete, system-role protection, the privilege ceiling that blocks
self-escalation, direct + group role permission resolution feeding the request
context, bulk assignment per-item outcomes, and cross-tenant isolation.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance import group_service, role_assignment_service, role_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.seed import seed_system_governance
from vip_api.governance.services import _permission_keys, assigned_role_ids_for
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)

ADMIN_PERMISSIONS = frozenset(
    {
        "role.read",
        "role.create",
        "role.update",
        "role.delete",
        "role.assign",
        "group.read",
        "group.create",
        "group.members.manage",
        "dashboard.read",
        "dashboard.update",
        "dashboard.share",
    }
)


def _admin_context(user: UUID, org: UUID, ws: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=ADMIN_PERMISSIONS,
        entitlements=frozenset(),
        feature_flags={},
        quotas={},
        correlation_id="custom-roles-test",
    )


async def _role_id(db: AsyncSession, key: str) -> UUID:
    from vip_api.governance.services import get_role

    scope = "organization" if key.startswith("organization") else "workspace"
    role = await get_role(db, key, scope)
    return role.id


async def _seed_tenant(db: AsyncSession, suffix: str) -> tuple[Organization, Workspace, User, User]:
    admin = User(
        username=f"role-admin-{suffix}",
        normalized_username=f"role-admin-{suffix}",
        email=f"role-admin-{suffix}@vip.test",
        normalized_email=f"role-admin-{suffix}@vip.test",
        display_name="Role Admin",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    member = User(
        username=f"role-member-{suffix}",
        normalized_username=f"role-member-{suffix}",
        email=f"role-member-{suffix}@vip.test",
        normalized_email=f"role-member-{suffix}@vip.test",
        display_name="Role Member",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add_all((admin, member))
    await db.flush()
    org = Organization(
        name=f"Role Org {suffix}",
        slug=f"role-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=admin.id,
    )
    db.add(org)
    await db.flush()
    ws = Workspace(
        organization_id=org.id,
        name="Role WS",
        slug="role-ws",
        status=WorkspaceStatus.ACTIVE,
        is_default=True,
        created_by_user_id=admin.id,
    )
    db.add(ws)
    await db.flush()
    org_admin_role = await _role_id(db, "organization_admin")
    org_member_role = await _role_id(db, "organization_member")
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
        )
    )
    await db.commit()
    return org, ws, admin, member


@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_role_lifecycle_and_enforcement(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            suffix = uuid4().hex[:8]
            org, ws, admin, member = await _seed_tenant(db, suffix)
            org_ids.append(org.id)
            user_ids.extend([admin.id, member.id])
            ctx = _admin_context(admin.id, org.id, ws.id)

            # Create a custom organization role from catalog permissions.
            role = await role_service.create_role(
                db,
                ctx,
                name="Report Curator",
                description="Curates dashboards",
                scope="organization",
                permission_keys={"dashboard.read", "dashboard.update"},
            )
            assert role.is_system is False
            assert role.is_editable is True
            assert role.organization_id == org.id

            # Duplicate name is rejected.
            with pytest.raises(ApplicationError) as dup:
                await role_service.create_role(
                    db,
                    ctx,
                    name="Report Curator",
                    description="",
                    scope="organization",
                    permission_keys={"dashboard.read"},
                )
            assert dup.value.code == "ROLE_NAME_TAKEN"

            # Privilege ceiling: cannot grant a permission the admin does not hold.
            with pytest.raises(ApplicationError) as esc:
                await role_service.create_role(
                    db,
                    ctx,
                    name="Escalator",
                    description="",
                    scope="organization",
                    permission_keys={"pipeline.delete"},
                )
            assert esc.value.code == "PERMISSION_ESCALATION_DENIED"

            # System roles are protected.
            system_role_id = await _role_id(db, "organization_admin")
            with pytest.raises(ApplicationError) as prot:
                await role_service.update_role(
                    db, ctx, system_role_id, expected_version=1, name="Hacked"
                )
            assert prot.value.code == "ROLE_PROTECTED"

            # Assign the custom role to the member -> permissions resolve into context.
            await role_assignment_service.assign_user_role(
                db, ctx, role_id=role.id, user_id=member.id
            )
            assigned = await assigned_role_ids_for(
                db, organization_id=org.id, workspace_id=ws.id, user_id=member.id
            )
            assert role.id in assigned
            keys = await _permission_keys(db, assigned)
            assert "dashboard.update" in keys

            # Group role assignment inheritance.
            group = await group_service.create_group(db, ctx, name="Curators")
            await group_service.add_member(db, ctx, group.id, member.id)
            role2 = await role_service.create_role(
                db,
                ctx,
                name="Sharer",
                description="",
                scope="organization",
                permission_keys={"dashboard.share"},
            )
            await role_assignment_service.assign_group_role(
                db, ctx, role_id=role2.id, group_id=group.id
            )
            assigned = await assigned_role_ids_for(
                db, organization_id=org.id, workspace_id=ws.id, user_id=member.id
            )
            keys = await _permission_keys(db, assigned)
            assert {"dashboard.update", "dashboard.share"} <= keys

            # Clone copies permissions under a new name.
            clone = await role_service.clone_role(db, ctx, role.id, name="Report Curator Copy")
            clone_view = await role_service.role_view(db, clone)
            assert set(clone_view.permission_keys) == {"dashboard.read", "dashboard.update"}

            # Archive removes the role's grants from the resolved permission set.
            await role_service.set_archived(
                db, ctx, role.id, expected_version=role.row_version, archived=True
            )
            assigned = await assigned_role_ids_for(
                db, organization_id=org.id, workspace_id=ws.id, user_id=member.id
            )
            assert role.id not in assigned

            # Bulk assignment returns per-item outcomes (valid user + bogus subject).
            bogus = uuid4()
            results = await role_assignment_service.bulk_assign_role(
                db, ctx, role_id=role2.id, user_ids=[admin.id, bogus], group_ids=[]
            )
            outcomes = {r.subject_id: r.ok for r in results}
            assert outcomes[admin.id] is True
            assert outcomes[bogus] is False
    finally:
        async with database.session_factory() as db:
            for oid in org_ids:
                await db.execute(delete(Organization).where(Organization.id == oid))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_role_tenant_isolation(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            suffix_a = uuid4().hex[:8]
            suffix_b = uuid4().hex[:8]
            org_a, ws_a, admin_a, member_a = await _seed_tenant(db, suffix_a)
            org_b, ws_b, admin_b, _member_b = await _seed_tenant(db, suffix_b)
            org_ids.extend([org_a.id, org_b.id])
            user_ids.extend([admin_a.id, member_a.id, admin_b.id, _member_b.id])
            ctx_a = _admin_context(admin_a.id, org_a.id, ws_a.id)
            ctx_b = _admin_context(admin_b.id, org_b.id, ws_b.id)

            role_a = await role_service.create_role(
                db,
                ctx_a,
                name="Org A Role",
                description="",
                scope="organization",
                permission_keys={"dashboard.read"},
            )
            # Org B cannot see or fetch Org A's role.
            visible_b = await role_service.list_roles(db, ctx_b, include_system=False)
            assert role_a.id not in {r.id for r in visible_b}
            with pytest.raises(ApplicationError) as nf:
                await role_service.get_role(db, ctx_b, role_a.id)
            assert nf.value.code == "ROLE_NOT_FOUND"
    finally:
        async with database.session_factory() as db:
            for oid in org_ids:
                await db.execute(delete(Organization).where(Organization.id == oid))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.engine.dispose()
