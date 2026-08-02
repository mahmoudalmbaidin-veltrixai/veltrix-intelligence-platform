"""Group lifecycle and membership management with audit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User
from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Group, GroupMembership
from vip_api.tenancy.models import MembershipStatus, OrganizationMembership


@dataclass(frozen=True, slots=True)
class GroupMemberView:
    user_id: UUID
    display_name: str
    email: str | None
    username: str
    added_at: datetime


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")[:120]
    return normalized or f"group-{uuid4().hex[:8]}"


def _not_found() -> ApplicationError:
    return ApplicationError(
        code="GROUP_NOT_FOUND", message="The requested group was not found.", status_code=404
    )


def _check_version(group: Group, expected: int) -> None:
    if group.row_version != expected:
        raise ApplicationError(
            code="GROUP_VERSION_CONFLICT",
            message="This group was updated by another user. Reload before saving.",
            status_code=409,
        )


async def get_group(db: AsyncSession, context: AuthorizationContext, group_id: UUID) -> Group:
    group = await db.scalar(
        select(Group).where(
            Group.id == group_id,
            Group.organization_id == context.organization_id,
            Group.deleted_at.is_(None),
        )
    )
    if group is None:
        raise _not_found()
    return group


async def list_groups(
    db: AsyncSession, context: AuthorizationContext, *, include_archived: bool = False
) -> list[Group]:
    statement = select(Group).where(
        Group.organization_id == context.organization_id, Group.deleted_at.is_(None)
    )
    if not include_archived:
        statement = statement.where(Group.archived_at.is_(None))
    rows = await db.scalars(statement.order_by(Group.name))
    return list(rows.all())


async def member_count(db: AsyncSession, group_id: UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(GroupMembership)
        .where(GroupMembership.group_id == group_id)
    )
    return int(count or 0)


async def create_group(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    name: str,
    description: str = "",
    workspace_id: UUID | None = None,
) -> Group:
    slug = _slug(name)
    group = Group(
        id=uuid4(),
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        name=name.strip(),
        slug=slug,
        description=description.strip(),
        created_by_user_id=context.user_id,
    )
    db.add(group)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        group.slug = f"{slug}-{uuid4().hex[:6]}"
        db.add(group)
        await db.flush()
    await record_audit(
        db,
        "group.created",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="group",
        resource_id=group.id,
        metadata={"name": group.name, "slug": group.slug},
    )
    await db.commit()
    await db.refresh(group)
    return group


async def update_group(
    db: AsyncSession,
    context: AuthorizationContext,
    group_id: UUID,
    *,
    expected_version: int,
    name: str | None = None,
    description: str | None = None,
) -> Group:
    group = await get_group(db, context, group_id)
    _check_version(group, expected_version)
    before = {"name": group.name, "description": group.description}
    if name is not None:
        group.name = name.strip()
    if description is not None:
        group.description = description.strip()
    group.row_version += 1
    await record_audit(
        db,
        "group.updated",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="group",
        resource_id=group.id,
        metadata={
            "before": before,
            "after": {"name": group.name, "description": group.description},
        },
    )
    await db.commit()
    await db.refresh(group)
    return group


async def set_archived(
    db: AsyncSession,
    context: AuthorizationContext,
    group_id: UUID,
    *,
    expected_version: int,
    archived: bool,
) -> Group:
    group = await get_group(db, context, group_id)
    _check_version(group, expected_version)
    group.archived_at = datetime.now(UTC) if archived else None
    group.row_version += 1
    await record_audit(
        db,
        "group.archived" if archived else "group.restored",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="group",
        resource_id=group.id,
    )
    await db.commit()
    await db.refresh(group)
    return group


async def delete_group(
    db: AsyncSession, context: AuthorizationContext, group_id: UUID, *, expected_version: int
) -> None:
    group = await get_group(db, context, group_id)
    _check_version(group, expected_version)
    group.deleted_at = datetime.now(UTC)
    group.row_version += 1
    await record_audit(
        db,
        "group.deleted",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="group",
        resource_id=group.id,
    )
    await db.commit()


async def list_members(
    db: AsyncSession, context: AuthorizationContext, group_id: UUID
) -> list[GroupMemberView]:
    await get_group(db, context, group_id)
    rows = (
        await db.execute(
            select(User, GroupMembership.created_at)
            .join(GroupMembership, GroupMembership.user_id == User.id)
            .where(GroupMembership.group_id == group_id)
            .order_by(User.display_name)
        )
    ).all()
    return [
        GroupMemberView(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            username=user.username,
            added_at=added_at,
        )
        for user, added_at in rows
    ]


async def add_member(
    db: AsyncSession, context: AuthorizationContext, group_id: UUID, user_id: UUID
) -> None:
    group = await get_group(db, context, group_id)
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == context.organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise ApplicationError(
            code="USER_NOT_IN_ORGANIZATION",
            message="Only active organization members can join a group.",
            status_code=422,
        )
    existing = await db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id, GroupMembership.user_id == user_id
        )
    )
    if existing is not None:
        return
    db.add(
        GroupMembership(
            id=uuid4(), group_id=group.id, user_id=user_id, added_by_user_id=context.user_id
        )
    )
    await record_audit(
        db,
        "group.member.added",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="group",
        resource_id=group.id,
        metadata={"user_id": str(user_id)},
    )
    await db.commit()


async def remove_member(
    db: AsyncSession, context: AuthorizationContext, group_id: UUID, user_id: UUID
) -> None:
    group = await get_group(db, context, group_id)
    membership = await db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id, GroupMembership.user_id == user_id
        )
    )
    if membership is None:
        raise ApplicationError(
            code="GROUP_MEMBER_NOT_FOUND", message="The user is not in this group.", status_code=404
        )
    await db.delete(membership)
    await record_audit(
        db,
        "group.member.removed",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="group",
        resource_id=group.id,
        metadata={"user_id": str(user_id)},
    )
    await db.commit()
