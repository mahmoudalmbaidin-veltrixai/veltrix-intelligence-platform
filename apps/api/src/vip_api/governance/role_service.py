"""Tenant-configurable custom role lifecycle (Enterprise permissions — Slice C).

Custom roles reuse the shared ``roles`` / ``role_permissions`` tables so there is
no second RBAC system. A custom role is a tenant-owned row (``is_system = False``,
``organization_id`` populated) whose permissions are drawn from the authoritative
catalog. System roles remain protected and immutable through this service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import (
    GroupRoleAssignment,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from vip_api.governance.policies import SYSTEM_PERMISSION_KEYS

ROLE_SCOPES = ("organization", "workspace")
_CUSTOM_ROLE_PRIORITY = 500


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "role"


def _not_found() -> ApplicationError:
    return ApplicationError(
        code="ROLE_NOT_FOUND", message="The role was not found.", status_code=404
    )


def _protected() -> ApplicationError:
    return ApplicationError(
        code="ROLE_PROTECTED",
        message="System roles cannot be modified or deleted.",
        status_code=409,
    )


def _check_version(role: Role, expected: int) -> None:
    if role.row_version != expected:
        raise ApplicationError(
            code="ROLE_VERSION_CONFLICT",
            message="This role was modified by someone else. Reload and try again.",
            status_code=409,
        )


@dataclass(frozen=True, slots=True)
class RoleView:
    role: Role
    permission_keys: list[str]
    assignment_count: int


async def _permission_keys(db: AsyncSession, role_id: UUID) -> list[str]:
    keys = await db.scalars(
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
        .order_by(Permission.key)
    )
    return list(keys.all())


async def assignment_count(db: AsyncSession, role_id: UUID) -> int:
    users = await db.scalar(
        select(func.count())
        .select_from(UserRoleAssignment)
        .where(UserRoleAssignment.role_id == role_id)
    )
    groups = await db.scalar(
        select(func.count())
        .select_from(GroupRoleAssignment)
        .where(GroupRoleAssignment.role_id == role_id)
    )
    return int(users or 0) + int(groups or 0)


async def get_role(db: AsyncSession, context: AuthorizationContext, role_id: UUID) -> Role:
    role = await db.scalar(
        select(Role).where(
            Role.id == role_id,
            Role.deleted_at.is_(None),
            or_(Role.organization_id.is_(None), Role.organization_id == context.organization_id),
        )
    )
    if role is None:
        raise _not_found()
    return role


async def list_roles(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    include_system: bool = True,
    include_archived: bool = False,
    scope: str | None = None,
    query: str | None = None,
) -> list[Role]:
    conditions: list[Any] = [Role.deleted_at.is_(None)]
    if include_system:
        conditions.append(
            or_(Role.organization_id.is_(None), Role.organization_id == context.organization_id)
        )
    else:
        conditions.append(Role.organization_id == context.organization_id)
    if not include_archived:
        conditions.append(Role.archived_at.is_(None))
    if scope in ROLE_SCOPES:
        conditions.append(Role.scope == scope)
    if query:
        like = f"%{query.strip().lower()}%"
        conditions.append(func.lower(Role.name).like(like))
    rows = await db.scalars(
        select(Role)
        .where(*conditions)
        .order_by(Role.is_system.desc(), Role.priority.desc(), Role.name)
    )
    return list(rows.all())


async def role_view(db: AsyncSession, role: Role) -> RoleView:
    return RoleView(
        role=role,
        permission_keys=await _permission_keys(db, role.id),
        assignment_count=await assignment_count(db, role.id),
    )


def _validate_permissions(
    context: AuthorizationContext,
    scope: str,
    permission_keys: set[str],
    catalog: dict[str, Permission],
    *,
    is_platform_admin: bool,
) -> None:
    unknown = permission_keys - SYSTEM_PERMISSION_KEYS
    if unknown:
        raise ApplicationError(
            code="PERMISSION_UNKNOWN",
            message=f"Unknown permissions: {', '.join(sorted(unknown))}.",
            status_code=422,
        )
    if scope == "workspace":
        misscoped = {k for k in permission_keys if catalog[k].scope != "workspace"}
        if misscoped:
            raise ApplicationError(
                code="PERMISSION_SCOPE_INVALID",
                message="Workspace roles may only contain workspace-scoped permissions.",
                status_code=422,
            )
    # Privilege ceiling: an administrator cannot grant permissions they do not
    # themselves hold (prevents custom-role self-escalation). Platform admins are
    # exempt because they already hold every permission.
    if not is_platform_admin:
        escalation = permission_keys - set(context.permissions)
        if escalation:
            raise ApplicationError(
                code="PERMISSION_ESCALATION_DENIED",
                message="You cannot grant permissions you do not hold.",
                status_code=403,
            )


async def _catalog(db: AsyncSession) -> dict[str, Permission]:
    rows = await db.scalars(select(Permission))
    return {row.key: row for row in rows.all()}


async def _apply_permissions(db: AsyncSession, role_id: UUID, permission_keys: set[str]) -> None:
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    if not permission_keys:
        return
    perms = await db.scalars(select(Permission).where(Permission.key.in_(permission_keys)))
    for perm in perms.all():
        db.add(RolePermission(role_id=role_id, permission_id=perm.id))


async def create_role(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    name: str,
    description: str,
    scope: str,
    permission_keys: set[str],
    is_platform_admin: bool = False,
) -> Role:
    if scope not in ROLE_SCOPES:
        raise ApplicationError(
            code="ROLE_SCOPE_INVALID", message="Unknown role scope.", status_code=422
        )
    catalog = await _catalog(db)
    _validate_permissions(
        context, scope, permission_keys, catalog, is_platform_admin=is_platform_admin
    )
    slug = _slug(name)
    clash = await db.scalar(
        select(Role).where(
            Role.organization_id == context.organization_id,
            Role.slug == slug,
            Role.deleted_at.is_(None),
        )
    )
    if clash is not None:
        raise ApplicationError(
            code="ROLE_NAME_TAKEN",
            message="A role with this name already exists.",
            status_code=409,
        )
    role = Role(
        id=uuid4(),
        key=f"org:{context.organization_id}:{slug}:{uuid4().hex[:8]}",
        name=name.strip(),
        description=description.strip(),
        scope=scope,
        is_system=False,
        is_assignable=True,
        priority=_CUSTOM_ROLE_PRIORITY,
        organization_id=context.organization_id,
        workspace_id=None,
        slug=slug,
        status="active",
        is_editable=True,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
        row_version=1,
    )
    db.add(role)
    await db.flush()
    await _apply_permissions(db, role.id, permission_keys)
    await record_audit(
        db,
        "role.created",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="role",
        resource_id=role.id,
        metadata={"name": role.name, "scope": scope, "permissions": sorted(permission_keys)},
    )
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(
    db: AsyncSession,
    context: AuthorizationContext,
    role_id: UUID,
    *,
    expected_version: int,
    name: str | None = None,
    description: str | None = None,
    permission_keys: set[str] | None = None,
    is_platform_admin: bool = False,
) -> Role:
    role = await get_role(db, context, role_id)
    if role.is_system or role.organization_id is None:
        raise _protected()
    _check_version(role, expected_version)
    before = {"name": role.name, "permissions": await _permission_keys(db, role.id)}
    catalog = await _catalog(db)
    if name is not None and name.strip() and name.strip() != role.name:
        slug = _slug(name)
        clash = await db.scalar(
            select(Role).where(
                Role.organization_id == context.organization_id,
                Role.slug == slug,
                Role.id != role.id,
                Role.deleted_at.is_(None),
            )
        )
        if clash is not None:
            raise ApplicationError(
                code="ROLE_NAME_TAKEN",
                message="A role with this name already exists.",
                status_code=409,
            )
        role.name = name.strip()
        role.slug = slug
    if description is not None:
        role.description = description.strip()
    if permission_keys is not None:
        _validate_permissions(
            context, role.scope, permission_keys, catalog, is_platform_admin=is_platform_admin
        )
        await _apply_permissions(db, role.id, permission_keys)
    role.updated_by_user_id = context.user_id
    role.row_version += 1
    await record_audit(
        db,
        "role.updated",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="role",
        resource_id=role.id,
        metadata={
            "before": before,
            "after": {
                "name": role.name,
                "permissions": sorted(permission_keys)
                if permission_keys is not None
                else before["permissions"],
            },
        },
    )
    await db.commit()
    await db.refresh(role)
    return role


async def clone_role(
    db: AsyncSession,
    context: AuthorizationContext,
    role_id: UUID,
    *,
    name: str,
    is_platform_admin: bool = False,
) -> Role:
    source = await get_role(db, context, role_id)
    keys = set(await _permission_keys(db, source.id))
    return await create_role(
        db,
        context,
        name=name,
        description=source.description,
        scope=source.scope,
        permission_keys=keys,
        is_platform_admin=is_platform_admin,
    )


async def set_archived(
    db: AsyncSession,
    context: AuthorizationContext,
    role_id: UUID,
    *,
    expected_version: int,
    archived: bool,
) -> Role:
    role = await get_role(db, context, role_id)
    if role.is_system or role.organization_id is None:
        raise _protected()
    _check_version(role, expected_version)
    role.archived_at = datetime.now(UTC) if archived else None
    role.status = "archived" if archived else "active"
    role.updated_by_user_id = context.user_id
    role.row_version += 1
    await record_audit(
        db,
        "role.archived" if archived else "role.restored",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="role",
        resource_id=role.id,
        metadata={"name": role.name},
    )
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(
    db: AsyncSession,
    context: AuthorizationContext,
    role_id: UUID,
    *,
    expected_version: int,
) -> None:
    role = await get_role(db, context, role_id)
    if role.is_system or role.organization_id is None:
        raise _protected()
    _check_version(role, expected_version)
    # Remove assignments so no user/group keeps a dangling grant, then soft-delete.
    await db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.role_id == role.id))
    await db.execute(delete(GroupRoleAssignment).where(GroupRoleAssignment.role_id == role.id))
    role.deleted_at = datetime.now(UTC)
    role.status = "deleted"
    role.updated_by_user_id = context.user_id
    role.row_version += 1
    await record_audit(
        db,
        "role.deleted",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="role",
        resource_id=role.id,
        metadata={"name": role.name},
    )
    await db.commit()
