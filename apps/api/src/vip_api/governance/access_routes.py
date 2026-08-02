"""Enterprise permissions APIs: groups, resource sharing, and effective access."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import AuthenticatedContext, get_current_session, require_csrf
from vip_api.database.session import get_db_session
from vip_api.governance import group_service, principals, resource_access_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_any_permission, require_permission
from vip_api.governance.models import Group
from vip_api.schemas.access import (
    EffectiveAccessResponse,
    GroupArchiveRequest,
    GroupCreate,
    GroupMemberAdd,
    GroupMemberResponse,
    GroupResponse,
    GroupUpdate,
    PrincipalResponse,
    ResourceEntryResponse,
    ResourceGrantRequest,
    ResourceSearchItem,
    ResourceTypeInfo,
    SimulateRequest,
)

router = APIRouter(tags=["access"])


async def _group_response(db: AsyncSession, group: Group) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        slug=group.slug,
        description=group.description,
        workspace_id=group.workspace_id,
        archived_at=group.archived_at,
        row_version=group.row_version,
        member_count=await group_service.member_count(db, group.id),
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


# --------------------------------------------------------------------------- groups


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    context: Annotated[AuthorizationContext, Depends(require_permission("group.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    include_archived: bool = Query(default=False),
) -> list[GroupResponse]:
    groups = await group_service.list_groups(db, context, include_archived=include_archived)
    return [await _group_response(db, group) for group in groups]


@router.post("/groups", response_model=GroupResponse, dependencies=[Depends(require_csrf)])
async def create_group(
    payload: GroupCreate,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.create"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GroupResponse:
    group = await group_service.create_group(
        db,
        context,
        name=payload.name,
        description=payload.description,
        workspace_id=payload.workspace_id,
    )
    return await _group_response(db, group)


@router.get("/groups/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GroupResponse:
    return await _group_response(db, await group_service.get_group(db, context, group_id))


@router.patch(
    "/groups/{group_id}", response_model=GroupResponse, dependencies=[Depends(require_csrf)]
)
async def update_group(
    group_id: UUID,
    payload: GroupUpdate,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.update"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GroupResponse:
    group = await group_service.update_group(
        db,
        context,
        group_id,
        expected_version=payload.expected_version,
        name=payload.name,
        description=payload.description,
    )
    return await _group_response(db, group)


@router.post(
    "/groups/{group_id}/archive",
    response_model=GroupResponse,
    dependencies=[Depends(require_csrf)],
)
async def archive_group(
    group_id: UUID,
    payload: GroupArchiveRequest,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.update"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GroupResponse:
    group = await group_service.set_archived(
        db, context, group_id, expected_version=payload.expected_version, archived=payload.archived
    )
    return await _group_response(db, group)


@router.delete("/groups/{group_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_group(
    group_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.delete"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    expected_version: int = Query(ge=1),
) -> None:
    await group_service.delete_group(db, context, group_id, expected_version=expected_version)


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_group_members(
    group_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[GroupMemberResponse]:
    members = await group_service.list_members(db, context, group_id)
    return [
        GroupMemberResponse(
            user_id=member.user_id,
            display_name=member.display_name,
            email=member.email,
            username=member.username,
            added_at=member.added_at,
        )
        for member in members
    ]


@router.post("/groups/{group_id}/members", status_code=204, dependencies=[Depends(require_csrf)])
async def add_group_member(
    group_id: UUID,
    payload: GroupMemberAdd,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.members.manage"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await group_service.add_member(db, context, group_id, payload.user_id)


@router.delete(
    "/groups/{group_id}/members/{user_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("group.members.manage"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await group_service.remove_member(db, context, group_id, user_id)


# ---------------------------------------------------------------------- principals


@router.get("/principals/search", response_model=list[PrincipalResponse])
async def search_principals(
    context: Annotated[
        AuthorizationContext,
        Depends(
            require_any_permission(
                "resource.permissions.read",
                "group.members.manage",
                "role.assign",
            )
        ),
    ],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PrincipalResponse]:
    results = await principals.search_principals(db, context, query=q, limit=limit)
    return [
        PrincipalResponse(
            principal_type=item.principal_type,
            id=item.id,
            label=item.label,
            detail=item.detail,
            in_workspace=item.in_workspace,
        )
        for item in results
    ]


# ------------------------------------------------------------------ resource access


@router.get("/resource-types", response_model=list[ResourceTypeInfo])
async def list_resource_types(
    _context: Annotated[
        AuthorizationContext, Depends(require_permission("resource.permissions.read"))
    ],
) -> list[ResourceTypeInfo]:
    return [
        ResourceTypeInfo(
            resource_type=resource_type,
            levels=list(resource_access_service.levels_for(resource_type)),
        )
        for resource_type in resource_access_service.resource_types()
    ]


@router.get("/resources/{resource_type}/search", response_model=list[ResourceSearchItem])
async def search_resources(
    resource_type: str,
    context: Annotated[
        AuthorizationContext, Depends(require_permission("resource.permissions.read"))
    ],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[ResourceSearchItem]:
    rows = await resource_access_service.search_resources(
        db,
        resource_type=resource_type,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        query=q,
        limit=limit,
    )
    return [
        ResourceSearchItem(
            id=row.id,
            name=row.name,
            resource_type=row.resource_type,
            status=row.status,
            owner_user_id=row.owner_user_id,
            workspace_id=row.workspace_id,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


def _entry_response(entry: resource_access_service.ResourceEntryView) -> ResourceEntryResponse:
    return ResourceEntryResponse(
        id=entry.id,
        subject_type=entry.subject_type,
        subject_id=entry.subject_id,
        subject_label=entry.subject_label,
        subject_detail=entry.subject_detail,
        access_level=entry.access_level,
        effect=entry.effect,
        expires_at=entry.expires_at,
        granted_by_user_id=entry.granted_by_user_id,
        created_at=entry.created_at,
    )


@router.get(
    "/resources/{resource_type}/{resource_id}/access",
    response_model=list[ResourceEntryResponse],
)
async def list_access(
    resource_type: str,
    resource_id: UUID,
    context: Annotated[
        AuthorizationContext, Depends(require_permission("resource.permissions.read"))
    ],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ResourceEntryResponse]:
    entries = await resource_access_service.list_resource_entries(
        db, context, resource_type=resource_type, resource_id=resource_id
    )
    return [_entry_response(entry) for entry in entries]


@router.post(
    "/resources/{resource_type}/{resource_id}/access",
    response_model=ResourceEntryResponse,
    dependencies=[Depends(require_csrf)],
)
async def grant_access(
    resource_type: str,
    resource_id: UUID,
    payload: ResourceGrantRequest,
    context: Annotated[
        AuthorizationContext, Depends(require_permission("resource.permissions.manage"))
    ],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResourceEntryResponse:
    entry = await resource_access_service.grant_resource_access(
        db,
        context,
        resource_type=resource_type,
        resource_id=resource_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        access_level=payload.access_level,
        effect=payload.effect,
        expires_at=payload.expires_at,
        is_platform_admin=auth.user.is_platform_admin,
    )
    return ResourceEntryResponse(
        id=entry.id,
        subject_type=entry.subject_type,
        subject_id=entry.subject_id,
        subject_label="",
        subject_detail=None,
        access_level=entry.access_level,
        effect=entry.effect,
        expires_at=entry.expires_at,
        granted_by_user_id=entry.granted_by_user_id,
        created_at=entry.created_at,
    )


@router.delete(
    "/resources/{resource_type}/{resource_id}/access/{entry_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def revoke_access(
    resource_type: str,
    resource_id: UUID,
    entry_id: UUID,
    context: Annotated[
        AuthorizationContext, Depends(require_permission("resource.permissions.manage"))
    ],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await resource_access_service.revoke_resource_access(
        db,
        context,
        resource_type=resource_type,
        resource_id=resource_id,
        entry_id=entry_id,
        is_platform_admin=auth.user.is_platform_admin,
    )


@router.get(
    "/resources/{resource_type}/{resource_id}/effective",
    response_model=EffectiveAccessResponse,
)
async def effective_access(
    resource_type: str,
    resource_id: UUID,
    context: Annotated[
        AuthorizationContext, Depends(require_permission("resource.permissions.read"))
    ],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_id: Annotated[UUID | None, Query()] = None,
) -> EffectiveAccessResponse:
    target = user_id or context.user_id
    is_admin = auth.user.is_platform_admin if target == context.user_id else False
    role_permissions = context.permissions if target == context.user_id else None
    result = await resource_access_service.effective_access(
        db,
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=target,
        is_platform_admin=is_admin,
        role_permissions=role_permissions,
    )
    return EffectiveAccessResponse(
        resource_type=result.resource_type,
        resource_id=result.resource_id,
        user_id=result.user_id,
        level=result.level,
        allowed_levels=result.allowed_levels,
        source=result.source,
        reason=result.reason,
    )


@router.post(
    "/resources/{resource_type}/{resource_id}/simulate",
    response_model=EffectiveAccessResponse,
    dependencies=[Depends(require_csrf)],
)
async def simulate_access(
    resource_type: str,
    resource_id: UUID,
    payload: SimulateRequest,
    context: Annotated[
        AuthorizationContext, Depends(require_permission("resource.permissions.read"))
    ],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> EffectiveAccessResponse:
    result = await resource_access_service.effective_access(
        db,
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=payload.user_id,
        is_platform_admin=False,
        role_permissions=None,
    )
    return EffectiveAccessResponse(
        resource_type=result.resource_type,
        resource_id=result.resource_id,
        user_id=result.user_id,
        level=result.level,
        allowed_levels=result.allowed_levels,
        source=result.source,
        reason=result.reason,
    )
