"""Live Dataset Studio APIs."""

from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import AuthenticatedContext, get_current_session, require_csrf
from vip_api.connections.dependencies import get_secret_provider
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings, get_settings
from vip_api.database.session import get_db_session
from vip_api.datasets.dependencies import RequireB5Governance
from vip_api.datasets.discovery import MetadataDiscoveryAdapterRegistry
from vip_api.datasets.ingestion import ingest_csv, ingest_csv_file
from vip_api.datasets.preview import preview_dataset, profile_dataset
from vip_api.datasets.schemas import (
    CsvIngestRequest,
    DatasetActivityPage,
    DatasetCertifyRequest,
    DatasetCreate,
    DatasetFieldResponse,
    DatasetFieldUpdate,
    DatasetListResponse,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetResponse,
    DatasetRevokeCertificationRequest,
    DatasetUpdate,
    DatasetVersionResponse,
    DatasetVersionRestore,
    DiscoveryRequest,
    DiscoveryResult,
    FileCsvIngestRequest,
    LineageCreate,
    LineageEdgeResponse,
    LineageGraph,
    QualityEvaluationResponse,
    QualityIncidentPage,
    QualityResultResponse,
    QualityRuleCreate,
    QualityRuleOverviewPage,
    QualityRuleResponse,
    QualitySummary,
)
from vip_api.datasets.services import (
    archive_dataset,
    certify_dataset,
    create_dataset,
    create_lineage,
    create_quality_evaluation,
    create_quality_rule,
    delete_lineage,
    delete_quality_rule,
    discover,
    get_dataset,
    get_dataset_version,
    lineage_graph,
    list_dataset_activity,
    list_dataset_versions,
    list_datasets,
    list_fields,
    list_quality_evaluations,
    list_quality_incident_overview,
    list_quality_results,
    list_quality_rule_overview,
    list_quality_rules,
    quality_summary,
    require_dataset_access,
    restore_dataset_version,
    revoke_dataset_certification,
    update_dataset,
    update_field,
    update_quality_rule,
)
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_capability
from vip_api.jobs import handlers as _handlers  # noqa: F401
from vip_api.jobs.queue import RedisJobQueue
from vip_api.jobs.registry import registry
from vip_api.jobs.schemas import JobCreate, JobResponse
from vip_api.jobs.services import create_job
from vip_api.redis.client import RedisClient

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _policy(
    permission: str, *, feature: str = "dataset_studio", quota: str | None = None
) -> object:
    return RequireB5Governance(permission, feature=feature, quota=quota)


# Feature/entitlement-only gates (no broad dataset.* permission) for resource-bound
# routes: the specific dataset's access is decided per-resource by the centralized
# evaluator inside the service, so an ACL grant elevates access without the broad
# workspace permission. Creation/discovery keep their RBAC + quota gates.
dataset_capability = require_capability("dataset_studio", "dataset_studio")
quality_capability = require_capability("data_quality", "dataset_studio")
lineage_capability = require_capability("data_lineage", "dataset_studio")


@lru_cache(maxsize=1)
def get_discovery_registry() -> MetadataDiscoveryAdapterRegistry:
    return MetadataDiscoveryAdapterRegistry(get_settings())


def _queue(request: Request) -> RedisJobQueue:
    settings: Settings = request.app.state.settings
    client: RedisClient = request.app.state.redis
    return RedisJobQueue(client.client, settings.JOB_QUEUE_PREFIX)


@router.get("", response_model=DatasetListResponse)
async def datasets_index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[
        Literal["active", "inactive", "archived"] | None, Query(alias="status")
    ] = None,
) -> DatasetListResponse:
    return await list_datasets(
        db, context, page=page, page_size=page_size, search=search, status=status_filter
    )


# Bounded workspace-wide Quality aggregates (VIP-BUG-004). Declared before the
# ``/{dataset_id}`` routes so the literal ``quality`` prefix is never captured as
# a dataset id. These replace the former per-dataset rule/incident fan-out with a
# single paginated call each, while enforcing the same collection authorization.
@router.get("/quality/rules", response_model=QualityRuleOverviewPage)
async def quality_rules_overview(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[
        Literal["passing", "warning", "failing", "unknown", "not_evaluated"] | None,
        Query(alias="status"),
    ] = None,
) -> QualityRuleOverviewPage:
    return await list_quality_rule_overview(
        db, context, page=page, page_size=page_size, search=search, status=status_filter
    )


@router.get("/quality/incidents", response_model=QualityIncidentPage)
async def quality_incidents_overview(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> QualityIncidentPage:
    return await list_quality_incident_overview(
        db, context, page=page, page_size=page_size
    )


@router.post(
    "", response_model=DatasetResponse, status_code=201, dependencies=[Depends(require_csrf)]
)
async def datasets_create(
    payload: DatasetCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("dataset.create", quota="datasets.max"))
    ],
) -> DatasetResponse:
    return await create_dataset(db, context, payload)


