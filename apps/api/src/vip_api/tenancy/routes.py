"""Versioned organization, workspace, membership, invitation, and context APIs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import get_current_user, require_csrf
from vip_api.auth.models import User, utc_now
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_governance, require_permission
from vip_api.governance.services import GovernanceRequirement, authorize, get_role
from vip_api.schemas.tenancy import (
    InvitationAccept,
    InvitationAccepted,
    InvitationCreate,
    InvitationCreated,
    InvitationList,
    InvitationSummary,
    MemberList,
    MembershipSummary,
    MemberSummary,
    MemberUpdate,
    OrganizationCreate,
    OrganizationCreated,
    OrganizationList,
    OrganizationSummary,
    OrganizationUpdate,
    TenantContextResponse,
    WorkspaceCreate,
    WorkspaceList,
    WorkspaceMemberCreate,
    WorkspaceSummary,
    WorkspaceUpdate,
)
from vip_api.tenancy.audit import audit_event
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.dependencies import get_tenant_context
from vip_api.tenancy.models import (
    Invitation,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    WorkspaceMembership,
    WorkspaceStatus,
)
from vip_api.tenancy.repositories import (
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
    WorkspaceRepository,
)
from vip_api.tenancy.services import (
    accept_invitation,
    authorized_organization,
    create_invitation,
    create_organization,
    create_workspace,
    remove_membership,
    revoke_invitation,
    update_membership,
)

router = APIRouter(tags=["tenancy"])


def ensure_authorization_scope(context: AuthorizationContext, organization_id: UUID) -> None:
    if context.organization_id != organization_id:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )


def organization_dto(
    organization: Organization, membership: OrganizationMembership
) -> OrganizationSummary:
    return OrganizationSummary(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        status=organization.status,
        membership=MembershipSummary(role=membership.role.key, status=membership.status),
    )


async def invitation_dto(
    repository: InvitationRepository, invitation: Invitation
) -> InvitationSummary:
    organization_id: UUID = invitation.organization_id
    invitation_id: UUID = invitation.id
    return InvitationSummary(
        id=invitation_id,
        organization_id=organization_id,
        email=invitation.email,
        organization_role=invitation.organization_role.key,
        workspace_role=invitation.workspace_role.key,
        workspace_ids=await repository.workspace_ids(organization_id, invitation_id),
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.get("/organizations", response_model=OrganizationList)
async def list_organizations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrganizationList:
    items = await OrganizationRepository(db).list_for_user(user.id)
    return OrganizationList(items=[organization_dto(org, membership) for org, membership in items])


@router.post(
    "/organizations",
    response_model=OrganizationCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_organization(
    payload: OrganizationCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrganizationCreated:
    settings: Settings = request.app.state.settings
    organization, membership, workspace = await create_organization(
        db, user, payload, settings.TENANCY_DEFAULT_WORKSPACE_NAME
    )
    return OrganizationCreated(
        organization=organization_dto(organization, membership),
        default_workspace=WorkspaceSummary.model_validate(workspace),
    )


@router.get("/organizations/{organization_id}", response_model=OrganizationSummary)
async def get_organization(
    organization_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.read"))
    ],
) -> OrganizationSummary:
    ensure_authorization_scope(authorization, organization_id)
    organization, membership = await authorized_organization(db, organization_id, user.id)
    return organization_dto(organization, membership)


@router.patch(
    "/organizations/{organization_id}",
    response_model=OrganizationSummary,
    dependencies=[Depends(require_csrf)],
)
async def patch_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.update"))
    ],
) -> OrganizationSummary:
    ensure_authorization_scope(authorization, organization_id)
    organization, membership = await authorized_organization(
        db, organization_id, user.id, manager=True
    )
    if payload.slug is not None and await OrganizationRepository(db).slug_exists(
        payload.slug, excluding_id=organization_id
    ):
        raise ApplicationError(
            code="ORGANIZATION_SLUG_CONFLICT",
            message="That organization slug is already in use.",
            status_code=409,
        )
    if payload.status is OrganizationStatus.DELETED:
        raise ApplicationError(
            code="INVALID_STATUS_TRANSITION",
            message="Deletion is not supported by this endpoint.",
            status_code=409,
        )
    if payload.name is not None:
        organization.name = payload.name.strip()
    if payload.slug is not None:
        organization.slug = payload.slug
    if payload.status is not None:
        organization.status = payload.status
        if payload.status is OrganizationStatus.ARCHIVED:
            organization.archived_at = utc_now()
    await db.commit()
    audit_event(
        "organization.updated",
        actor_user_id=user.id,
        organization_id=organization_id,
        resource_type="organization",
        resource_id=organization_id,
    )
    return organization_dto(organization, membership)


@router.get("/organizations/{organization_id}/workspaces", response_model=WorkspaceList)
async def list_workspaces(
    organization_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    include_archived: bool = False,
) -> WorkspaceList:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id)
    if include_archived:
        await authorize(db, authorization, GovernanceRequirement("workspace.update"))
    workspaces = await WorkspaceRepository(db).list_for_user(
        organization_id, user.id, include_archived=include_archived
    )
    return WorkspaceList(items=[WorkspaceSummary.model_validate(item) for item in workspaces])


@router.post(
    "/organizations/{organization_id}/workspaces",
    response_model=WorkspaceSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_workspace(
    organization_id: UUID,
    payload: WorkspaceCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext,
        Depends(require_governance("workspace.create", quota="workspaces.max")),
    ],
) -> WorkspaceSummary:
    workspace = await create_workspace(db, organization_id, user, payload, authorization)
    return WorkspaceSummary.model_validate(workspace)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}",
    response_model=WorkspaceSummary,
)
async def get_workspace(
    organization_id: UUID,
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
) -> WorkspaceSummary:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id)
    result = await WorkspaceRepository(db).get_authorized(organization_id, workspace_id, user.id)
    if result is None:
        raise ApplicationError(
            code="WORKSPACE_NOT_FOUND", message="The workspace was not found.", status_code=404
        )
    return WorkspaceSummary.model_validate(result[0])


@router.patch(
    "/organizations/{organization_id}/workspaces/{workspace_id}",
    response_model=WorkspaceSummary,
    dependencies=[Depends(require_csrf)],
)
async def patch_workspace(
    organization_id: UUID,
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_permission("workspace.update"))],
) -> WorkspaceSummary:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id, manager=True)
    repository = WorkspaceRepository(db)
    workspace = await repository.get_in_organization(organization_id, workspace_id)
    if workspace is None:
        raise ApplicationError(
            code="WORKSPACE_NOT_FOUND", message="The workspace was not found.", status_code=404
        )
    if payload.slug is not None and await repository.slug_exists(
        organization_id, payload.slug, excluding_id=workspace_id
    ):
        raise ApplicationError(
            code="WORKSPACE_SLUG_CONFLICT",
            message="That workspace slug is already in use.",
            status_code=409,
        )
    if payload.status is WorkspaceStatus.DELETED:
        raise ApplicationError(
            code="INVALID_STATUS_TRANSITION",
            message="Deletion is not supported by this endpoint.",
            status_code=409,
        )
    if payload.is_default is False and workspace.is_default:
        raise ApplicationError(
            code="DEFAULT_WORKSPACE_REQUIRED",
            message="Select another default workspace first.",
            status_code=409,
        )
    if payload.is_default is True and not workspace.is_default:
        await db.execute(
            update(type(workspace))
            .where(type(workspace).organization_id == organization_id)
            .values(is_default=False)
        )
        workspace.is_default = True
    if payload.name is not None:
        workspace.name = payload.name.strip()
    if payload.slug is not None:
        workspace.slug = payload.slug
    if payload.status is not None:
        if workspace.is_default and payload.status is not WorkspaceStatus.ACTIVE:
            raise ApplicationError(
                code="DEFAULT_WORKSPACE_REQUIRED",
                message="The default workspace must remain active.",
                status_code=409,
            )
        workspace.status = payload.status
        if payload.status is WorkspaceStatus.ARCHIVED:
            workspace.archived_at = utc_now()
    await db.commit()
    audit_event(
        "workspace.updated",
        actor_user_id=user.id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        resource_type="workspace",
        resource_id=workspace_id,
    )
    return WorkspaceSummary.model_validate(workspace)


@router.get("/organizations/{organization_id}/members", response_model=MemberList)
async def list_members(
    organization_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.members.read"))
    ],
) -> MemberList:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id, manager=True)
    items = await MembershipRepository(db).list_organization_members(organization_id)
    return MemberList(
        items=[
            MemberSummary(
                id=membership.id,
                user_id=member.id,
                email=member.email,
                display_name=member.display_name,
                role=membership.role.key,
                status=membership.status,
                joined_at=membership.joined_at,
            )
            for membership, member in items
        ]
    )


@router.patch(
    "/organizations/{organization_id}/members/{membership_id}",
    response_model=MemberSummary,
    dependencies=[Depends(require_csrf)],
)
async def patch_member(
    organization_id: UUID,
    membership_id: UUID,
    payload: MemberUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.members.update"))
    ],
) -> MemberSummary:
    membership = await update_membership(
        db, organization_id, membership_id, user, payload, authorization
    )
    member = await db.scalar(select(User).where(User.id == membership.user_id))
    if member is None:
        raise ApplicationError(
            code="MEMBERSHIP_NOT_FOUND", message="Membership not found.", status_code=404
        )
    return MemberSummary(
        id=membership.id,
        user_id=member.id,
        email=member.email,
        display_name=member.display_name,
        role=membership.role.key,
        status=membership.status,
        joined_at=membership.joined_at,
    )


@router.delete(
    "/organizations/{organization_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_member(
    organization_id: UUID,
    membership_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.members.remove"))
    ],
) -> None:
    await remove_membership(db, organization_id, membership_id, user, authorization)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/members",
    response_model=MemberList,
)
async def list_workspace_members(
    organization_id: UUID,
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("workspace.members.read"))
    ],
) -> MemberList:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id, manager=True)
    if await WorkspaceRepository(db).get_in_organization(organization_id, workspace_id) is None:
        raise ApplicationError(
            code="WORKSPACE_NOT_FOUND", message="Workspace not found.", status_code=404
        )
    items = await MembershipRepository(db).list_workspace_members(organization_id, workspace_id)
    return MemberList(
        items=[
            MemberSummary(
                id=membership.id,
                user_id=member.id,
                email=member.email,
                display_name=member.display_name,
                role=membership.role.key,
                status=membership.status,
                joined_at=None,
            )
            for membership, member in items
        ]
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/members",
    response_model=MemberSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_workspace_member(
    organization_id: UUID,
    workspace_id: UUID,
    payload: WorkspaceMemberCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("workspace.members.manage"))
    ],
) -> MemberSummary:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id, manager=True)
    if (
        await WorkspaceRepository(db).get_in_organization(
            organization_id, workspace_id, active_only=True
        )
        is None
    ):
        raise ApplicationError(
            code="WORKSPACE_NOT_FOUND", message="Workspace not found.", status_code=404
        )
    organization_membership = await MembershipRepository(db).get_user_organization_membership(
        organization_id, payload.user_id
    )
    if (
        organization_membership is None
        or organization_membership.status is not MembershipStatus.ACTIVE
    ):
        raise ApplicationError(
            code="MEMBERSHIP_REQUIRED",
            message="An active organization membership is required.",
            status_code=409,
        )
    existing = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.organization_id == organization_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == payload.user_id,
        )
    )
    if existing is None:
        role = await get_role(db, payload.role, "workspace")
        if not role.is_assignable:
            raise ApplicationError(
                code="ROLE_ASSIGNMENT_DENIED",
                message="The selected role cannot be assigned.",
                status_code=403,
            )
        existing = WorkspaceMembership(
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=payload.user_id,
            role_id=role.id,
            status=MembershipStatus.ACTIVE,
        )
        db.add(existing)
    else:
        role = await get_role(db, payload.role, "workspace")
        existing.role_id = role.id
        existing.role = role
        existing.status = MembershipStatus.ACTIVE
        existing.removed_at = None
    await db.commit()
    member = await db.scalar(select(User).where(User.id == payload.user_id))
    if member is None:
        raise ApplicationError(
            code="MEMBERSHIP_NOT_FOUND", message="Membership not found.", status_code=404
        )
    return MemberSummary(
        id=existing.id,
        user_id=member.id,
        email=member.email,
        display_name=member.display_name,
        role=existing.role.key,
        status=existing.status,
        joined_at=None,
    )


@router.delete(
    "/organizations/{organization_id}/workspaces/{workspace_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_workspace_member(
    organization_id: UUID,
    workspace_id: UUID,
    membership_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("workspace.members.manage"))
    ],
) -> None:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id, manager=True)
    membership = await MembershipRepository(db).get_workspace_membership(
        organization_id, workspace_id, membership_id
    )
    if membership is None:
        raise ApplicationError(
            code="MEMBERSHIP_NOT_FOUND", message="Membership not found.", status_code=404
        )
    membership.status = MembershipStatus.REMOVED
    membership.removed_at = utc_now()
    await db.commit()


@router.post(
    "/organizations/{organization_id}/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_invitation(
    organization_id: UUID,
    payload: InvitationCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.members.invite"))
    ],
) -> InvitationCreated:
    settings: Settings = request.app.state.settings
    invitation, workspace_ids, token = await create_invitation(
        db, organization_id, user, payload, settings, authorization
    )
    return InvitationCreated(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email,
        organization_role=invitation.organization_role.key,
        workspace_role=invitation.workspace_role.key,
        workspace_ids=workspace_ids,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        token=token,
    )


@router.get("/organizations/{organization_id}/invitations", response_model=InvitationList)
async def list_invitations(
    organization_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.members.read"))
    ],
) -> InvitationList:
    ensure_authorization_scope(authorization, organization_id)
    await authorized_organization(db, organization_id, user.id, manager=True)
    repository = InvitationRepository(db)
    invitations = await repository.list_for_organization(organization_id)
    return InvitationList(items=[await invitation_dto(repository, item) for item in invitations])


@router.delete(
    "/organizations/{organization_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[
        AuthorizationContext, Depends(require_permission("organization.members.invite"))
    ],
) -> None:
    await revoke_invitation(db, organization_id, invitation_id, user, authorization)


@router.post(
    "/invitations/accept",
    response_model=InvitationAccepted,
    dependencies=[Depends(require_csrf)],
)
async def post_accept_invitation(
    payload: InvitationAccept,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvitationAccepted:
    invitation, workspace_ids = await accept_invitation(db, user, payload.token)
    return InvitationAccepted(
        organization_id=invitation.organization_id,
        workspace_ids=workspace_ids,
        status=invitation.status,
    )


@router.get("/tenant-context", response_model=TenantContextResponse)
async def resolve_tenant_context(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContextResponse:
    audit_event(
        "organization.switched",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        resource_type="organization",
        resource_id=context.organization_id,
    )
    if context.workspace_id is not None:
        audit_event(
            "workspace.switched",
            actor_user_id=context.user_id,
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            resource_type="workspace",
            resource_id=context.workspace_id,
        )
    return TenantContextResponse(
        user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        organization_membership_id=context.organization_membership_id,
        workspace_membership_id=context.workspace_membership_id,
        organization_role=context.organization_role,
        workspace_role=context.workspace_role,
        correlation_id=context.correlation_id,
    )
