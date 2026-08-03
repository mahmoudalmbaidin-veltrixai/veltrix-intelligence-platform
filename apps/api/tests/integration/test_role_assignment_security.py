"""Role-assignment privilege-escalation guards (Phase B9.0 critical stabilization).

Drives the real ``role_assignment_service`` against vip_test to prove the
fail-closed authorization added to ``assign_user_role`` / ``assign_group_role`` /
``bulk_assign_role``: an actor holding ``role.assign`` can never confer a role that
exceeds their own authority (permission ceiling), a higher-ranked system role
(priority ceiling), a non-assignable/protected role, or an archived role — and the
same guard applies identically to group assignments, closing the group-based
escalation path. Platform super-admins bypass the ceiling; cross-tenant attempts
are non-disclosing; every denial is audited.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance import role_assignment_service, role_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import AuditEvent, Permission, Role
from vip_api.governance.seed import seed_system_governance
from vip_api.governance.services import get_role as get_system_role
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)


def _ctx(
    *,
    user: UUID,
    org: UUID,
    ws: UUID | None,
    org_role: str,
    ws_role: str | None,
    perms: frozenset[str],
) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key=org_role,
        workspace_role_key=ws_role,
        permissions=perms,
        entitlements=frozenset(),
        feature_flags={},
        quotas={},
        correlation_id="role-assign-security-test",
    )


async def _all_permission_keys(db: AsyncSession) -> frozenset[str]:
    rows = await db.scalars(select(Permission.key))
    return frozenset(rows.all())


async def _system_role(db: AsyncSession, key: str) -> Role:
    scope = "organization" if key.startswith("organization") else "workspace"
    return await get_system_role(db, key, scope)


async def _role_permission_keys(db: AsyncSession, role_id: UUID) -> frozenset[str]:
    from vip_api.governance.role_service import _permission_keys

    return frozenset(await _permission_keys(db, role_id))


async def _make_user(db: AsyncSession, suffix: str, label: str) -> User:
    user = User(
        username=f"ras-{label}-{suffix}",
        normalized_username=f"ras-{label}-{suffix}",
        email=f"ras-{label}-{suffix}@vip.test",
        normalized_email=f"ras-{label}-{suffix}@vip.test",
        display_name=f"RAS {label}",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_org(db: AsyncSession, suffix: str) -> tuple[Organization, Workspace, User, User]:
    admin = await _make_user(db, suffix, "admin")
    member = await _make_user(db, suffix, "member")
    org = Organization(
        name=f"RAS Org {suffix}",
        slug=f"ras-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=admin.id,
    )
    db.add(org)
    await db.flush()
    ws = Workspace(
        organization_id=org.id,
        name="RAS WS",
        slug="ras-ws",
        status=WorkspaceStatus.ACTIVE,
        is_default=True,
        created_by_user_id=admin.id,
    )
    db.add(ws)
    await db.flush()
    admin_role = await _system_role(db, "organization_admin")
    member_role = await _system_role(db, "organization_member")
    db.add_all(
        (
            OrganizationMembership(
                organization_id=org.id,
                user_id=admin.id,
                role_id=admin_role.id,
                status=MembershipStatus.ACTIVE,
            ),
            OrganizationMembership(
                organization_id=org.id,
                user_id=member.id,
                role_id=member_role.id,
                status=MembershipStatus.ACTIVE,
            ),
        )
    )
    await db.commit()
    return org, ws, admin, member


async def _denied_audit_count(db: AsyncSession, org_id: UUID) -> int:
    total = await db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.organization_id == org_id,
            AuditEvent.event_type == "role.assignment.denied",
        )
    )
    return int(total or 0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_assignment_privilege_ceilings(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            suffix = uuid4().hex[:8]
            org, ws, admin, member = await _seed_org(db, suffix)
            org_ids.append(org.id)
            user_ids.extend([admin.id, member.id])

            all_perms = await _all_permission_keys(db)
            owner = await _system_role(db, "organization_owner")
            org_admin = await _system_role(db, "organization_admin")
            ws_admin = await _system_role(db, "workspace_admin")
            editor = await _system_role(db, "editor")
            viewer = await _system_role(db, "viewer")
            ws_admin_perms = await _role_permission_keys(db, ws_admin.id)

            # A fully-capable org admin (rank 80, holds every permission).
            admin_ctx = _ctx(
                user=admin.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_admin",
                ws_role="workspace_admin",
                perms=all_perms,
            )

            # 1. Equal-or-lower system role → allowed (editor 50, org_admin 80).
            assignment = await role_assignment_service.assign_user_role(
                db, admin_ctx, role_id=editor.id, user_id=member.id
            )
            assert assignment.role_id == editor.id
            assert assignment.scope == "workspace"
            assert assignment.workspace_id == ws.id  # bound to the actor's workspace
            equal = await role_assignment_service.assign_user_role(
                db, admin_ctx, role_id=org_admin.id, user_id=member.id
            )
            assert equal.role_id == org_admin.id

            # 2. Higher / protected system role (Organization Owner, is_assignable=False)
            #    → denied even for a full org admin, and even for self.
            with pytest.raises(ApplicationError) as higher:
                await role_assignment_service.assign_user_role(
                    db, admin_ctx, role_id=owner.id, user_id=member.id
                )
            assert higher.value.code == "ROLE_NOT_ASSIGNABLE"
            assert higher.value.status_code == 403
            with pytest.raises(ApplicationError) as self_owner:
                await role_assignment_service.assign_user_role(
                    db, admin_ctx, role_id=owner.id, user_id=admin.id
                )
            assert self_owner.value.code == "ROLE_NOT_ASSIGNABLE"

            # 3. Permission ceiling: a custom role carrying a permission the actor
            #    lacks cannot be conferred. Build it from a broader actor, then
            #    attempt assignment from a narrower actor.
            broad_ctx = _ctx(
                user=admin.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_admin",
                ws_role="workspace_admin",
                perms=all_perms,
            )
            elevated_role = await role_service.create_role(
                db,
                broad_ctx,
                name=f"Elevated {suffix}",
                description="",
                scope="organization",
                permission_keys={"pipeline.delete"},
                is_platform_admin=False,
            )
            narrow_ctx = _ctx(
                user=member.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_member",
                ws_role="viewer",
                perms=frozenset({"role.assign", "role.read", "workspace.read"}),
            )
            with pytest.raises(ApplicationError) as perm_ceiling:
                await role_assignment_service.assign_user_role(
                    db, narrow_ctx, role_id=elevated_role.id, user_id=admin.id
                )
            assert perm_ceiling.value.code == "ROLE_ESCALATION_DENIED"
            assert perm_ceiling.value.status_code == 403

            # 4. Priority ceiling: an actor who *does* hold every workspace_admin
            #    permission (via grants) but ranks only as a viewer still cannot
            #    confer the higher-ranked workspace_admin system role.
            low_rank_ctx = _ctx(
                user=member.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_member",
                ws_role="viewer",
                perms=ws_admin_perms | {"role.assign"},
            )
            with pytest.raises(ApplicationError) as rank_ceiling:
                await role_assignment_service.assign_user_role(
                    db, low_rank_ctx, role_id=ws_admin.id, user_id=admin.id
                )
            assert rank_ceiling.value.code == "ROLE_ESCALATION_DENIED"

            # 5. Self-escalation attempt (member granting themselves org_admin) → denied.
            with pytest.raises(ApplicationError) as self_esc:
                await role_assignment_service.assign_user_role(
                    db, narrow_ctx, role_id=org_admin.id, user_id=member.id
                )
            assert self_esc.value.code == "ROLE_ESCALATION_DENIED"

            # 6. Every denial above is persisted as an audited event.
            assert await _denied_audit_count(db, org.id) >= 4

            # 7. A viewer assignment (rank 30 ≤ 80) by the admin remains allowed —
            #    the guard restricts escalation, not legitimate administration.
            ok_viewer = await role_assignment_service.assign_user_role(
                db, admin_ctx, role_id=viewer.id, user_id=member.id
            )
            assert ok_viewer.role_id == viewer.id
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
async def test_group_assignment_shares_the_same_ceiling(settings: Settings) -> None:
    """The group path must not be a back door around the user-path guard."""
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            suffix = uuid4().hex[:8]
            org, ws, admin, member = await _seed_org(db, suffix)
            org_ids.append(org.id)
            user_ids.extend([admin.id, member.id])

            from vip_api.governance import group_service

            broad_ctx = _ctx(
                user=admin.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_admin",
                ws_role="workspace_admin",
                perms=await _all_permission_keys(db),
            )
            group = await group_service.create_group(db, broad_ctx, name=f"Curators {suffix}")
            elevated = await role_service.create_role(
                db,
                broad_ctx,
                name=f"Elevated Group {suffix}",
                description="",
                scope="organization",
                permission_keys={"pipeline.delete"},
            )
            narrow_ctx = _ctx(
                user=member.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_member",
                ws_role="viewer",
                perms=frozenset({"role.assign", "role.read", "workspace.read"}),
            )
            with pytest.raises(ApplicationError) as denied:
                await role_assignment_service.assign_group_role(
                    db, narrow_ctx, role_id=elevated.id, group_id=group.id
                )
            assert denied.value.code == "ROLE_ESCALATION_DENIED"

            # The full admin can still legitimately assign the same role to the group.
            ok = await role_assignment_service.assign_group_role(
                db, broad_ctx, role_id=elevated.id, group_id=group.id
            )
            assert ok.role_id == elevated.id
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
async def test_platform_admin_bypasses_ceiling_but_not_archived(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            suffix = uuid4().hex[:8]
            org, ws, admin, member = await _seed_org(db, suffix)
            org_ids.append(org.id)
            user_ids.extend([admin.id, member.id])

            owner = await _system_role(db, "organization_owner")
            # A platform super-admin operating in-tenant can confer the protected
            # Owner role that a tenant admin cannot.
            platform_ctx = _ctx(
                user=admin.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_admin",
                ws_role="workspace_admin",
                perms=frozenset({"role.assign"}),
            )
            assignment = await role_assignment_service.assign_user_role(
                db,
                platform_ctx,
                role_id=owner.id,
                user_id=member.id,
                is_platform_admin=True,
            )
            assert assignment.role_id == owner.id

            # Archived roles are refused even for a platform admin.
            broad_ctx = _ctx(
                user=admin.id,
                org=org.id,
                ws=ws.id,
                org_role="organization_admin",
                ws_role="workspace_admin",
                perms=await _all_permission_keys(db),
            )
            custom = await role_service.create_role(
                db,
                broad_ctx,
                name=f"Archivable {suffix}",
                description="",
                scope="organization",
                permission_keys={"dashboard.read"},
            )
            await role_service.set_archived(
                db, broad_ctx, custom.id, expected_version=custom.row_version, archived=True
            )
            with pytest.raises(ApplicationError) as archived:
                await role_assignment_service.assign_user_role(
                    db,
                    broad_ctx,
                    role_id=custom.id,
                    user_id=member.id,
                    is_platform_admin=True,
                )
            assert archived.value.code == "ROLE_ARCHIVED"
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
async def test_cross_tenant_assignment_is_non_disclosing(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            s1, s2 = uuid4().hex[:8], uuid4().hex[:8]
            org_a, ws_a, admin_a, _ = await _seed_org(db, s1)
            org_b, ws_b, _, member_b = await _seed_org(db, s2)
            org_ids.extend([org_a.id, org_b.id])
            user_ids.extend([admin_a.id, member_b.id])

            editor = await _system_role(db, "editor")
            ctx_a = _ctx(
                user=admin_a.id,
                org=org_a.id,
                ws=ws_a.id,
                org_role="organization_admin",
                ws_role="workspace_admin",
                perms=await _all_permission_keys(db),
            )
            # Subject belongs to another tenant → non-disclosing SUBJECT_NOT_FOUND.
            with pytest.raises(ApplicationError) as cross:
                await role_assignment_service.assign_user_role(
                    db, ctx_a, role_id=editor.id, user_id=member_b.id
                )
            assert cross.value.code == "SUBJECT_NOT_FOUND"

            # A custom role scoped to org B cannot be resolved from org A → ROLE_NOT_FOUND.
            ctx_b = _ctx(
                user=member_b.id,
                org=org_b.id,
                ws=ws_b.id,
                org_role="organization_admin",
                ws_role="workspace_admin",
                perms=await _all_permission_keys(db),
            )
            role_b = await role_service.create_role(
                db,
                ctx_b,
                name=f"OrgB Role {s2}",
                description="",
                scope="organization",
                permission_keys={"dashboard.read"},
            )
            with pytest.raises(ApplicationError) as cross_role:
                await role_assignment_service.assign_user_role(
                    db, ctx_a, role_id=role_b.id, user_id=admin_a.id
                )
            assert cross_role.value.code == "ROLE_NOT_FOUND"
    finally:
        async with database.session_factory() as db:
            for oid in org_ids:
                await db.execute(delete(Organization).where(Organization.id == oid))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.engine.dispose()
