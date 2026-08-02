"""Organization-and-workspace-qualified connection persistence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.models import Connection, ConnectionType


class ConnectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_scoped(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        include_archived: bool = False,
        extra_filters: Sequence[Any] = (),
    ) -> tuple[list[tuple[Connection, ConnectionType]], int]:
        # ``extra_filters`` carry the per-user resource-visibility predicate,
        # applied to both count and page so hidden connections never leak.
        filters = [
            Connection.organization_id == organization_id,
            Connection.workspace_id == workspace_id,
            *extra_filters,
        ]
        if not include_archived:
            filters.append(Connection.archived_at.is_(None))
        total = int(
            await self.db.scalar(select(func.count()).select_from(Connection).where(*filters)) or 0
        )
        statement = (
            select(Connection, ConnectionType)
            .join(ConnectionType, ConnectionType.id == Connection.connection_type_id)
            .where(*filters)
            .order_by(Connection.name, Connection.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.db.execute(statement)).tuples().all()), total

    async def get_scoped(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        connection_id: UUID,
        *,
        for_update: bool = False,
        include_archived: bool = False,
    ) -> tuple[Connection, ConnectionType] | None:
        conditions = [
            Connection.id == connection_id,
            Connection.organization_id == organization_id,
            Connection.workspace_id == workspace_id,
        ]
        if not include_archived:
            conditions.append(Connection.archived_at.is_(None))
        statement = (
            select(Connection, ConnectionType)
            .join(ConnectionType, ConnectionType.id == Connection.connection_type_id)
            .where(*conditions)
        )
        if for_update:
            statement = statement.with_for_update(of=Connection)
        return (await self.db.execute(statement)).tuples().one_or_none()

    async def name_exists(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        normalized_name: str,
        *,
        excluding_id: UUID | None = None,
    ) -> bool:
        conditions = [
            Connection.organization_id == organization_id,
            Connection.workspace_id == workspace_id,
            Connection.normalized_name == normalized_name,
            Connection.archived_at.is_(None),
        ]
        if excluding_id is not None:
            conditions.append(Connection.id != excluding_id)
        return await self.db.scalar(select(Connection.id).where(*conditions)) is not None

    async def get_type(self, type_key: str) -> ConnectionType | None:
        return cast(
            ConnectionType | None,
            await self.db.scalar(select(ConnectionType).where(ConnectionType.key == type_key)),
        )

    async def list_types(self) -> list[ConnectionType]:
        return list(
            (
                await self.db.scalars(
                    select(ConnectionType).order_by(ConnectionType.category, ConnectionType.name)
                )
            ).all()
        )
