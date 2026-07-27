"""Cross-tenant platform super-admin services.

Every function here is reachable only behind ``require_platform_admin``. Actions
are audited. These are the only places in the codebase that intentionally query
across tenant boundaries, on behalf of a verified platform operator.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.authentication import normalize_email
from vip_api.auth.models import User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.services import get_role
from vip_api.platform_admin.schemas import (
    AddOrgMemberRequest,
    CreateOrganizationRequest,
    CreatePlatformUserRequest,
    PlatformMemberRow,
    PlatformOrganizationDetail,
    PlatformOrganizationList,
    PlatformOrganizationRow,
    PlatformOverview,
    PlatformUserList,
    PlatformUserRow,
    PlatformWorkspaceRow,
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
        clause = func.lower(User.email).like(term) | func.lower(User.display_name).like(term)
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

    Reuses the standard password hashing; no schema change. 'username' is the
    display name, the login identifier is the email.
    """
    normalized = normalize_email(payload.email)
    existing = await db.scalar(select(User).where(User.normalized_email == normalized))
    if existing is not None:
        raise ApplicationError(
            code="EMAIL_ALREADY_EXISTS",
            message="A user with that email already exists.",
            status_code=409,
        )
    user = User(
        email=payload.email.strip(),
        normalized_email=normalized,
        password_hash=password_service.hash_password(payload.password),
        display_name=payload.display_name.strip(),
        status=UserStatus.ACTIVE,
        is_platform_admin=payload.is_platform_admin,
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
    """Add an existing user (by email) to an organization with a role."""
    user = await db.scalar(
        select(User).where(User.normalized_email == normalize_email(payload.email))
    )
    if user is None:
        raise ApplicationError(
            code="USER_NOT_FOUND", message="No user exists with that email.", status_code=404
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
        email=user.email,
        display_name=user.display_name,
        status=str(user.status),
        is_platform_admin=user.is_platform_admin,
        organization_count=org_count,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


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
        email=user.email,
        display_name=user.display_name,
        status=str(user.status),
        is_platform_admin=user.is_platform_admin,
        organization_count=org_count,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )
