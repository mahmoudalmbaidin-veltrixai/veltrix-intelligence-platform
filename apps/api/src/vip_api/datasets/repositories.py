"""Strictly tenant-qualified dataset persistence."""

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.datasets.models import Dataset, DatasetField, DatasetQualityEvaluation


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
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
        extra_filters: Sequence[Any] = (),
    ) -> tuple[list[tuple[Dataset, int | None]], int]:
        # ``extra_filters`` carry the per-user resource-visibility predicate so the
        # ACL filter is applied to BOTH the count and the paginated page — hidden
        # datasets never leak through pagination or the reported total.
        filters = [
            Dataset.organization_id == self.organization_id,
            Dataset.workspace_id == self.workspace_id,
            Dataset.archived_at.is_(None),
            *extra_filters,
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
        # Project the latest completed quality score in the same bounded page
        # query.  The row-number subquery is tenant/workspace qualified and the
        # outer join is applied only after the normal visibility predicates, so
        # it neither adds per-item queries nor changes collection authorization.
        ranked_quality = (
            select(
                DatasetQualityEvaluation.dataset_id.label("dataset_id"),
                DatasetQualityEvaluation.score.label("score"),
                func.row_number()
                .over(
                    partition_by=DatasetQualityEvaluation.dataset_id,
                    order_by=DatasetQualityEvaluation.created_at.desc(),
                )
                .label("quality_rank"),
            )
            .where(
                DatasetQualityEvaluation.organization_id == self.organization_id,
                DatasetQualityEvaluation.workspace_id == self.workspace_id,
                DatasetQualityEvaluation.completed_at.is_not(None),
            )
            .subquery()
        )
        latest_quality = (
            select(ranked_quality.c.dataset_id, ranked_quality.c.score)
            .where(ranked_quality.c.quality_rank == 1)
            .subquery()
        )
        rows = (
            await self.db.execute(
                select(Dataset, latest_quality.c.score)
                .outerjoin(latest_quality, latest_quality.c.dataset_id == Dataset.id)
                .where(*filters)
                .order_by(Dataset.display_name, Dataset.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items = [
            (cast(Dataset, dataset), cast(int | None, quality_score))
            for dataset, quality_score in rows
        ]
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