@router.post("/discover", response_model=DiscoveryResult, dependencies=[Depends(require_csrf)])
async def datasets_discover(
    payload: DiscoveryRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("dataset.discover"))],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
    registry: Annotated[MetadataDiscoveryAdapterRegistry, Depends(get_discovery_registry)],
) -> DiscoveryResult:
    return await discover(db, context, payload, provider, registry)


@router.post("/ingest-csv", response_model=DiscoveryResult, dependencies=[Depends(require_csrf)])
async def datasets_ingest_csv(
    payload: CsvIngestRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("dataset.create", quota="datasets.max"))
    ],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
    registry: Annotated[MetadataDiscoveryAdapterRegistry, Depends(get_discovery_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscoveryResult:
    return await ingest_csv(db, context, payload, provider, registry, settings)


@router.post(
    "/ingest-file",
    response_model=DiscoveryResult,
    dependencies=[Depends(require_csrf)],
)
async def datasets_ingest_file(
    payload: FileCsvIngestRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("dataset.create", quota="datasets.max"))
    ],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
    registry: Annotated[MetadataDiscoveryAdapterRegistry, Depends(get_discovery_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscoveryResult:
    return await ingest_csv_file(
        db,
        context,
        payload.file_id,
        payload.connection_id,
        payload.source_schema,
        payload.source_name,
        payload.display_name,
        payload.description,
        provider,
        registry,
        settings,
        sheet_name=payload.sheet_name,
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def datasets_detail(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
) -> DatasetResponse:
    return await get_dataset(db, context, dataset_id, is_platform_admin=auth.user.is_platform_admin)


@router.patch("/{dataset_id}", response_model=DatasetResponse, dependencies=[Depends(require_csrf)])
async def datasets_update(
    dataset_id: UUID,
    payload: DatasetUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> DatasetResponse:
    return await update_dataset(db, context, dataset_id, payload)


@router.post(
    "/{dataset_id}/certify",
    response_model=DatasetResponse,
    dependencies=[Depends(require_csrf)],
)
async def datasets_certify(
    dataset_id: UUID,
    payload: DatasetCertifyRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> DatasetResponse:
    return await certify_dataset(
        db, context, dataset_id, version=payload.version, note=payload.note
    )


@router.post(
    "/{dataset_id}/certification/revoke",
    response_model=DatasetResponse,
    dependencies=[Depends(require_csrf)],
)
async def datasets_revoke_certification(
    dataset_id: UUID,
    payload: DatasetRevokeCertificationRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> DatasetResponse:
    return await revoke_dataset_certification(
        db, context, dataset_id, version=payload.version, note=payload.note
    )


@router.get("/{dataset_id}/activity", response_model=DatasetActivityPage)
async def datasets_activity(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DatasetActivityPage:
    return await list_dataset_activity(db, context, dataset_id, limit=limit, offset=offset)


@router.post("/{dataset_id}/archive", status_code=204, dependencies=[Depends(require_csrf)])
async def datasets_archive(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> Response:
    await archive_dataset(db, context, dataset_id)
    return Response(status_code=204)


@router.delete("/{dataset_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def datasets_delete(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> Response:
    await archive_dataset(db, context, dataset_id)
    return Response(status_code=204)


@router.get("/{dataset_id}/fields", response_model=list[DatasetFieldResponse])
async def fields_index(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> list[DatasetFieldResponse]:
    return await list_fields(db, context, dataset_id)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def preview_show(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DatasetPreviewResponse:
    # Preview streams sample rows; enforce read access on the specific dataset.
    await require_dataset_access(db, context, dataset_id, "query")
    return await preview_dataset(db, context, dataset_id, page, page_size, provider, settings)


@router.get("/{dataset_id}/profile", response_model=DatasetProfileResponse)
async def profile_show(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetProfileResponse:
    await require_dataset_access(db, context, dataset_id, "query")
    return await profile_dataset(db, context, dataset_id, provider, settings)


@router.patch(
    "/{dataset_id}/fields/{field_id}",
    response_model=DatasetFieldResponse,
    dependencies=[Depends(require_csrf)],
)
async def fields_update(
    dataset_id: UUID,
    field_id: UUID,
    payload: DatasetFieldUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> DatasetFieldResponse:
    return await update_field(db, context, dataset_id, field_id, payload)


@router.get("/{dataset_id}/quality", response_model=QualitySummary)
async def quality_detail(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
) -> QualitySummary:
    return await quality_summary(db, context, dataset_id)


@router.post(
    "/{dataset_id}/quality-evaluations",
    response_model=JobResponse,
    status_code=202,
    dependencies=[Depends(require_csrf)],
)
async def quality_evaluations_create(
    request: Request,
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
) -> JobResponse:
    evaluation = await create_quality_evaluation(db, context, dataset_id)
    settings: Settings = request.app.state.settings
    job = await create_job(
        db,
        context,
        JobCreate(
            job_type="system",
            handler="dataset.quality",
            name="Evaluate dataset quality",
            payload={"quality_evaluation_id": str(evaluation.id)},
            idempotency_key=f"quality-{evaluation.id}-{uuid4().hex[:12]}",
            max_attempts=3,
            timeout_seconds=settings.PIPELINE_RUN_TIMEOUT_SECONDS,
        ),
        settings,
        _queue(request),
        registry,
    )
    evaluation.job_id = job.id
    await db.commit()
    return job


@router.get(
    "/{dataset_id}/quality-evaluations",
    response_model=list[QualityEvaluationResponse],
)
async def quality_evaluations_index(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[QualityEvaluationResponse]:
    return await list_quality_evaluations(db, context, dataset_id, limit=limit)


@router.get("/{dataset_id}/quality-rules", response_model=list[QualityRuleResponse])
async def quality_rules_index(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
) -> list[QualityRuleResponse]:
    return await list_quality_rules(db, context, dataset_id)


@router.post(
    "/{dataset_id}/quality-rules",
    response_model=QualityRuleResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def quality_rules_create(
    dataset_id: UUID,
    payload: QualityRuleCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
) -> QualityRuleResponse:
    return await create_quality_rule(db, context, dataset_id, payload)


@router.patch(
    "/{dataset_id}/quality-rules/{rule_id}",
    response_model=QualityRuleResponse,
    dependencies=[Depends(require_csrf)],
)
async def quality_rules_update(
    dataset_id: UUID,
    rule_id: UUID,
    payload: QualityRuleCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
) -> QualityRuleResponse:
    return await update_quality_rule(db, context, dataset_id, rule_id, payload)


@router.get("/{dataset_id}/quality-results", response_model=list[QualityResultResponse])
async def quality_results_index(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
) -> list[QualityResultResponse]:
    return await list_quality_results(db, context, dataset_id)


@router.delete(
    "/{dataset_id}/quality-rules/{rule_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def quality_rules_delete(
    dataset_id: UUID,
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(quality_capability)],
) -> Response:
    await delete_quality_rule(db, context, dataset_id, rule_id)
    return Response(status_code=204)


@router.get("/{dataset_id}/lineage", response_model=LineageGraph)
async def lineage_detail(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(lineage_capability)],
    direction: Literal["upstream", "downstream", "both"] = "both",
    depth: Annotated[int, Query(ge=1)] = 3,
    max_nodes: Annotated[int, Query(ge=1)] = 100,
) -> LineageGraph:
    settings = get_settings()
    return await lineage_graph(
        db,
        context,
        dataset_id,
        direction=direction,
        depth=min(depth, settings.LINEAGE_MAX_DEPTH),
        max_nodes=min(max_nodes, settings.LINEAGE_MAX_NODES),
    )


@router.post(
    "/{dataset_id}/lineage",
    response_model=LineageEdgeResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def lineage_create(
    dataset_id: UUID,
    payload: LineageCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(lineage_capability)],
) -> LineageEdgeResponse:
    return await create_lineage(db, context, dataset_id, payload)


@router.delete(
    "/{dataset_id}/lineage/{edge_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def lineage_delete(
    dataset_id: UUID,
    edge_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(lineage_capability)],
) -> Response:
    await delete_lineage(db, context, dataset_id, edge_id)
    return Response(status_code=204)


# --- Dataset versions (post-Core P2) ---------------------------------------
# Resource-level authorization is enforced inside the service: list/get require
# query, restore requires edit.


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionResponse])
async def dataset_versions_index(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> list[DatasetVersionResponse]:
    return await list_dataset_versions(db, context, dataset_id)


@router.get("/{dataset_id}/versions/{version_id}", response_model=DatasetVersionResponse)
async def dataset_version_detail(
    dataset_id: UUID,
    version_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> DatasetVersionResponse:
    return await get_dataset_version(db, context, dataset_id, version_id)


@router.post(
    "/{dataset_id}/versions/{version_id}/restore",
    response_model=DatasetResponse,
    dependencies=[Depends(require_csrf)],
)
async def dataset_version_restore(
    dataset_id: UUID,
    version_id: UUID,
    payload: DatasetVersionRestore,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dataset_capability)],
) -> DatasetResponse:
    return await restore_dataset_version(
        db, context, dataset_id, version_id, payload.expected_version
    )
