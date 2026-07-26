"""Transactional organization, workspace, membership, and invitation operations."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.authentication import normalize_email
from vip_api.auth.models import User, utc_now
from vip_api.core.config import AppEnvironment, Settings
from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.seed import provision_organization_governance
from vip_api.governance.services import GovernanceRequirement, authorize, consume_quota, get_role
from vip_api.schemas.tenancy import (
    InvitationCreate,
    MemberUpdate,
    OrganizationCreate,
    WorkspaceCreate,
)
from vip_api.tenancy.audit import audit_event
from vip_api.tenancy.models import (
    Invitation,
    InvitationStatus,
    InvitationWorkspace,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)
from vip_api.tenancy.repositories import (
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
    WorkspaceRepository,
)

logger = logging.getLogger(__name__)


def conflict(code: str, message: str) -> ApplicationError:
    return ApplicationError(code=code, message=message, status_code=409)


async def authorized_organization(
    db: AsyncSession, organization_id: UUID, user_id: UUID, *, manager: bool = False
) -> tuple[Organization, OrganizationMembership]:
    result = await OrganizationRepository(db).get_authorized(organization_id, user_id)
    if result is None:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    if manager and result[1].role.key not in {"organization_owner", "organization_admin"}:
        raise ApplicationError(
            code="ORGANIZATION_ACCESS_DENIED",
            message="You do not have permission to perform this action.",
            status_code=403,
        )
    return result


async def create_organization(
    db: AsyncSession, actor: User, payload: OrganizationCreate, default_workspace_name: str
) -> tuple[Organization, OrganizationMembership, Workspace]:
    repository = OrganizationRepository(db)
    if await repository.slug_exists(payload.slug):
        raise conflict("ORGANIZATION_SLUG_CONFLICT", "That organization slug is already in use.")
    organization = Organization(
        name=payload.name.strip(),
        slug=payload.slug,
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=actor.id,
    )
    db.add(organization)
    try:
        await db.flush()
        owner_role = await get_role(db, "organization_owner", "organization")
        workspace_admin_role = await get_role(db, "workspace_admin", "workspace")
        membership = OrganizationMembership(
            organization_id=organization.id,
            user_id=actor.id,
            role_id=owner_role.id,
            role=owner_role,
            status=MembershipStatus.ACTIVE,
            joined_at=utc_now(),
        )
        workspace = Workspace(
            organization_id=organization.id,
            name=default_workspace_name,
            slug="default",
            status=WorkspaceStatus.ACTIVE,
            is_default=True,
            created_by_user_id=actor.id,
        )
        db.add_all([membership, workspace])
        await db.flush()
        await provision_organization_governance(db, organization.id)
        db.add(
            WorkspaceMembership(
                organization_id=organization.id,
                workspace_id=workspace.id,
                user_id=actor.id,
                role_id=workspace_admin_role.id,
                status=MembershipStatus.ACTIVE,
            )
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise conflict(
            "ORGANIZATION_SLUG_CONFLICT", "That organization slug is already in use."
        ) from exc
    audit_event(
        "organization.created",
        actor_user_id=actor.id,
        organization_id=organization.id,
        resource_type="organization",
        resource_id=organization.id,
    )
    return organization, membership, workspace


async def create_workspace(
    db: AsyncSession,
    organization_id: UUID,
    actor: User,
    payload: WorkspaceCreate,
    authorization_context: AuthorizationContext,
) -> Workspace:
    await authorize(
        db,
        authorization_context,
        GovernanceRequirement("workspace.create", quota="workspaces.max"),
    )
    await consume_quota(db, authorization_context, "workspaces.max")
    if authorization_context.organization_id != organization_id:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    await authorized_organization(db, organization_id, actor.id, manager=True)
    repository = WorkspaceRepository(db)
    if await repository.slug_exists(organization_id, payload.slug):
        raise conflict("WORKSPACE_SLUG_CONFLICT", "That workspace slug is already in use.")
    workspace = Workspace(
        organization_id=organization_id,
        name=payload.name.strip(),
        slug=payload.slug,
        status=WorkspaceStatus.ACTIVE,
        is_default=False,
        created_by_user_id=actor.id,
    )
    db.add(workspace)
    try:
        await db.flush()
        workspace_admin_role = await get_role(db, "workspace_admin", "workspace")
        db.add(
            WorkspaceMembership(
                organization_id=organization_id,
                workspace_id=workspace.id,
                user_id=actor.id,
                role_id=workspace_admin_role.id,
                status=MembershipStatus.ACTIVE,
            )
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise conflict("WORKSPACE_SLUG_CONFLICT", "That workspace slug is already in use.") from exc
    audit_event(
        "workspace.created",
        actor_user_id=actor.id,
        organization_id=organization_id,
        workspace_id=workspace.id,
        resource_type="workspace",
        resource_id=workspace.id,
    )
    return workspace


async def update_membership(
    db: AsyncSession,
    organization_id: UUID,
    membership_id: UUID,
    actor: User,
    payload: MemberUpdate,
    authorization_context: AuthorizationContext,
) -> OrganizationMembership:
    await authorize(db, authorization_context, GovernanceRequirement("organization.members.update"))
    if authorization_context.organization_id != organization_id:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    await authorized_organization(db, organization_id, actor.id, manager=True)
    # Serialize owner-count changes on the organization. Locking only the target
    # membership would allow two owners to demote one another concurrently.
    await db.scalar(
        select(Organization.id).where(Organization.id == organization_id).with_for_update()
    )
    repository = MembershipRepository(db)
    membership = await repository.get_organization_membership(
        organization_id, membership_id, for_update=True
    )
    if membership is None:
        raise ApplicationError(
            code="MEMBERSHIP_NOT_FOUND", message="The membership was not found.", status_code=404
        )
    if membership.user_id == actor.id and payload.role not in {None, membership.role.key}:
        raise ApplicationError(
            code="SELF_ROLE_CHANGE_DENIED",
            message="You cannot change your own organization role.",
            status_code=403,
        )
    removes_owner = membership.role.key == "organization_owner" and (
        (payload.role is not None and payload.role != "organization_owner")
        or (payload.status is not None and payload.status is not MembershipStatus.ACTIVE)
    )
    if removes_owner and await repository.active_owner_count(organization_id) <= 1:
        raise conflict(
            "LAST_OWNER_REQUIRED", "The final organization owner cannot be removed or demoted."
        )
    previous_role = membership.role.key
    if payload.role is not None:
        role = await get_role(db, payload.role, "organization")
        if role.key == "organization_owner":
            raise ApplicationError(
                code="ROLE_ASSIGNMENT_DENIED",
                message="The selected role cannot be assigned through this operation.",
                status_code=403,
            )
        membership.role_id = role.id
        membership.role = role
    if payload.status is not None:
        membership.status = payload.status
        if payload.status is MembershipStatus.REMOVED:
            membership.removed_at = utc_now()
        if payload.status is not MembershipStatus.ACTIVE:
            await repository.revoke_workspace_access(organization_id, membership.user_id)
    await record_audit(
        db,
        "membership.role_changed" if payload.role is not None else "membership.status_changed",
        actor_user_id=actor.id,
        organization_id=organization_id,
        outcome="success",
        resource_type="organization_membership",
        resource_id=membership.id,
        metadata={"previous_role": previous_role, "new_role": membership.role.key},
    )
    await db.commit()
    audit_event(
        "membership.updated",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="organization_membership",
        resource_id=membership.id,
    )
    return membership


async def remove_membership(
    db: AsyncSession,
    organization_id: UUID,
    membership_id: UUID,
    actor: User,
    authorization_context: AuthorizationContext,
) -> OrganizationMembership:
    return await update_membership(
        db,
        organization_id,
        membership_id,
        actor,
        MemberUpdate(status=MembershipStatus.REMOVED),
        authorization_context,
    )


def invitation_token_hash(token: str) -> str:
    return hashlib.sha256(f"vip-invitation-v1:{token}".encode()).hexdigest()


async def create_invitation(
    db: AsyncSession,
    organization_id: UUID,
    actor: User,
    payload: InvitationCreate,
    settings: Settings,
    authorization_context: AuthorizationContext,
) -> tuple[Invitation, list[UUID], str | None]:
    await authorize(db, authorization_context, GovernanceRequirement("organization.members.invite"))
    if authorization_context.organization_id != organization_id:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    await authorized_organization(db, organization_id, actor.id, manager=True)
    workspace_repository = WorkspaceRepository(db)
    for workspace_id in payload.workspace_ids:
        if (
            await workspace_repository.get_in_organization(
                organization_id, workspace_id, active_only=True
            )
            is None
        ):
            raise ApplicationError(
                code="WORKSPACE_NOT_FOUND", message="The workspace was not found.", status_code=404
            )
    normalized_email = normalize_email(payload.email)
    memberships = MembershipRepository(db)
    existing_user = await db.scalar(select(User).where(User.normalized_email == normalized_email))
    if existing_user is not None:
        existing_membership = await memberships.get_user_organization_membership(
            organization_id, existing_user.id
        )
        if existing_membership and existing_membership.status is MembershipStatus.ACTIVE:
            raise conflict(
                "MEMBERSHIP_ALREADY_EXISTS", "The user is already an organization member."
            )
    invitation_repository = InvitationRepository(db)
    if await invitation_repository.pending_for_email(organization_id, normalized_email):
        raise conflict("INVITATION_ALREADY_PENDING", "A pending invitation already exists.")
    token = secrets.token_urlsafe(settings.INVITATION_TOKEN_BYTES)
    organization_role = await get_role(db, payload.organization_role, "organization")
    workspace_role = await get_role(db, payload.workspace_role, "workspace")
    if not organization_role.is_assignable or not workspace_role.is_assignable:
        raise ApplicationError(
            code="ROLE_ASSIGNMENT_DENIED",
            message="The selected role cannot be assigned through an invitation.",
            status_code=403,
        )
    invitation = Invitation(
        organization_id=organization_id,
        email=payload.email.strip(),
        normalized_email=normalized_email,
        organization_role_id=organization_role.id,
        workspace_role_id=workspace_role.id,
        organization_role=organization_role,
        workspace_role=workspace_role,
        token_hash=invitation_token_hash(token),
        status=InvitationStatus.PENDING,
        expires_at=utc_now() + timedelta(hours=settings.INVITATION_TOKEN_TTL_HOURS),
        invited_by_user_id=actor.id,
    )
    db.add(invitation)
    try:
        await db.flush()
        db.add_all(
            [
                InvitationWorkspace(
                    invitation_id=invitation.id,
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                )
                for workspace_id in payload.workspace_ids
            ]
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise conflict(
            "INVITATION_ALREADY_PENDING", "A pending invitation already exists."
        ) from exc
    audit_event(
        "invitation.created",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="invitation",
        resource_id=invitation.id,
    )
    delivered_token = (
        token if settings.APP_ENV in {AppEnvironment.DEVELOPMENT, AppEnvironment.TEST} else None
    )
    return invitation, payload.workspace_ids, delivered_token


async def accept_invitation(
    db: AsyncSession, actor: User, token: str
) -> tuple[Invitation, list[UUID]]:
    repository = InvitationRepository(db)
    invitation = await repository.get_by_token_hash(invitation_token_hash(token))
    if invitation is None:
        raise ApplicationError(
            code="INVITATION_INVALID", message="The invitation is invalid.", status_code=404
        )
    if invitation.status is InvitationStatus.REVOKED:
        raise ApplicationError(
            code="INVITATION_REVOKED", message="The invitation has been revoked.", status_code=410
        )
    if invitation.status is InvitationStatus.ACCEPTED:
        raise ApplicationError(
            code="INVITATION_ALREADY_USED",
            message="The invitation has already been used.",
            status_code=410,
        )
    if invitation.status is InvitationStatus.EXPIRED or invitation.expires_at <= utc_now():
        invitation.status = InvitationStatus.EXPIRED
        await db.commit()
        raise ApplicationError(
            code="INVITATION_EXPIRED", message="The invitation has expired.", status_code=410
        )
    if invitation.normalized_email != actor.normalized_email:
        raise ApplicationError(
            code="INVITATION_EMAIL_MISMATCH",
            message="The invitation is not valid for this account.",
            status_code=403,
        )
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == invitation.organization_id,
            Organization.status == OrganizationStatus.ACTIVE,
            Organization.deleted_at.is_(None),
        )
    )
    if organization is None:
        raise ApplicationError(
            code="INVITATION_INVALID", message="The invitation is invalid.", status_code=404
        )
    workspace_ids = await repository.workspace_ids(invitation.organization_id, invitation.id)
    workspace_repository = WorkspaceRepository(db)
    for workspace_id in workspace_ids:
        if (
            await workspace_repository.get_in_organization(
                invitation.organization_id, workspace_id, active_only=True
            )
            is None
        ):
            raise ApplicationError(
                code="INVITATION_INVALID", message="The invitation is invalid.", status_code=409
            )
    membership_repository = MembershipRepository(db)
    membership = await membership_repository.get_user_organization_membership(
        invitation.organization_id, actor.id
    )
    if membership is None:
        db.add(
            OrganizationMembership(
                organization_id=invitation.organization_id,
                user_id=actor.id,
                role_id=invitation.organization_role_id,
                status=MembershipStatus.ACTIVE,
                joined_at=utc_now(),
                invited_by_user_id=invitation.invited_by_user_id,
            )
        )
    else:
        membership.role_id = invitation.organization_role_id
        membership.role = invitation.organization_role
        membership.status = MembershipStatus.ACTIVE
        membership.joined_at = membership.joined_at or utc_now()
        membership.removed_at = None
    for workspace_id in workspace_ids:
        workspace_membership = await db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.organization_id == invitation.organization_id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == actor.id,
            )
        )
        if workspace_membership is None:
            db.add(
                WorkspaceMembership(
                    organization_id=invitation.organization_id,
                    workspace_id=workspace_id,
                    user_id=actor.id,
                    role_id=invitation.workspace_role_id,
                    status=MembershipStatus.ACTIVE,
                )
            )
        else:
            workspace_membership.role_id = invitation.workspace_role_id
            workspace_membership.role = invitation.workspace_role
            workspace_membership.status = MembershipStatus.ACTIVE
            workspace_membership.removed_at = None
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_by_user_id = actor.id
    invitation.accepted_at = utc_now()
    await db.commit()
    audit_event(
        "invitation.accepted",
        actor_user_id=actor.id,
        organization_id=invitation.organization_id,
        resource_type="invitation",
        resource_id=invitation.id,
    )
    return invitation, workspace_ids


async def revoke_invitation(
    db: AsyncSession,
    organization_id: UUID,
    invitation_id: UUID,
    actor: User,
    authorization_context: AuthorizationContext,
) -> Invitation:
    await authorize(db, authorization_context, GovernanceRequirement("organization.members.invite"))
    await authorized_organization(db, organization_id, actor.id, manager=True)
    invitation = await InvitationRepository(db).get_scoped(
        organization_id, invitation_id, for_update=True
    )
    if invitation is None:
        raise ApplicationError(
            code="INVITATION_INVALID", message="The invitation was not found.", status_code=404
        )
    if invitation.status is InvitationStatus.PENDING:
        invitation.status = InvitationStatus.REVOKED
        invitation.revoked_at = utc_now()
        await db.commit()
    audit_event(
        "invitation.revoked",
        actor_user_id=actor.id,
        organization_id=organization_id,
        resource_type="invitation",
        resource_id=invitation.id,
    )
    return invitation
