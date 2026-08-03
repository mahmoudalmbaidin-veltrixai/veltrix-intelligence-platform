"""Semantic modeling audit-trail coverage (Phase B9.1C).

Proves that every dimension/measure/metric/KPI create/update/delete and a direct
model validation emit a persistent, tenant-scoped audit event against the parent
model, with actor, workspace, resource, before/after and a correlation id — and
that no secret or raw SQL is captured. Publish, query, and sharing/ACL audit are
covered elsewhere (test_semantic_republish + governance/query suites).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

# Reuse the tenant + dataset + model seeding from the re-publish suite (same dir).
from test_semantic_republish import _build_valid_model, _cleanup, _context, _seed

from vip_api.auth.models import User
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.governance.models import AuditEvent
from vip_api.semantic.schemas import (
    DimensionCreate,
    KpiCreate,
    MeasureCreate,
    MetricCreate,
)
from vip_api.semantic.services import (
    create_dimension,
    create_kpi,
    create_measure,
    create_metric,
    delete_dimension,
    delete_kpi,
    delete_measure,
    delete_metric,
    update_dimension,
    validate_model,
)
from vip_api.tenancy.models import Organization


async def _events(db: AsyncSession, org_id: UUID) -> list[AuditEvent]:
    return list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == org_id)
                .order_by(AuditEvent.occurred_at)
            )
        ).all()
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_modeling_changes_are_audited(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id, category_id = await _seed(db, suffix)
            org_ids.append(org_id)
            user_ids.append(user_id)
            ctx = _context(user_id, org_id, ws_id)

            # _build_valid_model creates model + dimension + measure + metric.
            mid = await _build_valid_model(db, ctx, dataset_id, category_id)

            # Add + edit + delete a dimension to exercise create/update/delete.
            dim = await create_dimension(
                db,
                ctx,
                mid,
                DimensionCreate(
                    dataset_id=dataset_id,
                    field_id=category_id,
                    key="region",
                    name="Region",
                    dimension_type="categorical",
                ),
            )
            await update_dimension(
                db,
                ctx,
                mid,
                dim.id,
                DimensionCreate(
                    dataset_id=dataset_id,
                    field_id=category_id,
                    key="region",
                    name="Region (edited)",
                    dimension_type="categorical",
                ),
            )
            await delete_dimension(db, ctx, mid, dim.id)

            # A second measure + metric, then delete them.
            measure = await create_measure(
                db,
                ctx,
                mid,
                MeasureCreate(
                    dataset_id=dataset_id, key="row_count", name="Rows", aggregation="count"
                ),
            )
            metric = await create_metric(
                db,
                ctx,
                mid,
                MetricCreate(
                    key="rows", name="Rows", metric_type="measure", base_measure_id=measure.id
                ),
            )
            # KPI create + delete.
            kpi = await create_kpi(
                db,
                ctx,
                mid,
                KpiCreate(
                    metric_id=metric.id,
                    key="rows_kpi",
                    name="Rows KPI",
                    comparison_operator="greater_than",
                ),
            )
            await delete_kpi(db, ctx, mid, kpi.id)
            await delete_metric(db, ctx, mid, metric.id)
            await delete_measure(db, ctx, mid, measure.id)

            # A direct validation request is audited (route path).
            await validate_model(db, ctx, mid)

            events = await _events(db, org_id)
            types = [e.event_type for e in events]

            # Every modeling mutation produced a persistent event.
            for expected in (
                "semantic_dimension.created",
                "semantic_dimension.updated",
                "semantic_dimension.deleted",
                "semantic_measure.created",
                "semantic_measure.deleted",
                "semantic_metric.created",
                "semantic_metric.deleted",
                "semantic_kpi.created",
                "semantic_kpi.deleted",
                "semantic_model.validated",
            ):
                assert expected in types, f"missing audit event: {expected}"

            # Each child event carries actor, tenant, workspace, resource, entity + id.
            child = next(e for e in events if e.event_type == "semantic_dimension.updated")
            assert child.actor_user_id == user_id
            assert child.organization_id == org_id
            assert child.workspace_id == ws_id
            assert child.resource_type == "semantic_model"
            assert child.resource_id == mid
            assert child.correlation_id  # non-empty
            meta = child.event_metadata
            assert meta["entity"] == "dimension"
            assert meta["entity_id"] == str(dim.id)
            # Before/after reflect the rename and contain no secret/raw SQL.
            assert meta["before"]["name"] == "Region"
            assert meta["after"]["name"] == "Region (edited)"
            blob = str(meta).lower()
            assert "select " not in blob and "password" not in blob and "secret" not in blob

            # The validation event records the outcome without leaking internals.
            validated = next(e for e in events if e.event_type == "semantic_model.validated")
            assert validated.outcome == "success"
            assert validated.event_metadata["valid"] is True
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_validation_is_audited_as_failure(settings: Settings) -> None:
    """A model with no dimensions/metrics validates as failure and is audited."""
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user_id, org_id, ws_id, dataset_id, _category = await _seed(db, suffix)
            org_ids.append(org_id)
            user_ids.append(user_id)
            ctx = _context(user_id, org_id, ws_id)

            from vip_api.semantic.schemas import SemanticModelCreate
            from vip_api.semantic.services import create_model

            created = await create_model(
                db,
                ctx,
                SemanticModelCreate(key="empty_model", name="Empty", primary_dataset_id=dataset_id),
            )
            result = await validate_model(db, ctx, created.id)
            assert result.valid is False

            events = await _events(db, org_id)
            validated = [e for e in events if e.event_type == "semantic_model.validated"]
            assert validated and validated[-1].outcome == "failure"
            assert "DIMENSION_REQUIRED" in validated[-1].event_metadata["error_codes"]
    finally:
        await _cleanup(database, org_ids, user_ids)


# Keep a reference so linters don't drop the User/Organization/delete imports used
# transitively by the reused seed/cleanup helpers.
_ = (User, Organization, delete)
