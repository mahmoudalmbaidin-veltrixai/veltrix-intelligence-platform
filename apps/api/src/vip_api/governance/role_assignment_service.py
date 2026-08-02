"""Role assignment + bulk operations (Enterprise permissions — Slice C).

Assigns system or custom roles to users and groups at organization or workspace
scope. Assignment scope is derived from the role's own scope so a workspace role
is always workspace-bound and an organization role is org-wide. Every mutation is
tenant-isolated and audited; bulk operations return per-item outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User
from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Group, GroupRoleAssignment, Role, UserRoleAssignment
from vip_api.governance.role_service import get_role
from vip_api.tenancy.models import MembershipStatus, OrganizationMembership


@dataclass(frozen=True, slots=True)
class AssignmentView:
    id: UUID
    subject_type: str
    subject_id: UUID
    subject_label: str
    role_id: UUID
    role_name: str
    scope: str
    workspace_id: UUID | None
    created_at: object


@dataclass(frozen=True, slots=True)
class BulkResult:
    subject_id: UUID
    ok: bool
    detail: str


def _assignment_scope(role: Role, context: AuthorizationContext) -> tuple[str, UUID | None]:
    if role.scope == "workspace":
        if context.workspace_id is None:
            raise ApplicationError(
                code="WORKSPACE_REQUIRED",
                message="A workspace context is required to assign a workspace role.",
                status_code=422,
            )
        return "workspace", context.workspace_id
    return "organization", None


async def _require_org_user(db: AsyncSession, context: AuthorizationContext, user_id: UUID) -> User:
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == context.organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise ApplicationError(
            code="SUBJECT_NOT_FOUND",
            message="The user is not an active member of this organization.",
            status_code=422,
        )
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise ApplicationError(
            code="SUBJECT_NOT_FOUND", message="The user was not found.", status_code=422
        )
    return user


async def _require_org_group(
    db: AsyncSession, context: AuthorizationContext, group_id: UUID
) -> Group:
    group = await db.scalar(
        select(Group).where(
            Group.id == group_id,
            Group.organization_id == context.organization_id,
            Group.deleted_at.is_(None),
        )
    )
    if group is None:
        raise ApplicationError(
            code="SUBJECT_NOT_FOUND", message="The group was not found.", status_code=422
        )
    return group


async def assign_user_role(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    role_id: UUID,
    user_id: UUID,
    commit: bool = True,
) -> UserRoleAssignment:
    role = await get_role(db, context, role_id)
    scope, workspace_id = _assignment_scope(role, context)
    await _require_org_user(db, context, user_id)
    existing = await db.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.organization_id == context.organization_id,
            UserRoleAssignment.workspace_id.is_(workspace_id)
            if workspace_id is None
            else UserRoleAssignment.workspace_id == workspace_id,
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id,
        )
    )
    if existing is not None:
        return existing
    assignment = UserRoleAssignment(
        id=uuid4(),
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        role_id=role_id,
        scope=scope,
        assigned_by_user_id=context.user_id,
    )
    db.add(assignment)
    await record_audit(
        db,
        "role.assigned",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="role",
        resource_id=role_id,
        metadata={"subject_type": "user", "subject_id": str(user_id), "scope": scope},
    )
    if commit:
        await db.commit()
        await db.refresh(assignment)
    return assignment


async def assign_group_role(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    role_id: UUID,
    group_id: UUID,
    commit: bool = True,
) -> GroupRoleAssignment:
    role = await get_role(db, context, role_id)
    scope, workspace_id = _assignment_scope(role, context)
    await _require_org_group(db, context, group_id)
    existing = await db.scalar(
        select(GroupRoleAssignment).where(
            GroupRoleAssignment.organization_id == context.organization_id,
            GroupRoleAssignment.workspace_id.is_(workspace_id)
            if workspace_id is None
            else GroupRoleAssignment.workspace_id == workspace_id,
            GroupRoleAssignment.group_id == group_id,
            GroupRoleAssignment.role_id == role_id,
        )
    )
    if existing is not None:
        return existing
    assignment = GroupRoleAssignment(
        id=uuid4(),
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        group_id=group_id,
        role_id=role_id,
        scope=scope,
        assigned_by_user_id=context.user_id,
    )
    db.add(assignment)
    await record_audit(
        db,
        "role.assigned",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="role",
        resource_id=role_id,
        metadata={"subject_type": "group", "subject_id": str(group_id), "scope": scope},
    )
    if commit:
        await db.commit()
        await db.refresh(assignment)
    return assignment


async def unassign_user_role(
    db: AsyncSession, context: AuthorizationContext, assignment_id: UUID
) -> None:
    assignment = await db.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.id == assignment_id,
            UserRoleAssignment.organization_id == context.organization_id,
        )
    )
    if assignment is None:
        raise ApplicationError(
            code="ASSIGNMENT_NOT_FOUND", message="The assignment was not found.", status_code=404
        )
    await db.delete(assignment)
    await record_audit(
        db,
        "role.unassigned",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=assignment.workspace_id,
        resource_type="role",
        resource_id=assignment.role_id,
        metadata={"subject_type": "user", "subject_id": str(assignment.user_id)},
    )
    await db.commit()


async def unassign_group_role(
    db: AsyncSession, context: AuthorizationContext, assignment_id: UUID
) -> None:
    assignment = await db.scalar(
        select(GroupRoleAssignment).where(
            GroupRoleAssignment.id == assignment_id,
            GroupRoleAssignment.organization_id == context.organization_id,
        )
    )
    if assignment is None:
        raise ApplicationError(
            code="ASSIGNMENT_NOT_FOUND", message="The assignment was not found.", status_code=404
        )
    await db.delete(assignment)
    await record_audit(
        db,
        "role.unassigned",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=assignment.workspace_id,
        resource_type="role",
        resource_id=assignment.role_id,
        metadata={"subject_type": "group", "subject_id": str(assignment.group_id)},
    )
    await db.commit()


async def list_role_assignments(
    db: AsyncSession, context: AuthorizationContext, role_id: UUID
) -> list[AssignmentView]:
    await get_role(db, context, role_id)
    views: list[AssignmentView] = []
    user_rows = list(
        (
            await db.scalars(
                select(UserRoleAssignment).where(
                    UserRoleAssignment.role_id == role_id,
                    UserRoleAssignment.organization_id == context.organization_id,
                )
            )
        ).all()
    )
    role = await db.scalar(select(Role).where(Role.id == role_id))
    role_name = role.name if role else ""
    if user_rows:
        users = {
            u.id: u
            for u in (
                await db.scalars(select(User).where(User.id.in_([r.user_id for r in user_rows])))
            ).all()
        }
        for row in user_rows:
            user = users.get(row.user_id)
            views.append(
                AssignmentView(
                    id=row.id,
                    subject_type="user",
                    subject_id=row.user_id,
                    subject_label=user.display_name if user else "Unknown user",
                    role_id=role_id,
                    role_name=role_name,
                    scope=row.scope,
                    workspace_id=row.workspace_id,
                    created_at=row.created_at,
                )
            )
    group_rows = list(
        (
            await db.scalars(
                select(GroupRoleAssignment).where(
                    GroupRoleAssignment.role_id == role_id,
                    GroupRoleAssignment.organization_id == context.organization_id,
                )
            )
        ).all()
    )
    if group_rows:
        groups = {
            g.id: g
            for g in (
                await db.scalars(
                    select(Group).where(Group.id.in_([r.group_id for r in group_rows]))
                )
            ).all()
        }
        for grow in group_rows:
            group = groups.get(grow.group_id)
            views.append(
                AssignmentView(
                    id=grow.id,
                    subject_type="group",
                    subject_id=grow.group_id,
                    subject_label=group.name if group else "Unknown group",
                    role_id=role_id,
                    role_name=role_name,
                    scope=grow.scope,
                    workspace_id=grow.workspace_id,
                    created_at=grow.created_at,
                )
            )
    views.sort(key=lambda v: (v.subject_type, v.subject_label.lower()))
    return views


async def bulk_assign_role(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    role_id: UUID,
    user_ids: list[UUID],
    group_ids: list[UUID],
) -> list[BulkResult]:
    """Assign one role to many users/groups, returning per-item outcomes.

    Each item is validated independently; a failed item never silently drops and
    never aborts the rest. All successful items commit together.
    """
    # Each item is validated before anything is staged, so a rejected item raises
    # without leaving partial state and without a session-wide rollback that would
    # discard earlier successes. Successful items commit together at the end.
    results: list[BulkResult] = []
    for user_id in user_ids:
        try:
            await assign_user_role(db, context, role_id=role_id, user_id=user_id, commit=False)
            results.append(BulkResult(user_id, True, "assigned"))
        except ApplicationError as exc:
            results.append(BulkResult(user_id, False, exc.code))
    for group_id in group_ids:
        try:
            await assign_group_role(db, context, role_id=role_id, group_id=group_id, commit=False)
            results.append(BulkResult(group_id, True, "assigned"))
        except ApplicationError as exc:
            results.append(BulkResult(group_id, False, exc.code))
    await db.commit()
    return results
