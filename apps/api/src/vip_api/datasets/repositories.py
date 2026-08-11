"""Strictly tenant-qualified dataset persistence."""

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.datasets.models import (
    Dataset,
    DatasetField,
    DatasetQualityEvaluation,
    DatasetQualityResult,
    DatasetQualityRule,
)


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

    async def list_quality_rules_scoped(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
        dataset_filters: Sequence[Any] = (),
    ) -> tuple[list[tuple[DatasetQualityRule, str, UUID]], int]:
        """Return workspace-wide quality rules joined to their dataset name.

        ``dataset_filters`` carry the SAME per-user visibility predicate used by
        the dataset collection, applied to ``Dataset`` so a caller can never see
        rules for datasets they may not access. Bounded: two queries total (count
        + page), independent of the number of datasets.
        """
        filters: list[Any] = [
            DatasetQualityRule.organization_id == self.organization_id,
            DatasetQualityRule.workspace_id == self.workspace_id,
            Dataset.archived_at.is_(None),
            *dataset_filters,
        ]
        if status:
            filters.append(DatasetQualityRule.status == status)
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(DatasetQualityRule.name.ilike(term), Dataset.display_name.ilike(term))
            )
        join = DatasetQualityRule.__table__.join(
            Dataset.__table__, Dataset.id == DatasetQualityRule.dataset_id
        )
        total = int(
            await self.db.scalar(select(func.count()).select_from(join).where(*filters)) or 0
        )
        rows = (
            await self.db.execute(
                select(DatasetQualityRule, Dataset.display_name, Dataset.id)
                .join(Dataset, Dataset.id == DatasetQualityRule.dataset_id)
                .where(*filters)
                .order_by(Dataset.display_name, DatasetQualityRule.name, DatasetQualityRule.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items = [
            (cast(DatasetQualityRule, rule), cast(str, name), cast(UUID, dataset_id))
            for rule, name, dataset_id in rows
        ]
        return items, total

    async def list_quality_incidents_scoped(
        self,
        *,
        page: int,
        page_size: int,
        dataset_filters: Sequence[Any] = (),
    ) -> tuple[list[tuple[DatasetQualityResult, DatasetQualityRule, str, UUID]], int]:
        """Return the latest failing/warning result per rule, workspace-wide.

        The "latest result per rule" collapse is done in SQL (a single windowed
        subquery), so this issues a bounded number of queries regardless of how
        many datasets or rules exist — replacing the former per-dataset fan-out.
        Visibility is enforced with the same ``dataset_filters`` predicate.
        """
        ranked = (
            select(
                DatasetQualityResult.id.label("result_id"),
                DatasetQualityResult.quality_rule_id.label("quality_rule_id"),
                func.row_number()
                .over(
                    partition_by=DatasetQualityResult.quality_rule_id,
                    order_by=DatasetQualityResult.evaluated_at.desc(),
                )
                .label("result_rank"),
            )
            .where(
                DatasetQualityResult.organization_id == self.organization_id,
                DatasetQualityResult.workspace_id == self.workspace_id,
            )
            .subquery()
        )
        latest = (
            select(ranked.c.result_id).where(ranked.c.result_rank == 1).subquery()
        )
        filters: list[Any] = [
            DatasetQualityResult.organization_id == self.organization_id,
            DatasetQualityResult.workspace_id == self.workspace_id,
            DatasetQualityResult.id.in_(select(latest.c.result_id)),
            DatasetQualityResult.status.in_(("failing", "warning")),
            Dataset.archived_at.is_(None),
            *dataset_filters,
        ]
        join = (
            DatasetQualityResult.__table__.join(
                DatasetQualityRule.__table__,
                DatasetQualityRule.id == DatasetQualityResult.quality_rule_id,
            ).join(Dataset.__table__, Dataset.id == DatasetQualityRule.dataset_id)
        )
        total = int(
            await self.db.scalar(select(func.count()).select_from(join).where(*filters)) or 0
        )
        rows = (
            await self.db.execute(
                select(DatasetQualityResult, DatasetQualityRule, Dataset.display_name, Dataset.id)
                .join(
                    DatasetQualityRule,
                    DatasetQualityRule.id == DatasetQualityResult.quality_rule_id,
                )
                .join(Dataset, Dataset.id == DatasetQualityRule.dataset_id)
                .where(*filters)
                .order_by(DatasetQualityResult.evaluated_at.desc(), DatasetQualityResult.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items = [
            (
                cast(DatasetQualityResult, result),
                cast(DatasetQualityRule, rule),
                cast(str, name),
                cast(UUID, dataset_id),
            )
            for result, rule, name, dataset_id in rows
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
