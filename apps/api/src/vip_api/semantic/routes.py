"""Live Semantic Studio, glossary, and safe analytical query APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import require_csrf
from vip_api.connections.dependencies import get_secret_provider
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings, get_settings
from vip_api.database.session import get_db_session
from vip_api.datasets.dependencies import RequireB5Governance
from vip_api.governance.context import AuthorizationContext
from vip_api.semantic.query import execute_query
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
    SemanticQueryRequest,
    SemanticQueryResult,
    SemanticValidationResponse,
)
from vip_api.semantic.services import (
    archive_model,
    create_dimension,
    create_domain,
    create_kpi,
    create_measure,
    create_metric,
    create_model,
    create_term,
    create_term_assignment,
    create_term_relationship,
    delete_dimension,
    delete_kpi,
    delete_measure,
    delete_metric,
    delete_term_assignment,
    delete_term_relationship,
    get_model,
    get_term,
    list_dimensions,
    list_domains,
    list_kpis,
    list_measures,
    list_metrics,
    list_model_versions,
    list_models,
    list_terms,
    publish_model,
    set_term_status,
    update_dimension,
    update_domain,
    update_kpi,
    update_measure,
    update_metric,
    update_model,
    update_term,
    validate_model,
)

models_router = APIRouter(prefix="/semantic-models", tags=["semantic-models"])
glossary_router = APIRouter(prefix="/glossary", tags=["glossary"])
query_router = APIRouter(tags=["semantic-query"])


def _policy(permission: str, feature: str = "semantic_layer", quota: str | None = None) -> object:
    return RequireB5Governance(permission, feature=feature, quota=quota)


@models_router.get("", response_model=list[SemanticModelResponse])
async def models_index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.read"))],
) -> list[SemanticModelResponse]:
    return await list_models(db, context)


@models_router.post(
    "", response_model=SemanticModelResponse, status_code=201, dependencies=[Depends(require_csrf)]
)
async def models_create(
    payload: SemanticModelCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("semantic_model.create", quota="semantic_models.max"))
    ],
) -> SemanticModelResponse:
    return await create_model(db, context, payload)


@models_router.get("/{model_id}", response_model=SemanticModelResponse)
async def models_detail(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.read"))],
) -> SemanticModelResponse:
    return await get_model(db, context, model_id)


@models_router.get(
    "/{model_id}/versions",
    response_model=list[SemanticModelVersionResponse],
)
async def models_versions(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.read"))],
) -> list[SemanticModelVersionResponse]:
    return await list_model_versions(db, context, model_id)


@models_router.patch(
    "/{model_id}", response_model=SemanticModelResponse, dependencies=[Depends(require_csrf)]
)
async def models_update(
    model_id: UUID,
    payload: SemanticModelUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.update"))],
) -> SemanticModelResponse:
    return await update_model(db, context, model_id, payload)


@models_router.post(
    "/{model_id}/validate",
    response_model=SemanticValidationResponse,
    dependencies=[Depends(require_csrf)],
)
async def models_validate(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.update"))],
) -> SemanticValidationResponse:
    return await validate_model(db, context, model_id)


@models_router.post(
    "/{model_id}/publish",
    response_model=SemanticModelResponse,
    dependencies=[Depends(require_csrf)],
)
async def models_publish(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.publish"))],
) -> SemanticModelResponse:
    return await publish_model(db, context, model_id)


@models_router.post("/{model_id}/archive", status_code=204, dependencies=[Depends(require_csrf)])
async def models_archive(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.archive"))],
) -> Response:
    await archive_model(db, context, model_id)
    return Response(status_code=204)


@models_router.get("/{model_id}/dimensions", response_model=list[DimensionResponse])
async def dimensions_index(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.read"))],
) -> list[DimensionResponse]:
    return await list_dimensions(db, context, model_id)


@models_router.post(
    "/{model_id}/dimensions",
    response_model=DimensionResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def dimensions_create(
    model_id: UUID,
    payload: DimensionCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_dimension.manage"))],
) -> DimensionResponse:
    return await create_dimension(db, context, model_id, payload)


@models_router.patch(
    "/{model_id}/dimensions/{dimension_id}",
    response_model=DimensionResponse,
    dependencies=[Depends(require_csrf)],
)
async def dimensions_update(
    model_id: UUID,
    dimension_id: UUID,
    payload: DimensionCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_dimension.manage"))],
) -> DimensionResponse:
    return await update_dimension(db, context, model_id, dimension_id, payload)


@models_router.delete(
    "/{model_id}/dimensions/{dimension_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def dimensions_delete(
    model_id: UUID,
    dimension_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_dimension.manage"))],
) -> Response:
    await delete_dimension(db, context, model_id, dimension_id)
    return Response(status_code=204)


@models_router.get("/{model_id}/measures", response_model=list[MeasureResponse])
async def measures_index(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.read"))],
) -> list[MeasureResponse]:
    return await list_measures(db, context, model_id)


@models_router.post(
    "/{model_id}/measures",
    response_model=MeasureResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def measures_create(
    model_id: UUID,
    payload: MeasureCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_measure.manage"))],
) -> MeasureResponse:
    return await create_measure(db, context, model_id, payload)


@models_router.patch(
    "/{model_id}/measures/{measure_id}",
    response_model=MeasureResponse,
    dependencies=[Depends(require_csrf)],
)
async def measures_update(
    model_id: UUID,
    measure_id: UUID,
    payload: MeasureCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_measure.manage"))],
) -> MeasureResponse:
    return await update_measure(db, context, model_id, measure_id, payload)


@models_router.delete(
    "/{model_id}/measures/{measure_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def measures_delete(
    model_id: UUID,
    measure_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_measure.manage"))],
) -> Response:
    await delete_measure(db, context, model_id, measure_id)
    return Response(status_code=204)


@models_router.get("/{model_id}/metrics", response_model=list[MetricResponse])
async def metrics_index(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.read"))],
) -> list[MetricResponse]:
    return await list_metrics(db, context, model_id)


@models_router.post(
    "/{model_id}/metrics",
    response_model=MetricResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def metrics_create(
    model_id: UUID,
    payload: MetricCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("semantic_metric.manage", quota="metrics.max"))
    ],
) -> MetricResponse:
    return await create_metric(db, context, model_id, payload)


@models_router.patch(
    "/{model_id}/metrics/{metric_id}",
    response_model=MetricResponse,
    dependencies=[Depends(require_csrf)],
)
async def metrics_update(
    model_id: UUID,
    metric_id: UUID,
    payload: MetricCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_metric.manage"))],
) -> MetricResponse:
    return await update_metric(db, context, model_id, metric_id, payload)


@models_router.delete(
    "/{model_id}/metrics/{metric_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def metrics_delete(
    model_id: UUID,
    metric_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_metric.manage"))],
) -> Response:
    await delete_metric(db, context, model_id, metric_id)
    return Response(status_code=204)


@models_router.get("/{model_id}/kpis", response_model=list[KpiResponse])
async def kpis_index(
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_model.read"))],
) -> list[KpiResponse]:
    return await list_kpis(db, context, model_id)


@models_router.post(
    "/{model_id}/kpis",
    response_model=KpiResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def kpis_create(
    model_id: UUID,
    payload: KpiCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_kpi.manage"))],
) -> KpiResponse:
    return await create_kpi(db, context, model_id, payload)


@models_router.patch(
    "/{model_id}/kpis/{kpi_id}", response_model=KpiResponse, dependencies=[Depends(require_csrf)]
)
async def kpis_update(
    model_id: UUID,
    kpi_id: UUID,
    payload: KpiCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_kpi.manage"))],
) -> KpiResponse:
    return await update_kpi(db, context, model_id, kpi_id, payload)


@models_router.delete(
    "/{model_id}/kpis/{kpi_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def kpis_delete(
    model_id: UUID,
    kpi_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("semantic_kpi.manage"))],
) -> Response:
    await delete_kpi(db, context, model_id, kpi_id)
    return Response(status_code=204)


@glossary_router.get("/domains", response_model=list[GlossaryDomainResponse])
async def domains_index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.read", "business_glossary"))
    ],
) -> list[GlossaryDomainResponse]:
    return await list_domains(db, context)


@glossary_router.post(
    "/domains",
    response_model=GlossaryDomainResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def domains_create(
    payload: GlossaryDomainCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.create", "business_glossary"))
    ],
) -> GlossaryDomainResponse:
    return await create_domain(db, context, payload)


@glossary_router.patch(
    "/domains/{domain_id}",
    response_model=GlossaryDomainResponse,
    dependencies=[Depends(require_csrf)],
)
async def domains_update(
    domain_id: UUID,
    payload: GlossaryDomainCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.update", "business_glossary"))
    ],
) -> GlossaryDomainResponse:
    return await update_domain(db, context, domain_id, payload)


@glossary_router.get("/terms", response_model=list[GlossaryTermResponse])
async def terms_index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.read", "business_glossary"))
    ],
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> list[GlossaryTermResponse]:
    return await list_terms(db, context, search)


@glossary_router.post(
    "/terms",
    response_model=GlossaryTermResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def terms_create(
    payload: GlossaryTermCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(_policy("glossary.create", "business_glossary", "glossary_terms.max")),
    ],
) -> GlossaryTermResponse:
    return await create_term(db, context, payload)


@glossary_router.get("/terms/{term_id}", response_model=GlossaryTermResponse)
async def terms_detail(
    term_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.read", "business_glossary"))
    ],
) -> GlossaryTermResponse:
    return await get_term(db, context, term_id)


@glossary_router.patch(
    "/terms/{term_id}", response_model=GlossaryTermResponse, dependencies=[Depends(require_csrf)]
)
async def terms_update(
    term_id: UUID,
    payload: GlossaryTermCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.update", "business_glossary"))
    ],
) -> GlossaryTermResponse:
    return await update_term(db, context, term_id, payload)


@glossary_router.post(
    "/terms/{term_id}/approve",
    response_model=GlossaryTermResponse,
    dependencies=[Depends(require_csrf)],
)
async def terms_approve(
    term_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.approve", "business_glossary"))
    ],
) -> GlossaryTermResponse:
    return await set_term_status(db, context, term_id, "approved")


@glossary_router.post(
    "/terms/{term_id}/deprecate",
    response_model=GlossaryTermResponse,
    dependencies=[Depends(require_csrf)],
)
async def terms_deprecate(
    term_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.deprecate", "business_glossary"))
    ],
) -> GlossaryTermResponse:
    return await set_term_status(db, context, term_id, "deprecated")


@glossary_router.post(
    "/terms/{term_id}/relationships",
    response_model=GlossaryRelationshipResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def relationships_create(
    term_id: UUID,
    payload: GlossaryRelationshipCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.update", "business_glossary"))
    ],
) -> GlossaryRelationshipResponse:
    return await create_term_relationship(db, context, term_id, payload)


@glossary_router.delete(
    "/terms/{term_id}/relationships/{relationship_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def relationships_delete(
    term_id: UUID,
    relationship_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.update", "business_glossary"))
    ],
) -> Response:
    await delete_term_relationship(db, context, term_id, relationship_id)
    return Response(status_code=204)


@glossary_router.post(
    "/terms/{term_id}/assignments",
    response_model=GlossaryAssignmentResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def assignments_create(
    term_id: UUID,
    payload: GlossaryAssignmentCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.assign", "business_glossary"))
    ],
) -> GlossaryAssignmentResponse:
    return await create_term_assignment(db, context, term_id, payload)


@glossary_router.delete(
    "/terms/{term_id}/assignments/{assignment_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def assignments_delete(
    term_id: UUID,
    assignment_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("glossary.assign", "business_glossary"))
    ],
) -> Response:
    await delete_term_assignment(db, context, term_id, assignment_id)
    return Response(status_code=204)


@query_router.post(
    "/semantic-query", response_model=SemanticQueryResult, dependencies=[Depends(require_csrf)]
)
async def semantic_query(
    payload: SemanticQueryRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(_policy("semantic.query", "semantic_query", "semantic_queries.per_day")),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
) -> SemanticQueryResult:
    return await execute_query(db, context, payload, settings, provider)
