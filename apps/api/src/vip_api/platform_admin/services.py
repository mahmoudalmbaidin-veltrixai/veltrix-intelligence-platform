"""Cross-tenant platform super-admin services.

Every function here is reachable only behind ``require_platform_admin``. Actions
are audited. These are the only places in the codebase that intentionally query
across tenant boundaries, on behalf of a verified platform operator.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.authentication import normalize_email
from vip_api.auth.models import User, UserStatus, normalize_username, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.sessions import revoke_all_user_sessions
from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.models import Role
from vip_api.governance.services import get_role
from vip_api.platform_admin.schemas import (
    AddOrgMemberRequest,
    AddWorkspaceMemberRequest,
    AdminResetPasswordRequest,
    CreateOrganizationRequest,
    CreatePlatformUserRequest,
    CreateWorkspaceRequest,
    OrgAssignment,
    PlatformMemberRow,
    PlatformOrganizationDetail,
    PlatformOrganizationList,
    PlatformOrganizationRow,
    PlatformOverview,
    PlatformUserList,
    PlatformUserRow,
    PlatformWorkspaceRow,
    UpdatePlatformUserRequest,
    UserAccessSummary,
    WorkspaceAssignment,
)
from vip_api.schemas.tenancy import OrganizationCreate
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)
from vip_api.tenancy.services import create_organization as tenancy_create_organization

# Maps an organization role to the workspace role granted on the default workspace.
_ORG_TO_WORKSPACE_ROLE = {
    "organization_owner": "workspace_admin",
    "organization_admin": "workspace_admin",
    "organization_member": "viewer",
}


async def _provision_org_access(
    db: AsyncSession, user: User, organization_id: UUID, org_role_key: str
) -> None:
    """Idempotently give ``user`` a role in an org + access to its default workspace."""
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND", message="Organization not found.", status_code=404
        )
    org_role = await get_role(db, org_role_key, "organization")

    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if membership is None:
        db.add(
            OrganizationMembership(
                organization_id=organization_id,
                user_id=user.id,
                role_id=org_role.id,
                status=MembershipStatus.ACTIVE,
                joined_at=utc_now(),
            )
        )
    else:
        membership.role_id = org_role.id
        membership.status = MembershipStatus.ACTIVE

    # Grant access to the organization's default workspace so studio modules work.
    workspace = await db.scalar(
        select(Workspace).where(
            Workspace.organization_id == organization_id,
            Workspace.is_default.is_(True),
            Workspace.status == WorkspaceStatus.ACTIVE,
        )
    )
    if workspace is not None:
        ws_role_key = _ORG_TO_WORKSPACE_ROLE.get(org_role_key, "viewer")
        ws_role = await get_role(db, ws_role_key, "workspace")
        ws_membership = await db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == user.id,
            )
        )
        if ws_membership is None:
            db.add(
                WorkspaceMembership(
                    organization_id=organization_id,
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role_id=ws_role.id,
                    status=MembershipStatus.ACTIVE,
                )
            )
        else:
            ws_membership.role_id = ws_role.id
            ws_membership.status = MembershipStatus.ACTIVE


_ACTIVE_MEMBER = (MembershipStatus.ACTIVE, MembershipStatus.INVITED)


async def overview(db: AsyncSession) -> PlatformOverview:
    orgs_total = await db.scalar(select(func.count()).select_from(Organization)) or 0
    orgs_active = (
        await db.scalar(
            select(func.count()).where(Organization.status == OrganizationStatus.ACTIVE)
        )
        or 0
    )
    orgs_suspended = (
        await db.scalar(
            select(func.count()).where(Organization.status == OrganizationStatus.SUSPENDED)
        )
        or 0
    )
    ws_total = (
        await db.scalar(select(func.count()).where(Workspace.status != WorkspaceStatus.DELETED))
        or 0
    )
    users_total = await db.scalar(select(func.count()).select_from(User)) or 0
    users_active = (
        await db.scalar(select(func.count()).where(User.status == UserStatus.ACTIVE)) or 0
    )
    users_suspended = (
        await db.scalar(select(func.count()).where(User.status == UserStatus.SUSPENDED)) or 0
    )
    admins = await db.scalar(select(func.count()).where(User.is_platform_admin.is_(True))) or 0
    return PlatformOverview(
        organizations_total=orgs_total,
        organizations_active=orgs_active,
        organizations_suspended=orgs_suspended,
        workspaces_total=ws_total,
        users_total=users_total,
        users_active=users_active,
        users_suspended=users_suspended,
        platform_admins=admins,
    )


async def list_organizations(
    db: AsyncSession, *, page: int, page_size: int, search: str | None
) -> PlatformOrganizationList:
    base = select(Organization)
    count_stmt = select(func.count()).select_from(Organization)
    if search:
        term = f"%{search.strip().lower()}%"
        clause = func.lower(Organization.name).like(term) | func.lower(Organization.slug).like(term)
        base = base.where(clause)
        count_stmt = count_stmt.where(clause)
    total = await db.scalar(count_stmt) or 0
    rows = (
        await db.scalars(
            base.order_by(Organization.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items: list[PlatformOrganizationRow] = []
    for org in rows:
        member_count = (
            await db.scalar(
                select(func.count()).where(
                    OrganizationMembership.organization_id == org.id,
                    OrganizationMembership.status.in_(_ACTIVE_MEMBER),
                )
            )
            or 0
        )
        workspace_count = (
            await db.scalar(
                select(func.count()).where(
                    Workspace.organization_id == org.id,
                    Workspace.status != WorkspaceStatus.DELETED,
                )
            )
            or 0
        )
        items.append(
            PlatformOrganizationRow(
                id=org.id,
                name=org.name,
                slug=org.slug,
                status=str(org.status),
                member_count=member_count,
                workspace_count=workspace_count,
                created_at=org.created_at,
            )
        )
    return PlatformOrganizationList(items=items, page=page, page_size=page_size, total=total)


async def get_organization_detail(db: AsyncSession, org_id: UUID) -> PlatformOrganizationDetail:
    org = await db.get(Organization, org_id)
    if org is None:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND", message="Organization not found.", status_code=404
        )
    member_rows = (
        await db.execute(
            select(OrganizationMembership, User)
            .join(User, User.id == OrganizationMembership.user_id)
            .where(OrganizationMembership.organization_id == org_id)
            .order_by(OrganizationMembership.created_at.asc())
        )
    ).all()
    members = [
        PlatformMemberRow(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role.key,
            status=str(membership.status),
        )
        for membership, user in member_rows
    ]
    workspaces = [
        PlatformWorkspaceRow(
            id=ws.id, name=ws.name, slug=ws.slug, status=str(ws.status), is_default=ws.is_default
        )
        for ws in (
            await db.scalars(
                select(Workspace)
                .where(Workspace.organization_id == org_id)
                .order_by(Workspace.created_at.asc())
            )
        ).all()
    ]
    return PlatformOrganizationDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=str(org.status),
        created_at=org.created_at,
        members=members,
        workspaces=workspaces,
    )


async def set_organization_status(
    db: AsyncSession, actor: User, org_id: UUID, *, suspend: bool
) -> PlatformOrganizationDetail:
    org = await db.get(Organization, org_id)
    if org is None:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND", message="Organization not found.", status_code=404
        )
    if org.status in (OrganizationStatus.ARCHIVED, OrganizationStatus.DELETED):
        raise ApplicationError(
            code="ORGANIZATION_NOT_MODIFIABLE",
            message="Archived or deleted organizations cannot change status.",
            status_code=409,
        )
    org.status = OrganizationStatus.SUSPENDED if suspend else OrganizationStatus.ACTIVE
    await record_audit(
        db,
        "platform.organization.suspended" if suspend else "platform.organization.activated",
        actor_user_id=actor.id,
        organization_id=org.id,
        resource_type="organization",
        resource_id=org.id,
    )
    await db.commit()
    return await get_organization_detail(db, org_id)


async def create_organization(
    db: AsyncSession, actor: User, payload: CreateOrganizationRequest, default_workspace_name: str
) -> PlatformOrganizationDetail:
    owner: User = actor
    if payload.owner_email:
        found = await db.scalar(
            select(User).where(User.normalized_email == normalize_email(payload.owner_email))
        )
        if found is None:
            raise ApplicationError(
                code="OWNER_NOT_FOUND",
                message="No user exists with that owner email.",
                status_code=422,
            )
        owner = found
    organization, _, _ = await tenancy_create_organization(
        db,
        owner,
        OrganizationCreate(name=payload.name, slug=payload.slug),
        default_workspace_name,
    )
    await record_audit(
        db,
        "platform.organization.created",
        actor_user_id=actor.id,
        organization_id=organization.id,
        resource_type="organization",
        resource_id=organization.id,
        metadata={"owner_user_id": str(owner.id)},
    )
    await db.commit()
    return await get_organization_detail(db, organization.id)


async def list_users(
    db: AsyncSession, *, page: int, page_size: int, search: str | None
) -> PlatformUserList:
    base = select(User)
    count_stmt = select(func.count()).select_from(User)
    if search:
        term = f"%{search.strip().lower()}%"
        clause = (
            func.lower(User.username).like(term)
            | func.lower(User.email).like(term)
            | func.lower(User.display_name).like(term)
        )
        base = base.where(clause)
        count_stmt = count_stmt.where(clause)
    total = await db.scalar(count_stmt) or 0
    rows = (
        await db.scalars(
            base.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    items: list[PlatformUserRow] = []
    for user in rows:
        org_count = (
            await db.scalar(
                select(func.count()).where(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.status.in_(_ACTIVE_MEMBER),
                )
            )
            or 0
        )
        items.append(
            PlatformUserRow(
                id=user.id,
                username=user.username,
                email=user.email,
                display_name=user.display_name,
                status=str(user.status),
                is_platform_admin=user.is_platform_admin,
                organization_count=org_count,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
            )
        )
    return PlatformUserList(items=items, page=page, page_size=page_size, total=total)


async def create_user(
    db: AsyncSession,
    actor: User,
    payload: CreatePlatformUserRequest,
    password_service: PasswordService,
) -> PlatformUserRow:
    """Provision a user directly with an operator-set initial password.

    Login is by username (required). Email is optional — its uniqueness is only
    checked when provided; a NULL email is stored (never a placeholder).
    """
    norm_username = normalize_username(payload.username)
    if await db.scalar(select(User).where(User.normalized_username == norm_username)):
        raise ApplicationError(
            code="USERNAME_ALREADY_EXISTS",
            message="A user with that username already exists.",
            status_code=409,
        )
    email = payload.email.strip() if payload.email and payload.email.strip() else None
    norm_email = normalize_email(email) if email else None
    if norm_email and await db.scalar(select(User).where(User.normalized_email == norm_email)):
        raise ApplicationError(
            code="EMAIL_ALREADY_EXISTS",
            message="A user with that email already exists.",
            status_code=409,
        )
    user = User(
        username=payload.username.strip(),
        normalized_username=norm_username,
        email=email,
        normalized_email=norm_email,
        password_hash=password_service.hash_password(payload.password),
        display_name=payload.display_name.strip(),
        status=UserStatus.ACTIVE,
        is_platform_admin=payload.is_platform_admin,
        created_by=actor.id,
    )
    db.add(user)
    await db.flush()
    # Optionally assign the new user into an organization + default workspace.
    if payload.organization_id is not None and payload.organization_role:
        await _provision_org_access(db, user, payload.organization_id, payload.organization_role)
    await record_audit(
        db,
        "platform.user.created",
        actor_user_id=actor.id,
        organization_id=payload.organization_id,
        resource_type="user",
        resource_id=user.id,
        metadata={"is_platform_admin": payload.is_platform_admin},
    )
    await db.commit()
    org_count = 1 if payload.organization_id is not None and payload.organization_role else 0
    return PlatformUserRow(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        status=str(user.status),
        is_platform_admin=user.is_platform_admin,
        organization_count=org_count,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


async def add_org_member(
    db: AsyncSession, actor: User, organization_id: UUID, payload: AddOrgMemberRequest
) -> PlatformUserRow:
    """Add an existing user (by username or email) to an organization with a role."""
    if payload.username:
        user = await db.scalar(
            select(User).where(User.normalized_username == normalize_username(payload.username))
        )
    else:
        assert payload.email is not None  # guaranteed by the request validator
        user = await db.scalar(
            select(User).where(User.normalized_email == normalize_email(payload.email))
        )
    if user is None:
        raise ApplicationError(
            code="USER_NOT_FOUND", message="No user exists with that identifier.", status_code=404
        )
    await _provision_org_access(db, user, organization_id, payload.organization_role)
    await record_audit(
        db,
        "platform.member.added",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="user",
        resource_id=user.id,
        metadata={"organization_role": payload.organization_role},
    )
    await db.commit()
    org_count = (
        await db.scalar(
            select(func.count()).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status.in_(_ACTIVE_MEMBER),
            )
        )
        or 0
    )
    return PlatformUserRow(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        status=str(user.status),
        is_platform_admin=user.is_platform_admin,
        organization_count=org_count,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


async def terminate_user_sessions(db: AsyncSession, actor: User, user_id: UUID) -> int:
    """Revoke every active session for a user (admin-initiated). Returns the count."""
    user = await db.get(User, user_id)
    if user is None:
        raise ApplicationError(code="USER_NOT_FOUND", message="User not found.", status_code=404)
    revoked = await revoke_all_user_sessions(db, user.id, "admin_terminated")
    await record_audit(
        db,
        "session.revoked_by_admin",
        actor_user_id=actor.id,
        organization_id=None,
        resource_type="user",
        resource_id=user.id,
        metadata={"revoked": revoked},
    )
    await db.commit()
    return revoked


async def set_user_status(
    db: AsyncSession, actor: User, user_id: UUID, *, suspend: bool
) -> PlatformUserRow:
    user = await db.get(User, user_id)
    if user is None:
        raise ApplicationError(code="USER_NOT_FOUND", message="User not found.", status_code=404)
    if user.id == actor.id:
        raise ApplicationError(
            code="CANNOT_SUSPEND_SELF",
            message="You cannot change your own platform status here.",
            status_code=409,
        )
    if user.status in (UserStatus.DELETED,):
        raise ApplicationError(
            code="USER_NOT_MODIFIABLE",
            message="Deleted users cannot change status.",
            status_code=409,
        )
    user.status = UserStatus.SUSPENDED if suspend else UserStatus.ACTIVE
    if suspend:
        # Immediately revoke active sessions on suspension. The auth dependency
        # already rejects non-active users on their next request; this also drops
        # any long-lived refresh session so nothing survives the suspension.
        await revoke_all_user_sessions(db, user.id, "admin_suspended")
    await record_audit(
        db,
        "platform.user.suspended" if suspend else "platform.user.activated",
        actor_user_id=actor.id,
        organization_id=None,
        resource_type="user",
        resource_id=user.id,
    )
    await db.commit()
    org_count = (
        await db.scalar(
            select(func.count()).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status.in_(_ACTIVE_MEMBER),
            )
        )
        or 0
    )
    return PlatformUserRow(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        status=str(user.status),
        is_platform_admin=user.is_platform_admin,
        organization_count=org_count,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


async def _resolve_user(db: AsyncSession, username: str | None, email: str | None) -> User:
    if username:
        user = await db.scalar(
            select(User).where(User.normalized_username == normalize_username(username))
        )
    else:
        assert email is not None
        user = await db.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    if user is None:
        raise ApplicationError(
            code="USER_NOT_FOUND", message="No user exists with that identifier.", status_code=404
        )
    return user


async def _provision_workspace_access(
    db: AsyncSession, user: User, organization_id: UUID, workspace_id: UUID, ws_role_key: str
) -> None:
    """Assign a user to a specific workspace. Enforces org membership first."""
    org_membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if org_membership is None or org_membership.status is not MembershipStatus.ACTIVE:
        raise ApplicationError(
            code="NOT_ORGANIZATION_MEMBER",
            message="The user must belong to the organization before joining a workspace.",
            status_code=409,
        )
    workspace = await db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.organization_id == organization_id,
            Workspace.status == WorkspaceStatus.ACTIVE,
        )
    )
    if workspace is None:
        raise ApplicationError(
            code="WORKSPACE_NOT_FOUND",
            message="Workspace not found in this organization.",
            status_code=404,
        )
    role = await get_role(db, ws_role_key, "workspace")
    membership = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if membership is None:
        db.add(
            WorkspaceMembership(
                organization_id=organization_id,
                workspace_id=workspace_id,
                user_id=user.id,
                role_id=role.id,
                status=MembershipStatus.ACTIVE,
            )
        )
    else:
        membership.role_id = role.id
        membership.status = MembershipStatus.ACTIVE


async def add_workspace_member(
    db: AsyncSession,
    actor: User,
    organization_id: UUID,
    workspace_id: UUID,
    payload: AddWorkspaceMemberRequest,
) -> UserAccessSummary:
    user = await _resolve_user(db, payload.username, payload.email)
    await _provision_workspace_access(
        db, user, organization_id, workspace_id, payload.workspace_role
    )
    await record_audit(
        db,
        "platform.workspace_member.added",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="workspace",
        resource_id=workspace_id,
        metadata={"user_id": str(user.id), "workspace_role": payload.workspace_role},
    )
    await db.commit()
    return await get_access_summary(db, user.id)


async def update_user(
    db: AsyncSession, actor: User, user_id: UUID, payload: UpdatePlatformUserRequest
) -> PlatformUserRow:
    user = await db.get(User, user_id)
    if user is None:
        raise ApplicationError(code="USER_NOT_FOUND", message="User not found.", status_code=404)
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.email is not None:
        cleaned = payload.email.strip()
        if cleaned == "":
            user.email = None
            user.normalized_email = None
        else:
            norm = normalize_email(cleaned)
            dup = await db.scalar(
                select(User.id).where(User.normalized_email == norm, User.id != user_id)
            )
            if dup is not None:
                raise ApplicationError(
                    code="EMAIL_ALREADY_EXISTS",
                    message="A user with that email already exists.",
                    status_code=409,
                )
            user.email = cleaned
            user.normalized_email = norm
    if payload.job_title is not None:
        user.job_title = payload.job_title.strip() or None
    if payload.department is not None:
        user.department = payload.department.strip() or None
    if payload.phone is not None:
        user.phone = payload.phone.strip() or None
    if payload.must_change_password is not None:
        user.must_change_password = payload.must_change_password
    if payload.default_organization_id is not None:
        user.default_organization_id = payload.default_organization_id
    if payload.default_workspace_id is not None:
        user.default_workspace_id = payload.default_workspace_id
    user.updated_by = actor.id
    await record_audit(
        db,
        "platform.user.updated",
        actor_user_id=actor.id,
        organization_id=None,
        resource_type="user",
        resource_id=user.id,
    )
    await db.commit()
    return await _user_row(db, user)


async def reset_user_password(
    db: AsyncSession,
    actor: User,
    user_id: UUID,
    password_service: PasswordService,
    payload: AdminResetPasswordRequest,
) -> PlatformUserRow:
    user = await db.get(User, user_id)
    if user is None:
        raise ApplicationError(code="USER_NOT_FOUND", message="User not found.", status_code=404)
    user.password_hash = password_service.hash_password(payload.password)
    user.password_changed_at = utc_now()
    user.must_change_password = payload.must_change_password
    user.failed_login_count = 0
    user.locked_until = None
    await revoke_all_user_sessions(db, user.id, "admin_password_reset")
    await record_audit(
        db,
        "platform.user.password_reset",
        actor_user_id=actor.id,
        organization_id=None,
        resource_type="user",
        resource_id=user.id,
    )
    await db.commit()
    return await _user_row(db, user)


async def remove_org_access(
    db: AsyncSession, actor: User, organization_id: UUID, user_id: UUID
) -> None:
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise ApplicationError(
            code="MEMBERSHIP_NOT_FOUND", message="Membership not found.", status_code=404
        )
    # Cascade: removing organization access also removes the users workspace
    # memberships within that organization.
    await db.execute(
        update(WorkspaceMembership)
        .where(
            WorkspaceMembership.organization_id == organization_id,
            WorkspaceMembership.user_id == user_id,
        )
        .values(status=MembershipStatus.REMOVED)
    )
    membership.status = MembershipStatus.REMOVED
    await record_audit(
        db,
        "platform.org_member.removed",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="user",
        resource_id=user_id,
    )
    await db.commit()


async def remove_workspace_access(
    db: AsyncSession, actor: User, organization_id: UUID, workspace_id: UUID, user_id: UUID
) -> None:
    membership = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise ApplicationError(
            code="MEMBERSHIP_NOT_FOUND", message="Workspace membership not found.", status_code=404
        )
    membership.status = MembershipStatus.REMOVED
    await record_audit(
        db,
        "platform.workspace_member.removed",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="workspace",
        resource_id=workspace_id,
        metadata={"user_id": str(user_id)},
    )
    await db.commit()


async def _user_row(db: AsyncSession, user: User) -> PlatformUserRow:
    org_count = (
        await db.scalar(
            select(func.count()).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status.in_(_ACTIVE_MEMBER),
            )
        )
        or 0
    )
    return PlatformUserRow(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        status=str(user.status),
        is_platform_admin=user.is_platform_admin,
        organization_count=org_count,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


async def get_access_summary(db: AsyncSession, user_id: UUID) -> UserAccessSummary:
    user = await db.get(User, user_id)
    if user is None:
        raise ApplicationError(code="USER_NOT_FOUND", message="User not found.", status_code=404)

    org_rows = (
        await db.execute(
            select(OrganizationMembership, Organization, Role)
            .join(Organization, Organization.id == OrganizationMembership.organization_id)
            .join(Role, Role.id == OrganizationMembership.role_id)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Organization.name)
        )
    ).all()
    organizations = [
        OrgAssignment(
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            role=role.key,
            status=str(membership.status),
        )
        for membership, org, role in org_rows
    ]

    ws_rows = (
        await db.execute(
            select(WorkspaceMembership, Workspace, Organization, Role)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .join(Organization, Organization.id == WorkspaceMembership.organization_id)
            .join(Role, Role.id == WorkspaceMembership.role_id)
            .where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Organization.name, Workspace.name)
        )
    ).all()
    workspaces = [
        WorkspaceAssignment(
            organization_id=org.id,
            workspace_id=ws.id,
            workspace_name=ws.name,
            organization_name=org.name,
            role=role.key,
            status=str(membership.status),
        )
        for membership, ws, org, role in ws_rows
    ]

    return UserAccessSummary(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        status=str(user.status),
        default_organization_id=user.default_organization_id,
        default_workspace_id=user.default_workspace_id,
        organizations=organizations,
        workspaces=workspaces,
    )


async def create_workspace(
    db: AsyncSession, actor: User, organization_id: UUID, payload: CreateWorkspaceRequest
) -> PlatformWorkspaceRow:
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND", message="Organization not found.", status_code=404
        )
    duplicate = await db.scalar(
        select(Workspace.id).where(
            Workspace.organization_id == organization_id,
            Workspace.slug == payload.slug,
            Workspace.status != WorkspaceStatus.DELETED,
        )
    )
    if duplicate is not None:
        raise ApplicationError(
            code="WORKSPACE_SLUG_CONFLICT",
            message="A workspace with that slug already exists in this organization.",
            status_code=409,
        )
    workspace = Workspace(
        organization_id=organization_id,
        name=payload.name.strip(),
        slug=payload.slug,
        status=WorkspaceStatus.ACTIVE,
        is_default=False,
        created_by_user_id=actor.id,
    )
    db.add(workspace)
    await db.flush()
    await record_audit(
        db,
        "platform.workspace.created",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="workspace",
        resource_id=workspace.id,
    )
    await db.commit()
    return PlatformWorkspaceRow(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        status=str(workspace.status),
        is_default=workspace.is_default,
    )


async def set_workspace_status(
    db: AsyncSession, actor: User, organization_id: UUID, workspace_id: UUID, *, suspend: bool
) -> PlatformWorkspaceRow:
    workspace = await db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id, Workspace.organization_id == organization_id
        )
    )
    if workspace is None or workspace.status is WorkspaceStatus.DELETED:
        raise ApplicationError(
            code="WORKSPACE_NOT_FOUND", message="Workspace not found.", status_code=404
        )
    workspace.status = WorkspaceStatus.SUSPENDED if suspend else WorkspaceStatus.ACTIVE
    await record_audit(
        db,
        "platform.workspace.suspended" if suspend else "platform.workspace.activated",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="workspace",
        resource_id=workspace.id,
    )
    await db.commit()
    return PlatformWorkspaceRow(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        status=str(workspace.status),
        is_default=workspace.is_default,
    )
