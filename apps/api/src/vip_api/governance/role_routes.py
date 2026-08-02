"""Custom role, permission-catalog, and role-assignment APIs (Slice C)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import AuthenticatedContext, get_current_session, require_csrf
from vip_api.database.session import get_db_session
from vip_api.governance import role_assignment_service, role_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_permission
from vip_api.governance.models import Permission, Role
from vip_api.schemas.access import (
    BulkResultItem,
    BulkRoleAssignRequest,
    PermissionCatalogItem,
    RoleArchiveRequest,
    RoleAssignmentResponse,
    RoleAssignRequest,
    RoleCloneRequest,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)

router = APIRouter(tags=["roles"])


async def _role_response(db: AsyncSession, role: Role) -> RoleResponse:
    view = await role_service.role_view(db, role)
    return RoleResponse(
        id=role.id,
        name=role.name,
        slug=role.slug,
        description=role.description,
        scope=role.scope,
        status=role.status,
        is_system=role.is_system,
        is_editable=role.is_editable,
        organization_id=role.organization_id,
        workspace_id=role.workspace_id,
        priority=role.priority,
        permission_keys=view.permission_keys,
        assignment_count=view.assignment_count,
        row_version=role.row_version,
        archived_at=role.archived_at,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/permission-catalog", response_model=list[PermissionCatalogItem])
async def permission_catalog(
    _context: Annotated[AuthorizationContext, Depends(require_permission("role.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PermissionCatalogItem]:
    rows = await db.scalars(select(Permission).order_by(Permission.category, Permission.key))
    return [
        PermissionCatalogItem(
            key=row.key,
            name=row.name,
            description=row.description or "",
            scope=row.scope,
            category=row.category,
        )
        for row in rows.all()
    ]


@router.get("/custom-roles", response_model=list[RoleResponse])
async def list_roles(
    context: Annotated[AuthorizationContext, Depends(require_permission("role.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    include_system: bool = Query(default=True),
    include_archived: bool = Query(default=False),
    scope: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> list[RoleResponse]:
    roles = await role_service.list_roles(
        db,
        context,
        include_system=include_system,
        include_archived=include_archived,
        scope=scope,
        query=q,
    )
    return [await _role_response(db, role) for role in roles]


@router.post("/custom-roles", response_model=RoleResponse, dependencies=[Depends(require_csrf)])
async def create_role(
    payload: RoleCreate,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.create"))],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    role = await role_service.create_role(
        db,
        context,
        name=payload.name,
        description=payload.description,
        scope=payload.scope,
        permission_keys=set(payload.permission_keys),
        is_platform_admin=auth.user.is_platform_admin,
    )
    return await _role_response(db, role)


@router.get("/custom-roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    return await _role_response(db, await role_service.get_role(db, context, role_id))


@router.patch(
    "/custom-roles/{role_id}", response_model=RoleResponse, dependencies=[Depends(require_csrf)]
)
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.update"))],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    role = await role_service.update_role(
        db,
        context,
        role_id,
        expected_version=payload.expected_version,
        name=payload.name,
        description=payload.description,
        permission_keys=set(payload.permission_keys)
        if payload.permission_keys is not None
        else None,
        is_platform_admin=auth.user.is_platform_admin,
    )
    return await _role_response(db, role)


@router.post(
    "/custom-roles/{role_id}/clone",
    response_model=RoleResponse,
    dependencies=[Depends(require_csrf)],
)
async def clone_role(
    role_id: UUID,
    payload: RoleCloneRequest,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.create"))],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    role = await role_service.clone_role(
        db, context, role_id, name=payload.name, is_platform_admin=auth.user.is_platform_admin
    )
    return await _role_response(db, role)


@router.post(
    "/custom-roles/{role_id}/archive",
    response_model=RoleResponse,
    dependencies=[Depends(require_csrf)],
)
async def archive_role(
    role_id: UUID,
    payload: RoleArchiveRequest,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.update"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    role = await role_service.set_archived(
        db, context, role_id, expected_version=payload.expected_version, archived=payload.archived
    )
    return await _role_response(db, role)


@router.delete("/custom-roles/{role_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_role(
    role_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.delete"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    expected_version: int = Query(ge=1),
) -> None:
    await role_service.delete_role(db, context, role_id, expected_version=expected_version)


def _assignment_response(item: role_assignment_service.AssignmentView) -> RoleAssignmentResponse:
    return RoleAssignmentResponse(
        id=item.id,
        subject_type=item.subject_type,
        subject_id=item.subject_id,
        subject_label=item.subject_label,
        role_id=item.role_id,
        role_name=item.role_name,
        scope=item.scope,
        workspace_id=item.workspace_id,
        created_at=item.created_at,
    )


@router.get("/custom-roles/{role_id}/assignments", response_model=list[RoleAssignmentResponse])
async def list_assignments(
    role_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RoleAssignmentResponse]:
    items = await role_assignment_service.list_role_assignments(db, context, role_id)
    return [_assignment_response(item) for item in items]


@router.post(
    "/custom-roles/{role_id}/assignments",
    response_model=RoleAssignmentResponse,
    dependencies=[Depends(require_csrf)],
)
async def assign_role(
    role_id: UUID,
    payload: RoleAssignRequest,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.assign"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleAssignmentResponse:
    if payload.subject_type == "user":
        await role_assignment_service.assign_user_role(
            db, context, role_id=role_id, user_id=payload.subject_id
        )
    else:
        await role_assignment_service.assign_group_role(
            db, context, role_id=role_id, group_id=payload.subject_id
        )
    items = await role_assignment_service.list_role_assignments(db, context, role_id)
    match = next(
        (
            i
            for i in items
            if i.subject_id == payload.subject_id and i.subject_type == payload.subject_type
        ),
        None,
    )
    assert match is not None
    return _assignment_response(match)


@router.post(
    "/custom-roles/{role_id}/assignments/bulk",
    response_model=list[BulkResultItem],
    dependencies=[Depends(require_csrf)],
)
async def bulk_assign(
    role_id: UUID,
    payload: BulkRoleAssignRequest,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.assign"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[BulkResultItem]:
    results = await role_assignment_service.bulk_assign_role(
        db, context, role_id=role_id, user_ids=payload.user_ids, group_ids=payload.group_ids
    )
    return [BulkResultItem(subject_id=r.subject_id, ok=r.ok, detail=r.detail) for r in results]


@router.delete(
    "/custom-roles/{role_id}/assignments/{assignment_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def unassign_role(
    role_id: UUID,
    assignment_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("role.assign"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    subject_type: str = Query(pattern="^(user|group)$"),
) -> None:
    if subject_type == "user":
        await role_assignment_service.unassign_user_role(db, context, assignment_id)
    else:
        await role_assignment_service.unassign_group_role(db, context, assignment_id)
