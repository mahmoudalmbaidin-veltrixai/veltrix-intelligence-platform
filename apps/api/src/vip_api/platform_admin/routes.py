"""Platform super-admin console API (operator-only, cross-tenant)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import require_csrf
from vip_api.auth.models import User
from vip_api.auth.password import PasswordService
from vip_api.core.config import Settings, get_settings
from vip_api.database.session import get_db_session
from vip_api.platform_admin import services
from vip_api.platform_admin.dependencies import require_platform_admin
from vip_api.platform_admin.schemas import (
    AddOrgMemberRequest,
    AddWorkspaceMemberRequest,
    AdminResetPasswordRequest,
    CreateOrganizationRequest,
    CreatePlatformUserRequest,
    CreateWorkspaceRequest,
    PlatformOrganizationDetail,
    PlatformOrganizationList,
    PlatformOverview,
    PlatformUserList,
    PlatformUserRow,
    PlatformWorkspaceRow,
    UpdatePlatformUserRequest,
    UserAccessSummary,
)

router = APIRouter(prefix="/platform", tags=["platform-admin"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
PlatformAdmin = Annotated[User, Depends(require_platform_admin)]


def get_password_service(request: Request) -> PasswordService:
    service: PasswordService = request.app.state.password_service
    return service


@router.get("/overview", response_model=PlatformOverview)
async def get_overview(db: DbSession, _admin: PlatformAdmin) -> PlatformOverview:
    return await services.overview(db)


@router.get("/organizations", response_model=PlatformOrganizationList)
async def get_organizations(
    db: DbSession,
    _admin: PlatformAdmin,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> PlatformOrganizationList:
    return await services.list_organizations(db, page=page, page_size=page_size, search=search)


@router.post(
    "/organizations",
    response_model=PlatformOrganizationDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_organization(
    payload: CreateOrganizationRequest,
    db: DbSession,
    admin: PlatformAdmin,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlatformOrganizationDetail:
    return await services.create_organization(
        db, admin, payload, settings.TENANCY_DEFAULT_WORKSPACE_NAME
    )


@router.get("/organizations/{organization_id}", response_model=PlatformOrganizationDetail)
async def get_organization(
    organization_id: UUID, db: DbSession, _admin: PlatformAdmin
) -> PlatformOrganizationDetail:
    return await services.get_organization_detail(db, organization_id)


@router.post(
    "/organizations/{organization_id}/suspend",
    response_model=PlatformOrganizationDetail,
    dependencies=[Depends(require_csrf)],
)
async def suspend_organization(
    organization_id: UUID, db: DbSession, admin: PlatformAdmin
) -> PlatformOrganizationDetail:
    return await services.set_organization_status(db, admin, organization_id, suspend=True)


@router.post(
    "/organizations/{organization_id}/activate",
    response_model=PlatformOrganizationDetail,
    dependencies=[Depends(require_csrf)],
)
async def activate_organization(
    organization_id: UUID, db: DbSession, admin: PlatformAdmin
) -> PlatformOrganizationDetail:
    return await services.set_organization_status(db, admin, organization_id, suspend=False)


@router.get("/users", response_model=PlatformUserList)
async def get_users(
    db: DbSession,
    _admin: PlatformAdmin,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> PlatformUserList:
    return await services.list_users(db, page=page, page_size=page_size, search=search)


@router.post(
    "/users",
    response_model=PlatformUserRow,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_user(
    payload: CreatePlatformUserRequest,
    db: DbSession,
    admin: PlatformAdmin,
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> PlatformUserRow:
    return await services.create_user(db, admin, payload, password_service)


@router.post(
    "/organizations/{organization_id}/members",
    response_model=PlatformUserRow,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_org_member(
    organization_id: UUID,
    payload: AddOrgMemberRequest,
    db: DbSession,
    admin: PlatformAdmin,
) -> PlatformUserRow:
    return await services.add_org_member(db, admin, organization_id, payload)


@router.post(
    "/users/{user_id}/suspend",
    response_model=PlatformUserRow,
    dependencies=[Depends(require_csrf)],
)
async def suspend_user(user_id: UUID, db: DbSession, admin: PlatformAdmin) -> PlatformUserRow:
    return await services.set_user_status(db, admin, user_id, suspend=True)


@router.post(
    "/users/{user_id}/activate",
    response_model=PlatformUserRow,
    dependencies=[Depends(require_csrf)],
)
async def activate_user(user_id: UUID, db: DbSession, admin: PlatformAdmin) -> PlatformUserRow:
    return await services.set_user_status(db, admin, user_id, suspend=False)


@router.get("/users/{user_id}/access-summary", response_model=UserAccessSummary)
async def get_user_access(user_id: UUID, db: DbSession, _admin: PlatformAdmin) -> UserAccessSummary:
    return await services.get_access_summary(db, user_id)


@router.patch(
    "/users/{user_id}",
    response_model=PlatformUserRow,
    dependencies=[Depends(require_csrf)],
)
async def patch_platform_user(
    user_id: UUID,
    payload: UpdatePlatformUserRequest,
    db: DbSession,
    admin: PlatformAdmin,
) -> PlatformUserRow:
    return await services.update_user(db, admin, user_id, payload)


@router.post(
    "/users/{user_id}/reset-password",
    response_model=PlatformUserRow,
    dependencies=[Depends(require_csrf)],
)
async def post_reset_password(
    user_id: UUID,
    payload: AdminResetPasswordRequest,
    db: DbSession,
    admin: PlatformAdmin,
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> PlatformUserRow:
    return await services.reset_user_password(db, admin, user_id, password_service, payload)


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/members",
    response_model=UserAccessSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_workspace_member(
    organization_id: UUID,
    workspace_id: UUID,
    payload: AddWorkspaceMemberRequest,
    db: DbSession,
    admin: PlatformAdmin,
) -> UserAccessSummary:
    return await services.add_workspace_member(db, admin, organization_id, workspace_id, payload)


@router.delete(
    "/organizations/{organization_id}/members/by-user/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_org_access(
    organization_id: UUID,
    user_id: UUID,
    db: DbSession,
    admin: PlatformAdmin,
) -> Response:
    await services.remove_org_access(db, admin, organization_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/organizations/{organization_id}/workspaces/{workspace_id}/members/by-user/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_workspace_access(
    organization_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
    db: DbSession,
    admin: PlatformAdmin,
) -> Response:
    await services.remove_workspace_access(db, admin, organization_id, workspace_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/organizations/{organization_id}/workspaces",
    response_model=PlatformWorkspaceRow,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_workspace(
    organization_id: UUID,
    payload: CreateWorkspaceRequest,
    db: DbSession,
    admin: PlatformAdmin,
) -> PlatformWorkspaceRow:
    return await services.create_workspace(db, admin, organization_id, payload)


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/suspend",
    response_model=PlatformWorkspaceRow,
    dependencies=[Depends(require_csrf)],
)
async def suspend_workspace(
    organization_id: UUID, workspace_id: UUID, db: DbSession, admin: PlatformAdmin
) -> PlatformWorkspaceRow:
    return await services.set_workspace_status(
        db, admin, organization_id, workspace_id, suspend=True
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/activate",
    response_model=PlatformWorkspaceRow,
    dependencies=[Depends(require_csrf)],
)
async def activate_workspace(
    organization_id: UUID, workspace_id: UUID, db: DbSession, admin: PlatformAdmin
) -> PlatformWorkspaceRow:
    return await services.set_workspace_status(
        db, admin, organization_id, workspace_id, suspend=False
    )
