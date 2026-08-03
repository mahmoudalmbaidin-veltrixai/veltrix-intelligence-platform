"""Semantic-model and glossary lifecycle services."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.errors import ApplicationError
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.governance.access_view import ResourceEffectiveAccess
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import consume_quota
from vip_api.schemas.error import ErrorDetail
from vip_api.semantic.models import (
    GlossaryAssignment,
    GlossaryDomain,
    GlossaryTerm,
    GlossaryTermRelationship,
    SemanticDimension,
    SemanticKpi,
    SemanticMeasure,
    SemanticMetric,
    SemanticModel,
    SemanticModelDataset,
    SemanticModelVersion,
)
from vip_api.semantic.schemas import (
    DimensionCreate,
    DimensionResponse,
    GlossaryAssignmentCreate,
    GlossaryAssignmentResponse,
    GlossaryDomainCreate,
    GlossaryDomainResponse,
    GlossaryRelationshipCreate,
    GlossaryRelationshipResponse,
    GlossaryTermCreate,
    GlossaryTermResponse,
    KpiCreate,
    KpiResponse,
    MeasureCreate,
    MeasureResponse,
    MetricCreate,
    MetricResponse,
    SemanticModelCreate,
    SemanticModelResponse,
    SemanticModelUpdate,
    SemanticModelVersionResponse,
    SemanticValidationResponse,
    ValidationIssue,
)


def _scope(context: AuthorizationContext) -> tuple[UUID, UUID]:
    if context.workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    return context.organization_id, context.workspace_id


async def _model(
    db: AsyncSession,
    context: AuthorizationContext,
    model_id: UUID,
    *,
    editable: bool = False,
    action_level: str | None = None,
) -> SemanticModel:
    from vip_api.governance import resource_access_service

    org, ws = _scope(context)
    item = await db.scalar(
        select(SemanticModel).where(
            SemanticModel.id == model_id,
            SemanticModel.organization_id == org,
            SemanticModel.workspace_id == ws,
            SemanticModel.archived_at.is_(None),
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    # Authoritative per-model decision: role level, direct/group ACL, explicit deny
    # and expiration in one place, so an ACL grant elevates access without a broad
    # semantic_model.* permission. Explicit deny -> 403; other denial -> 404.
    await resource_access_service.authorize_resource(
        db,
        context,
        resource_type="semantic_model",
        resource_id=item.id,
        action_level=action_level or ("edit" if editable else "view"),
    )
    if editable and item.status == "published":
        # Editing a published model reopens it as a draft. The previously published
        # version stays immutable (its frozen snapshot), and the next publish mints
        # the next sequential published version (computed at publish time), mirroring
        # the pipeline re-publish state machine. Archived models are already filtered
        # out above, so only draft/published reach here.
        item.status = "draft"
    return item


async def list_models(
    db: AsyncSession, context: AuthorizationContext
) -> list[SemanticModelResponse]:
    from vip_api.governance import resource_access_service

    org, ws = _scope(context)
    query = select(SemanticModel).where(
        SemanticModel.organization_id == org,
        SemanticModel.workspace_id == ws,
        SemanticModel.archived_at.is_(None),
    )
    # Broad-role users see every model; everyone else sees only models reachable
    # through a non-expired ACL allow (direct or group) minus lowest-level denies
    # (semantic models have no owner column). Filtered in SQL — no N+1, no leak.
    if resource_access_service.role_level("semantic_model", context.permissions) is None:
        subjects = {context.user_id} | await resource_access_service.group_ids_for_user(
            db, org, context.user_id
        )
        allowed_ids, denied_ids = resource_access_service.collection_visibility_subqueries(
            "semantic_model", subjects, now=datetime.now(UTC)
        )
        query = query.where(SemanticModel.id.in_(allowed_ids), SemanticModel.id.notin_(denied_ids))
    rows = (await db.scalars(query.order_by(SemanticModel.name))).all()
    return [SemanticModelResponse.model_validate(row) for row in rows]


async def get_model(
    db: AsyncSession,
    context: AuthorizationContext,
    model_id: UUID,
    *,
    is_platform_admin: bool = False,
) -> SemanticModelResponse:
    from vip_api.governance import resource_access_service

    item = await _model(db, context, model_id)
    response = SemanticModelResponse.model_validate(item)
    summary = await resource_access_service.resource_access_summary(
        db,
        context,
        resource_type="semantic_model",
        resource_id=item.id,
        is_platform_admin=is_platform_admin,
    )
    response.access = ResourceEffectiveAccess.from_summary(summary)
    return response


async def list_model_versions(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID
) -> list[SemanticModelVersionResponse]:
    item = await _model(db, context, model_id)
    rows = (
        await db.scalars(
            select(SemanticModelVersion)
            .where(
                SemanticModelVersion.semantic_model_id == item.id,
                SemanticModelVersion.organization_id == item.organization_id,
                SemanticModelVersion.workspace_id == item.workspace_id,
            )
            .order_by(SemanticModelVersion.version_number.desc())
        )
    ).all()
    return [SemanticModelVersionResponse.model_validate(row) for row in rows]


async def create_model(
    db: AsyncSession, context: AuthorizationContext, payload: SemanticModelCreate
) -> SemanticModelResponse:
    org, ws = _scope(context)
    dataset = await db.scalar(
        select(Dataset).where(
            Dataset.id == payload.primary_dataset_id,
            Dataset.organization_id == org,
            Dataset.workspace_id == ws,
            Dataset.status == "active",
            Dataset.archived_at.is_(None),
        )
    )
    if dataset is None:
        raise ApplicationError(
            code="INVALID_DATASET", message="The selected dataset is unavailable.", status_code=422
        )
    await consume_quota(db, context, "semantic_models.max")
    item = SemanticModel(
        organization_id=org,
        workspace_id=ws,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        primary_dataset_id=dataset.id,
        timezone=payload.timezone,
        currency=payload.currency,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
    )
    db.add(item)
    await db.flush()
    db.add(
        SemanticModelDataset(
            organization_id=org,
            workspace_id=ws,
            semantic_model_id=item.id,
            dataset_id=dataset.id,
            alias=dataset.source_name,
            is_primary=True,
        )
    )
    await record_audit(
        db,
        "semantic_model.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="semantic_model",
        resource_id=item.id,
    )
    await db.commit()
    return SemanticModelResponse.model_validate(item)


async def update_model(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, payload: SemanticModelUpdate
) -> SemanticModelResponse:
    org, ws = _scope(context)
    item = await _model(db, context, model_id, editable=True)
    if item.version != payload.version:
        raise ApplicationError(
            code="VERSION_CONFLICT",
            message="The resource was changed by another request.",
            status_code=409,
        )
    for key, value in payload.model_dump(exclude_unset=True, exclude={"version"}).items():
        setattr(item, key, value)
    item.version += 1
    item.version_number += 1
    item.updated_by_user_id = context.user_id
    await record_audit(
        db,
        "semantic_model.updated",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="semantic_model",
        resource_id=item.id,
    )
    await db.commit()
    return SemanticModelResponse.model_validate(item)


async def validate_model(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID
) -> SemanticValidationResponse:
    item = await _model(db, context, model_id)
    dimensions = list(
        (
            await db.scalars(
                select(SemanticDimension).where(SemanticDimension.semantic_model_id == item.id)
            )
        ).all()
    )
    metrics = list(
        (
            await db.scalars(
                select(SemanticMetric).where(SemanticMetric.semantic_model_id == item.id)
            )
        ).all()
    )
    errors: list[ValidationIssue] = []
    if not dimensions:
        errors.append(
            ValidationIssue(
                code="DIMENSION_REQUIRED", message="At least one dimension is required."
            )
        )
    if not metrics:
        errors.append(
            ValidationIssue(code="METRIC_REQUIRED", message="At least one metric is required.")
        )
    for metric in metrics:
        if metric.metric_type == "ratio" and (
            metric.numerator_metric_id == metric.id or metric.denominator_metric_id == metric.id
        ):
            errors.append(
                ValidationIssue(
                    code="METRIC_CYCLE",
                    message="A metric cannot depend on itself.",
                    resource=metric.key,
                )
            )
    return SemanticValidationResponse(valid=not errors, errors=errors, warnings=[])


async def publish_model(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID
) -> SemanticModelResponse:
    org, ws = _scope(context)
    # Publish must not re-draft: authorize manage without the editable re-draft,
    # and require an unpublished draft so a clean published model is not
    # republished into a duplicate version.
    item = await _model(db, context, model_id, action_level="manage")
    if item.status != "draft":
        raise ApplicationError(
            code="SEMANTIC_MODEL_NOT_DRAFT",
            message="There are no unpublished changes to publish.",
            status_code=409,
        )
    result = await validate_model(db, context, model_id)
    if not result.valid:
        raise ApplicationError(
            code="SEMANTIC_MODEL_INVALID",
            message="The semantic model has validation errors.",
            status_code=422,
            details=[
                ErrorDetail(field=issue.resource or "model", message=issue.message)
                for issue in result.errors
            ],
        )
    # Sequential, immutable published versions: the next published number is one
    # past the highest existing published version for this model (independent of
    # the draft edit counter), so re-publishing after edits never collides and
    # never skips — mirroring the pipeline re-publish numbering.
    highest = await db.scalar(
        select(func.max(SemanticModelVersion.version_number)).where(
            SemanticModelVersion.semantic_model_id == item.id
        )
    )
    next_version = int(highest or 0) + 1
    item.status = "published"
    item.published_version = next_version
    item.version += 1
    snapshot = {
        "model": SemanticModelResponse.model_validate(item).model_dump(mode="json"),
        "dimensions": [
            value.model_dump(mode="json") for value in await list_dimensions(db, context, item.id)
        ],
        "measures": [
            value.model_dump(mode="json") for value in await list_measures(db, context, item.id)
        ],
        "metrics": [
            value.model_dump(mode="json") for value in await list_metrics(db, context, item.id)
        ],
        "kpis": [value.model_dump(mode="json") for value in await list_kpis(db, context, item.id)],
    }
    db.add(
        SemanticModelVersion(
            organization_id=org,
            workspace_id=ws,
            semantic_model_id=item.id,
            version_number=next_version,
            definition=snapshot,
            published_by_user_id=context.user_id,
        )
    )
    await record_audit(
        db,
        "semantic_model.published",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="semantic_model",
        resource_id=item.id,
    )
    await db.commit()
    return SemanticModelResponse.model_validate(item)


async def archive_model(db: AsyncSession, context: AuthorizationContext, model_id: UUID) -> None:
    org, ws = _scope(context)
    item = await _model(db, context, model_id, action_level="manage")
    item.status = "archived"
    item.archived_at = datetime.now(UTC)
    item.version += 1
    await record_audit(
        db,
        "semantic_model.archived",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="semantic_model",
        resource_id=item.id,
    )
    await db.commit()


async def _field_for_model(
    db: AsyncSession,
    context: AuthorizationContext,
    model: SemanticModel,
    dataset_id: UUID,
    field_id: UUID,
) -> DatasetField:
    org, ws = _scope(context)
    attached = await db.scalar(
        select(SemanticModelDataset.id).where(
            SemanticModelDataset.semantic_model_id == model.id,
            SemanticModelDataset.dataset_id == dataset_id,
            SemanticModelDataset.organization_id == org,
            SemanticModelDataset.workspace_id == ws,
        )
    )
    field = await db.scalar(
        select(DatasetField).where(
            DatasetField.id == field_id,
            DatasetField.dataset_id == dataset_id,
            DatasetField.organization_id == org,
            DatasetField.workspace_id == ws,
        )
    )
    if attached is None or field is None:
        raise ApplicationError(
            code="INVALID_SEMANTIC_FIELD",
            message="The selected field is not available to this model.",
            status_code=422,
        )
    if field.is_hidden or field.is_sensitive:
        raise ApplicationError(
            code="SENSITIVE_FIELD_DENIED",
            message="Hidden or sensitive fields cannot be exposed by a semantic model.",
            status_code=422,
        )
    return field


async def list_dimensions(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID
) -> list[DimensionResponse]:
    model = await _model(db, context, model_id)
    return [
        DimensionResponse.model_validate(row)
        for row in (
            await db.scalars(
                select(SemanticDimension)
                .where(SemanticDimension.semantic_model_id == model.id)
                .order_by(SemanticDimension.sort_order, SemanticDimension.name)
            )
        ).all()
    ]


async def create_dimension(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, payload: DimensionCreate
) -> DimensionResponse:
    org, ws = _scope(context)
    model = await _model(db, context, model_id, editable=True)
    field = await _field_for_model(db, context, model, payload.dataset_id, payload.field_id)
    if payload.is_time_dimension and field.normalized_data_type not in {"date", "datetime"}:
        raise ApplicationError(
            code="INVALID_TIME_DIMENSION",
            message="A time dimension requires a date or datetime field.",
            status_code=422,
        )
    item = SemanticDimension(
        organization_id=org,
        workspace_id=ws,
        semantic_model_id=model.id,
        dataset_id=payload.dataset_id,
        field_id=field.id,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        dimension_type=payload.dimension_type,
        data_type=field.normalized_data_type,
        is_time_dimension=payload.is_time_dimension,
        time_granularities=payload.time_granularities,
        is_hidden=payload.is_hidden,
    )
    db.add(item)
    await db.commit()
    return DimensionResponse.model_validate(item)


async def update_dimension(
    db: AsyncSession,
    context: AuthorizationContext,
    model_id: UUID,
    dimension_id: UUID,
    payload: DimensionCreate,
) -> DimensionResponse:
    model = await _model(db, context, model_id, editable=True)
    field = await _field_for_model(db, context, model, payload.dataset_id, payload.field_id)
    item = await db.scalar(
        select(SemanticDimension).where(
            SemanticDimension.id == dimension_id, SemanticDimension.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    if payload.is_time_dimension and field.normalized_data_type not in {"date", "datetime"}:
        raise ApplicationError(
            code="INVALID_TIME_DIMENSION",
            message="A time dimension requires a date or datetime field.",
            status_code=422,
        )
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.data_type = field.normalized_data_type
    await db.commit()
    return DimensionResponse.model_validate(item)


async def delete_dimension(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, dimension_id: UUID
) -> None:
    model = await _model(db, context, model_id, editable=True)
    item = await db.scalar(
        select(SemanticDimension).where(
            SemanticDimension.id == dimension_id, SemanticDimension.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await db.commit()


async def list_measures(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID
) -> list[MeasureResponse]:
    model = await _model(db, context, model_id)
    return [
        MeasureResponse.model_validate(row)
        for row in (
            await db.scalars(
                select(SemanticMeasure)
                .where(SemanticMeasure.semantic_model_id == model.id)
                .order_by(SemanticMeasure.name)
            )
        ).all()
    ]


async def create_measure(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, payload: MeasureCreate
) -> MeasureResponse:
    org, ws = _scope(context)
    model = await _model(db, context, model_id, editable=True)
    field = None
    if payload.field_id:
        field = await _field_for_model(db, context, model, payload.dataset_id, payload.field_id)
    if payload.aggregation in {"sum", "average"} and (
        field is None or field.normalized_data_type not in {"integer", "decimal"}
    ):
        raise ApplicationError(
            code="INVALID_AGGREGATION",
            message="This aggregation requires a numeric field.",
            status_code=422,
        )
    item = SemanticMeasure(
        organization_id=org,
        workspace_id=ws,
        semantic_model_id=model.id,
        dataset_id=payload.dataset_id,
        field_id=payload.field_id,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        aggregation=payload.aggregation,
        data_type="integer"
        if payload.aggregation == "count"
        else field.normalized_data_type
        if field
        else "integer",
        is_hidden=payload.is_hidden,
    )
    db.add(item)
    await db.commit()
    return MeasureResponse.model_validate(item)


async def update_measure(
    db: AsyncSession,
    context: AuthorizationContext,
    model_id: UUID,
    measure_id: UUID,
    payload: MeasureCreate,
) -> MeasureResponse:
    model = await _model(db, context, model_id, editable=True)
    field = None
    if payload.field_id:
        field = await _field_for_model(db, context, model, payload.dataset_id, payload.field_id)
    item = await db.scalar(
        select(SemanticMeasure).where(
            SemanticMeasure.id == measure_id, SemanticMeasure.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    if payload.aggregation in {"sum", "average"} and (
        field is None or field.normalized_data_type not in {"integer", "decimal"}
    ):
        raise ApplicationError(
            code="INVALID_AGGREGATION",
            message="This aggregation requires a numeric field.",
            status_code=422,
        )
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.data_type = (
        "integer"
        if payload.aggregation == "count"
        else field.normalized_data_type
        if field
        else "integer"
    )
    await db.commit()
    return MeasureResponse.model_validate(item)


async def delete_measure(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, measure_id: UUID
) -> None:
    model = await _model(db, context, model_id, editable=True)
    item = await db.scalar(
        select(SemanticMeasure).where(
            SemanticMeasure.id == measure_id, SemanticMeasure.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await db.commit()


async def list_metrics(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID
) -> list[MetricResponse]:
    model = await _model(db, context, model_id)
    return [
        MetricResponse.model_validate(row)
        for row in (
            await db.scalars(
                select(SemanticMetric)
                .where(SemanticMetric.semantic_model_id == model.id)
                .order_by(SemanticMetric.name)
            )
        ).all()
    ]


async def create_metric(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, payload: MetricCreate
) -> MetricResponse:
    org, ws = _scope(context)
    model = await _model(db, context, model_id, editable=True)
    for dependency, kind in (
        (payload.base_measure_id, SemanticMeasure),
        (payload.numerator_metric_id, SemanticMetric),
        (payload.denominator_metric_id, SemanticMetric),
    ):
        if (
            dependency
            and await db.scalar(
                select(kind.id).where(
                    kind.id == dependency,
                    kind.semantic_model_id == model.id,
                    kind.organization_id == org,
                    kind.workspace_id == ws,
                )
            )
            is None
        ):
            raise ApplicationError(
                code="INVALID_METRIC_DEPENDENCY",
                message="A metric dependency is unavailable.",
                status_code=422,
            )
    await consume_quota(db, context, "metrics.max")
    item = SemanticMetric(
        organization_id=org,
        workspace_id=ws,
        semantic_model_id=model.id,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        metric_type=payload.metric_type,
        base_measure_id=payload.base_measure_id,
        numerator_metric_id=payload.numerator_metric_id,
        denominator_metric_id=payload.denominator_metric_id,
        unit=payload.unit,
    )
    db.add(item)
    await db.commit()
    return MetricResponse.model_validate(item)


async def update_metric(
    db: AsyncSession,
    context: AuthorizationContext,
    model_id: UUID,
    metric_id: UUID,
    payload: MetricCreate,
) -> MetricResponse:
    org, ws = _scope(context)
    model = await _model(db, context, model_id, editable=True)
    item = await db.scalar(
        select(SemanticMetric).where(
            SemanticMetric.id == metric_id, SemanticMetric.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    if metric_id in {payload.numerator_metric_id, payload.denominator_metric_id}:
        raise ApplicationError(
            code="METRIC_CYCLE", message="A metric cannot depend on itself.", status_code=422
        )
    for dependency, kind in (
        (payload.base_measure_id, SemanticMeasure),
        (payload.numerator_metric_id, SemanticMetric),
        (payload.denominator_metric_id, SemanticMetric),
    ):
        if (
            dependency
            and await db.scalar(
                select(kind.id).where(
                    kind.id == dependency,
                    kind.semantic_model_id == model.id,
                    kind.organization_id == org,
                    kind.workspace_id == ws,
                )
            )
            is None
        ):
            raise ApplicationError(
                code="INVALID_METRIC_DEPENDENCY",
                message="A metric dependency is unavailable.",
                status_code=422,
            )
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await db.commit()
    return MetricResponse.model_validate(item)


async def delete_metric(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, metric_id: UUID
) -> None:
    model = await _model(db, context, model_id, editable=True)
    item = await db.scalar(
        select(SemanticMetric).where(
            SemanticMetric.id == metric_id, SemanticMetric.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await db.commit()


async def list_kpis(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID
) -> list[KpiResponse]:
    model = await _model(db, context, model_id)
    return [
        KpiResponse.model_validate(row)
        for row in (
            await db.scalars(
                select(SemanticKpi)
                .where(SemanticKpi.semantic_model_id == model.id)
                .order_by(SemanticKpi.name)
            )
        ).all()
    ]


async def create_kpi(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, payload: KpiCreate
) -> KpiResponse:
    org, ws = _scope(context)
    model = await _model(db, context, model_id, editable=True)
    if (
        await db.scalar(
            select(SemanticMetric.id).where(
                SemanticMetric.id == payload.metric_id, SemanticMetric.semantic_model_id == model.id
            )
        )
        is None
    ):
        raise ApplicationError(
            code="INVALID_METRIC", message="The selected metric is unavailable.", status_code=422
        )
    item = SemanticKpi(
        organization_id=org,
        workspace_id=ws,
        semantic_model_id=model.id,
        metric_id=payload.metric_id,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        target_value=payload.target_value,
        warning_threshold=payload.warning_threshold,
        critical_threshold=payload.critical_threshold,
        comparison_operator=payload.comparison_operator,
        target_period=payload.target_period,
    )
    db.add(item)
    await db.commit()
    return KpiResponse.model_validate(item)


async def update_kpi(
    db: AsyncSession,
    context: AuthorizationContext,
    model_id: UUID,
    kpi_id: UUID,
    payload: KpiCreate,
) -> KpiResponse:
    model = await _model(db, context, model_id, editable=True)
    item = await db.scalar(
        select(SemanticKpi).where(
            SemanticKpi.id == kpi_id, SemanticKpi.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    if (
        await db.scalar(
            select(SemanticMetric.id).where(
                SemanticMetric.id == payload.metric_id, SemanticMetric.semantic_model_id == model.id
            )
        )
        is None
    ):
        raise ApplicationError(
            code="INVALID_METRIC", message="The selected metric is unavailable.", status_code=422
        )
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await db.commit()
    return KpiResponse.model_validate(item)


async def delete_kpi(
    db: AsyncSession, context: AuthorizationContext, model_id: UUID, kpi_id: UUID
) -> None:
    model = await _model(db, context, model_id, editable=True)
    item = await db.scalar(
        select(SemanticKpi).where(
            SemanticKpi.id == kpi_id, SemanticKpi.semantic_model_id == model.id
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await db.commit()


async def list_domains(
    db: AsyncSession, context: AuthorizationContext
) -> list[GlossaryDomainResponse]:
    org, ws = _scope(context)
    return [
        GlossaryDomainResponse.model_validate(row)
        for row in (
            await db.scalars(
                select(GlossaryDomain)
                .where(GlossaryDomain.organization_id == org, GlossaryDomain.workspace_id == ws)
                .order_by(GlossaryDomain.name)
            )
        ).all()
    ]


async def create_domain(
    db: AsyncSession, context: AuthorizationContext, payload: GlossaryDomainCreate
) -> GlossaryDomainResponse:
    org, ws = _scope(context)
    item = GlossaryDomain(organization_id=org, workspace_id=ws, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "glossary.domain.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="glossary_domain",
        resource_id=item.id,
    )
    await db.commit()
    return GlossaryDomainResponse.model_validate(item)


async def update_domain(
    db: AsyncSession, context: AuthorizationContext, domain_id: UUID, payload: GlossaryDomainCreate
) -> GlossaryDomainResponse:
    org, ws = _scope(context)
    item = await db.scalar(
        select(GlossaryDomain).where(
            GlossaryDomain.id == domain_id,
            GlossaryDomain.organization_id == org,
            GlossaryDomain.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await db.commit()
    return GlossaryDomainResponse.model_validate(item)


async def list_terms(
    db: AsyncSession, context: AuthorizationContext, search: str | None
) -> list[GlossaryTermResponse]:
    org, ws = _scope(context)
    filters = [GlossaryTerm.organization_id == org, GlossaryTerm.workspace_id == ws]
    if search:
        filters.append(
            or_(
                GlossaryTerm.name.ilike(f"%{search}%"),
                GlossaryTerm.key.ilike(f"%{search}%"),
                GlossaryTerm.definition.ilike(f"%{search}%"),
            )
        )
    return [
        GlossaryTermResponse.model_validate(row)
        for row in (
            await db.scalars(select(GlossaryTerm).where(*filters).order_by(GlossaryTerm.name))
        ).all()
    ]


async def create_term(
    db: AsyncSession, context: AuthorizationContext, payload: GlossaryTermCreate
) -> GlossaryTermResponse:
    org, ws = _scope(context)
    if (
        await db.scalar(
            select(GlossaryDomain.id).where(
                GlossaryDomain.id == payload.domain_id,
                GlossaryDomain.organization_id == org,
                GlossaryDomain.workspace_id == ws,
            )
        )
        is None
    ):
        raise ApplicationError(
            code="INVALID_GLOSSARY_DOMAIN",
            message="The selected glossary domain is unavailable.",
            status_code=422,
        )
    await consume_quota(db, context, "glossary_terms.max")
    values = payload.model_dump()
    values["synonyms"] = sorted(
        {value.strip().lower() for value in payload.synonyms if value.strip()}
    )
    item = GlossaryTerm(organization_id=org, workspace_id=ws, **values)
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "glossary.term.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="glossary_term",
        resource_id=item.id,
    )
    await db.commit()
    return GlossaryTermResponse.model_validate(item)


async def get_term(
    db: AsyncSession, context: AuthorizationContext, term_id: UUID
) -> GlossaryTermResponse:
    org, ws = _scope(context)
    item = await db.scalar(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id,
            GlossaryTerm.organization_id == org,
            GlossaryTerm.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    return GlossaryTermResponse.model_validate(item)


async def update_term(
    db: AsyncSession, context: AuthorizationContext, term_id: UUID, payload: GlossaryTermCreate
) -> GlossaryTermResponse:
    org, ws = _scope(context)
    item = await db.scalar(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id,
            GlossaryTerm.organization_id == org,
            GlossaryTerm.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    if (
        await db.scalar(
            select(GlossaryDomain.id).where(
                GlossaryDomain.id == payload.domain_id,
                GlossaryDomain.organization_id == org,
                GlossaryDomain.workspace_id == ws,
            )
        )
        is None
    ):
        raise ApplicationError(
            code="INVALID_GLOSSARY_DOMAIN",
            message="The selected glossary domain is unavailable.",
            status_code=422,
        )
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.synonyms = sorted({value.strip().lower() for value in payload.synonyms if value.strip()})
    await db.commit()
    return GlossaryTermResponse.model_validate(item)


async def set_term_status(
    db: AsyncSession, context: AuthorizationContext, term_id: UUID, status: str
) -> GlossaryTermResponse:
    org, ws = _scope(context)
    item = await db.scalar(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id,
            GlossaryTerm.organization_id == org,
            GlossaryTerm.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    item.status = status
    await record_audit(
        db,
        f"glossary.term.{status}",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="glossary_term",
        resource_id=item.id,
    )
    await db.commit()
    return GlossaryTermResponse.model_validate(item)


async def create_term_relationship(
    db: AsyncSession,
    context: AuthorizationContext,
    term_id: UUID,
    payload: GlossaryRelationshipCreate,
) -> GlossaryRelationshipResponse:
    org, ws = _scope(context)
    terms = list(
        (
            await db.scalars(
                select(GlossaryTerm).where(
                    GlossaryTerm.organization_id == org,
                    GlossaryTerm.workspace_id == ws,
                    GlossaryTerm.id.in_({term_id, payload.target_term_id}),
                )
            )
        ).all()
    )
    if len(terms) != 2 or term_id == payload.target_term_id:
        raise ApplicationError(
            code="INVALID_GLOSSARY_RELATIONSHIP",
            message="Both glossary terms must be distinct and available.",
            status_code=422,
        )
    item = GlossaryTermRelationship(
        organization_id=org,
        workspace_id=ws,
        source_term_id=term_id,
        target_term_id=payload.target_term_id,
        relationship_type=payload.relationship_type,
    )
    db.add(item)
    await db.commit()
    return GlossaryRelationshipResponse.model_validate(item)


async def delete_term_relationship(
    db: AsyncSession, context: AuthorizationContext, term_id: UUID, relationship_id: UUID
) -> None:
    org, ws = _scope(context)
    item = await db.scalar(
        select(GlossaryTermRelationship).where(
            GlossaryTermRelationship.id == relationship_id,
            GlossaryTermRelationship.source_term_id == term_id,
            GlossaryTermRelationship.organization_id == org,
            GlossaryTermRelationship.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await db.commit()


async def _assignment_resource_exists(
    db: AsyncSession, org: UUID, ws: UUID, payload: GlossaryAssignmentCreate
) -> bool:
    if payload.resource_type == "dataset":
        return (
            await db.scalar(
                select(Dataset.id).where(
                    Dataset.id == payload.resource_id,
                    Dataset.organization_id == org,
                    Dataset.workspace_id == ws,
                )
            )
            is not None
        )
    if payload.resource_type == "dataset_field":
        return (
            await db.scalar(
                select(DatasetField.id).where(
                    DatasetField.id == payload.resource_id,
                    DatasetField.organization_id == org,
                    DatasetField.workspace_id == ws,
                )
            )
            is not None
        )
    if payload.resource_type == "semantic_model":
        return (
            await db.scalar(
                select(SemanticModel.id).where(
                    SemanticModel.id == payload.resource_id,
                    SemanticModel.organization_id == org,
                    SemanticModel.workspace_id == ws,
                )
            )
            is not None
        )
    if payload.resource_type == "dimension":
        return (
            await db.scalar(
                select(SemanticDimension.id).where(
                    SemanticDimension.id == payload.resource_id,
                    SemanticDimension.organization_id == org,
                    SemanticDimension.workspace_id == ws,
                )
            )
            is not None
        )
    if payload.resource_type == "measure":
        return (
            await db.scalar(
                select(SemanticMeasure.id).where(
                    SemanticMeasure.id == payload.resource_id,
                    SemanticMeasure.organization_id == org,
                    SemanticMeasure.workspace_id == ws,
                )
            )
            is not None
        )
    if payload.resource_type == "metric":
        return (
            await db.scalar(
                select(SemanticMetric.id).where(
                    SemanticMetric.id == payload.resource_id,
                    SemanticMetric.organization_id == org,
                    SemanticMetric.workspace_id == ws,
                )
            )
            is not None
        )
    return (
        await db.scalar(
            select(SemanticKpi.id).where(
                SemanticKpi.id == payload.resource_id,
                SemanticKpi.organization_id == org,
                SemanticKpi.workspace_id == ws,
            )
        )
        is not None
    )


async def create_term_assignment(
    db: AsyncSession,
    context: AuthorizationContext,
    term_id: UUID,
    payload: GlossaryAssignmentCreate,
) -> GlossaryAssignmentResponse:
    org, ws = _scope(context)
    if await db.scalar(
        select(GlossaryTerm.id).where(
            GlossaryTerm.id == term_id,
            GlossaryTerm.organization_id == org,
            GlossaryTerm.workspace_id == ws,
        )
    ) is None or not await _assignment_resource_exists(db, org, ws, payload):
        raise ApplicationError(
            code="INVALID_GLOSSARY_ASSIGNMENT",
            message="The glossary assignment target is unavailable.",
            status_code=422,
        )
    item = GlossaryAssignment(
        organization_id=org,
        workspace_id=ws,
        term_id=term_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        created_by_user_id=context.user_id,
    )
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "glossary.assignment.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="glossary_assignment",
        resource_id=item.id,
    )
    await db.commit()
    return GlossaryAssignmentResponse.model_validate(item)


async def delete_term_assignment(
    db: AsyncSession, context: AuthorizationContext, term_id: UUID, assignment_id: UUID
) -> None:
    org, ws = _scope(context)
    item = await db.scalar(
        select(GlossaryAssignment).where(
            GlossaryAssignment.id == assignment_id,
            GlossaryAssignment.term_id == term_id,
            GlossaryAssignment.organization_id == org,
            GlossaryAssignment.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await db.commit()
