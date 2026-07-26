"""Strictly tenant-qualified dataset persistence."""

from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.datasets.models import Dataset, DatasetField


class DatasetRepository:
    def __init__(self, db: AsyncSession, organization_id: UUID, workspace_id: UUID) -> None:
        self.db = db
        self.organization_id = organization_id
        self.workspace_id = workspace_id

    async def get(self, dataset_id: UUID, *, include_archived: bool = False) -> Dataset | None:
        filters = [
            Dataset.id == dataset_id,
            Dataset.organization_id == self.organization_id,
            Dataset.workspace_id == self.workspace_id,
        ]
        if not include_archived:
            filters.append(Dataset.archived_at.is_(None))
        return cast(Dataset | None, await self.db.scalar(select(Dataset).where(*filters)))

    async def list_scoped(
        self, *, page: int, page_size: int, search: str | None, status: str | None
    ) -> tuple[list[Dataset], int]:
        filters = [
            Dataset.organization_id == self.organization_id,
            Dataset.workspace_id == self.workspace_id,
            Dataset.archived_at.is_(None),
        ]
        if status:
            filters.append(Dataset.status == status)
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(Dataset.display_name.ilike(term), Dataset.qualified_name.ilike(term))
            )
        total = int(
            await self.db.scalar(select(func.count()).select_from(Dataset).where(*filters)) or 0
        )
        items = list(
            (
                await self.db.scalars(
                    select(Dataset)
                    .where(*filters)
                    .order_by(Dataset.display_name, Dataset.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return items, total

    async def fields(self, dataset_id: UUID) -> list[DatasetField]:
        return list(
            (
                await self.db.scalars(
                    select(DatasetField)
                    .where(
                        DatasetField.organization_id == self.organization_id,
                        DatasetField.workspace_id == self.workspace_id,
                        DatasetField.dataset_id == dataset_id,
                    )
                    .order_by(DatasetField.ordinal_position)
                )
            ).all()
        )
