"""Tenant-filtered persistence APIs; tenant-owned access is never unscoped."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User
from vip_api.governance.models import Role
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


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(
        self, user_id: UUID
    ) -> list[tuple[Organization, OrganizationMembership]]:
        statement = (
            select(Organization, OrganizationMembership)
            .join(
                OrganizationMembership,
                OrganizationMembership.organization_id == Organization.id,
            )
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
                Organization.status == OrganizationStatus.ACTIVE,
                Organization.deleted_at.is_(None),
            )
            .order_by(Organization.name, Organization.id)
        )
        return list((await self.session.execute(statement)).tuples().all())

    async def get_authorized(
        self, organization_id: UUID, user_id: UUID, *, active_only: bool = True
    ) -> tuple[Organization, OrganizationMembership] | None:
        conditions = [
            Organization.id == organization_id,
            Organization.deleted_at.is_(None),
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        ]
        if active_only:
            conditions.append(Organization.status == OrganizationStatus.ACTIVE)
        statement = (
            select(Organization, OrganizationMembership)
            .join(
                OrganizationMembership,
                OrganizationMembership.organization_id == Organization.id,
            )
            .where(*conditions)
        )
        return (await self.session.execute(statement)).tuples().one_or_none()

    async def slug_exists(self, slug: str, *, excluding_id: UUID | None = None) -> bool:
        statement: Select[tuple[UUID]] = select(Organization.id).where(
            Organization.slug == slug, Organization.deleted_at.is_(None)
        )
        if excluding_id is not None:
            statement = statement.where(Organization.id != excluding_id)
        return await self.session.scalar(statement) is not None


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(
        self, organization_id: UUID, user_id: UUID, *, include_archived: bool = False
    ) -> list[Workspace]:
        status_condition = (
            Workspace.status != WorkspaceStatus.DELETED
            if include_archived
            else Workspace.status == WorkspaceStatus.ACTIVE
        )
        statement = (
            select(Workspace)
            .join(
                WorkspaceMembership,
                (WorkspaceMembership.organization_id == Workspace.organization_id)
                & (WorkspaceMembership.workspace_id == Workspace.id),
            )
            .where(
                Workspace.organization_id == organization_id,
                status_condition,
                Workspace.deleted_at.is_(None),
                WorkspaceMembership.organization_id == organization_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Workspace.is_default.desc(), Workspace.name, Workspace.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_authorized(
        self, organization_id: UUID, workspace_id: UUID, user_id: UUID
    ) -> tuple[Workspace, WorkspaceMembership] | None:
        statement = (
            select(Workspace, WorkspaceMembership)
            .join(
                WorkspaceMembership,
                (WorkspaceMembership.organization_id == Workspace.organization_id)
                & (WorkspaceMembership.workspace_id == Workspace.id),
            )
            .where(
                Workspace.id == workspace_id,
                Workspace.organization_id == organization_id,
                Workspace.status == WorkspaceStatus.ACTIVE,
                Workspace.deleted_at.is_(None),
                WorkspaceMembership.organization_id == organization_id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
            )
        )
        return (await self.session.execute(statement)).tuples().one_or_none()

    async def get_in_organization(
        self, organization_id: UUID, workspace_id: UUID, *, active_only: bool = False
    ) -> Workspace | None:
        conditions = [
            Workspace.organization_id == organization_id,
            Workspace.id == workspace_id,
            Workspace.deleted_at.is_(None),
        ]
        if active_only:
            conditions.append(Workspace.status == WorkspaceStatus.ACTIVE)
        return cast(
            Workspace | None, await self.session.scalar(select(Workspace).where(*conditions))
        )

    async def slug_exists(
        self, organization_id: UUID, slug: str, *, excluding_id: UUID | None = None
    ) -> bool:
        statement = select(Workspace.id).where(
            Workspace.organization_id == organization_id,
            Workspace.slug == slug,
            Workspace.deleted_at.is_(None),
        )
        if excluding_id is not None:
            statement = statement.where(Workspace.id != excluding_id)
        return await self.session.scalar(statement) is not None

    async def tenant_filtered_update(
        self, organization_id: UUID, workspace_id: UUID, values: dict[str, object]
    ) -> int:
        result = await self.session.execute(
            update(Workspace)
            .where(Workspace.organization_id == organization_id, Workspace.id == workspace_id)
            .values(**values)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def tenant_filtered_delete(self, organization_id: UUID, workspace_id: UUID) -> int:
        result = await self.session.execute(
            delete(Workspace).where(
                Workspace.organization_id == organization_id, Workspace.id == workspace_id
            )
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def count_for_tenant(self, organization_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.organization_id == organization_id, Workspace.deleted_at.is_(None))
        )
        return int(value or 0)


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_organization_members(
        self, organization_id: UUID
    ) -> list[tuple[OrganizationMembership, User]]:
        statement = (
            select(OrganizationMembership, User)
            .join(User, User.id == OrganizationMembership.user_id)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(User.display_name, OrganizationMembership.id)
        )
        return list((await self.session.execute(statement)).tuples().all())

    async def get_organization_membership(
        self, organization_id: UUID, membership_id: UUID, *, for_update: bool = False
    ) -> OrganizationMembership | None:
        statement = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.id == membership_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(OrganizationMembership | None, await self.session.scalar(statement))

    async def get_user_organization_membership(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMembership | None:
        return cast(
            OrganizationMembership | None,
            await self.session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.user_id == user_id,
                )
            ),
        )

    async def active_owner_count(self, organization_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .join(Role, Role.id == OrganizationMembership.role_id)
            .where(
                OrganizationMembership.organization_id == organization_id,
                Role.key == "organization_owner",
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
        )
        return int(value or 0)

    async def revoke_workspace_access(self, organization_id: UUID, user_id: UUID) -> int:
        result = await self.session.execute(
            update(WorkspaceMembership)
            .where(
                WorkspaceMembership.organization_id == organization_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status != MembershipStatus.REMOVED,
            )
            .values(status=MembershipStatus.REMOVED)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def list_workspace_members(
        self, organization_id: UUID, workspace_id: UUID
    ) -> list[tuple[WorkspaceMembership, User]]:
        statement = (
            select(WorkspaceMembership, User)
            .join(User, User.id == WorkspaceMembership.user_id)
            .where(
                WorkspaceMembership.organization_id == organization_id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
            )
            .order_by(User.display_name, WorkspaceMembership.id)
        )
        return list((await self.session.execute(statement)).tuples().all())

    async def get_workspace_membership(
        self, organization_id: UUID, workspace_id: UUID, membership_id: UUID
    ) -> WorkspaceMembership | None:
        return cast(
            WorkspaceMembership | None,
            await self.session.scalar(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.organization_id == organization_id,
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.id == membership_id,
                )
            ),
        )


class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_organization(self, organization_id: UUID) -> list[Invitation]:
        return list(
            (
                await self.session.scalars(
                    select(Invitation)
                    .where(Invitation.organization_id == organization_id)
                    .order_by(Invitation.created_at.desc(), Invitation.id)
                )
            ).all()
        )

    async def workspace_ids(self, organization_id: UUID, invitation_id: UUID) -> list[UUID]:
        return list(
            (
                await self.session.scalars(
                    select(InvitationWorkspace.workspace_id).where(
                        InvitationWorkspace.organization_id == organization_id,
                        InvitationWorkspace.invitation_id == invitation_id,
                    )
                )
            ).all()
        )

    async def get_scoped(
        self, organization_id: UUID, invitation_id: UUID, *, for_update: bool = False
    ) -> Invitation | None:
        statement = select(Invitation).where(
            Invitation.organization_id == organization_id, Invitation.id == invitation_id
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Invitation | None, await self.session.scalar(statement))

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        return cast(
            Invitation | None,
            await self.session.scalar(
                select(Invitation).where(Invitation.token_hash == token_hash).with_for_update()
            ),
        )

    async def pending_for_email(
        self, organization_id: UUID, normalized_email: str
    ) -> Invitation | None:
        return cast(
            Invitation | None,
            await self.session.scalar(
                select(Invitation).where(
                    Invitation.organization_id == organization_id,
                    Invitation.normalized_email == normalized_email,
                    Invitation.status == InvitationStatus.PENDING,
                )
            ),
        )
