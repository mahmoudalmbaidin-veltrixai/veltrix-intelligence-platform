"""Principal (user + group) search for sharing and assignment dialogs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Group
from vip_api.tenancy.models import MembershipStatus, OrganizationMembership, WorkspaceMembership


@dataclass(frozen=True, slots=True)
class PrincipalResult:
    principal_type: str  # "user" | "group"
    id: UUID
    label: str
    detail: str | None
    in_workspace: bool


async def search_principals(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    query: str = "",
    limit: int = 20,
) -> list[PrincipalResult]:
    term = f"%{query.strip()[:80]}%"
    results: list[PrincipalResult] = []

    workspace_user_ids: set[UUID] = set()
    if context.workspace_id is not None:
        rows = await db.scalars(
            select(WorkspaceMembership.user_id).where(
                WorkspaceMembership.workspace_id == context.workspace_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
            )
        )
        workspace_user_ids = set(rows.all())

    user_statement = (
        select(User)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(
            OrganizationMembership.organization_id == context.organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
        .order_by(User.display_name)
        .limit(limit)
    )
    if query.strip():
        user_statement = user_statement.where(
            or_(
                User.display_name.ilike(term),
                User.email.ilike(term),
                User.username.ilike(term),
            )
        )
    for user in (await db.scalars(user_statement)).all():
        results.append(
            PrincipalResult(
                principal_type="user",
                id=user.id,
                label=user.display_name,
                detail=user.email or user.username,
                in_workspace=user.id in workspace_user_ids,
            )
        )

    group_statement = (
        select(Group)
        .where(
            Group.organization_id == context.organization_id,
            Group.deleted_at.is_(None),
            Group.archived_at.is_(None),
        )
        .order_by(Group.name)
        .limit(limit)
    )
    if query.strip():
        group_statement = group_statement.where(Group.name.ilike(term))
    for group in (await db.scalars(group_statement)).all():
        results.append(
            PrincipalResult(
                principal_type="group",
                id=group.id,
                label=group.name,
                detail="Group",
                in_workspace=group.workspace_id in (None, context.workspace_id),
            )
        )
    return results
