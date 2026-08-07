"""Versioned pipeline authoring and asynchronous run APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import AuthenticatedContext, get_current_session, require_csrf
from vip_api.core.config import Settings, get_settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import (
    RequireGovernance,
    require_capability,
    require_governance,
)
from vip_api.pipelines.formula import (
    FUNCTION_CATALOG,
    parse_formula,
    referenced_fields,
    referenced_functions,
)
from vip_api.pipelines.models import PipelineArtifact
from vip_api.pipelines.schedule_services import (
    create_schedule,
    delete_schedule,
    list_schedule_runs,
    list_schedules,
    update_schedule,
)
from vip_api.pipelines.schemas import (
    ArtifactResponse,
    DownloadLink,
    FormulaValidationRequest,
    FormulaValidationResponse,
    ListPage,
    PipelineCreate,
    PipelineEditor,
    PipelineEditorSave,
    PipelineScheduleCreate,
    PipelineScheduleResponse,
    PipelineScheduleRunResponse,
    PipelineScheduleUpdate,
    PublishRequest,
    RestoreRequest,
    RunCreate,
    RunDetail,
    RunListPage,
    RunResponse,
    ValidationResponse,
    VersionResponse,
)
from vip_api.pipelines.services import (
    archive_pipeline,
    cancel_run,
    create_pipeline,
    create_run,
    get_editor,
    list_artifacts,
    list_pipelines,
    list_runs,
    list_versions,
    publish_pipeline,
    require_pipeline_access,
    restore_version,
    retry_run,
    run_detail,
    save_editor,
    validate_pipeline,
)
from vip_api.pipelines.storage import (
    ArtifactStorageError,
    DownloadClaims,
    DownloadTokens,
    PipelineArtifactStorage,
)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])
artifact_router = APIRouter(prefix="/pipeline-artifacts", tags=["pipeline artifacts"])


def gate(permission: str, *, quota: str | None = None) -> RequireGovernance:
    return require_governance(
        permission, feature="pipeline_studio", entitlement="pipeline_studio", quota=quota
    )


# Feature/entitlement-only gate (no broad pipeline.read). Read/list resolve the
# actual decision per-resource via the centralized evaluator, so a resource ACL
# grant elevates access without the broad workspace permission.
pipeline_capability = require_capability("pipeline_studio", "pipeline_studio")


@router.get("/formula-language")
async def formula_language(
    _context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> dict[str, object]:
    return {
        "version": 1,
        "field_syntax": "[field_name]",
        "functions": list(FUNCTION_CATALOG),
        "operators": [
            "+",
            "-",
            "*",
            "/",
            "==",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
            "and",
            "or",
            "not",
            "IF..THEN..ELSEIF..ELSE..ENDIF",
        ],
        "literals": ["number", "quoted string", "true", "false", "null"],
    }


@router.post(
    "/formula-language/validate",
    response_model=FormulaValidationResponse,
    dependencies=[Depends(require_csrf)],
)
async def formula_validate(
    payload: FormulaValidationRequest,
    _context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> FormulaValidationResponse:
    try:
        expression = parse_formula(
            payload.expression,
            set(payload.available_fields) if payload.available_fields else None,
        )
    except ApplicationError as exc:
        return FormulaValidationResponse(
            valid=False,
            errors=[exc.message],
            used_functions=[],
            used_fields=[],
        )
    return FormulaValidationResponse(
        valid=True,
        errors=[],
        used_functions=sorted(referenced_functions(expression)),
        used_fields=sorted(referenced_fields(expression)),
    )


@router.get("", response_model=ListPage)
async def index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> ListPage:
    return await list_pipelines(db, context, limit)


@router.post(
    "", response_model=PipelineEditor, status_code=201, dependencies=[Depends(require_csrf)]
)
async def create(
    payload: PipelineCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(gate("pipeline.create", quota="pipelines.max"))
    ],
) -> PipelineEditor:
    return await create_pipeline(db, context, payload)


@router.get("/{pipeline_id}", response_model=PipelineEditor)
async def show(
    pipeline_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
) -> PipelineEditor:
    # Resource-aware: an ACL grant (direct/group) elevates read without broad
    # pipeline.read; role, ownership, deny and expiration are all honoured. The
    # response carries the caller's effective access so the client can render
    # viewer/operator/developer/owner states from the enforced decision.
    await require_pipeline_access(db, context, pipeline_id, "viewer")
    return await get_editor(db, context, pipeline_id, is_platform_admin=auth.user.is_platform_admin)


@router.put("/{pipeline_id}", response_model=PipelineEditor, dependencies=[Depends(require_csrf)])
async def update(
    pipeline_id: UUID,
    payload: PipelineEditorSave,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> PipelineEditor:
    return await save_editor(db, context, pipeline_id, payload)


@router.delete("/{pipeline_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def archive(
    pipeline_id: UUID,
    expected_version: Annotated[int, Query(ge=1)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> Response:
    await archive_pipeline(db, context, pipeline_id, expected_version)
    return Response(status_code=204)


@router.post(
    "/{pipeline_id}/validate",
    response_model=ValidationResponse,
    dependencies=[Depends(require_csrf)],
)
async def validate(
    pipeline_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> ValidationResponse:
    return await validate_pipeline(db, context, pipeline_id)


@router.post(
    "/{pipeline_id}/publish",
    response_model=VersionResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def publish(
    pipeline_id: UUID,
    payload: PublishRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> VersionResponse:
    return await publish_pipeline(
        db, context, pipeline_id, payload.expected_version, payload.change_summary
    )


@router.get("/{pipeline_id}/versions", response_model=list[VersionResponse])
async def versions(
    pipeline_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> list[VersionResponse]:
    return await list_versions(db, context, pipeline_id)


@router.post(
    "/{pipeline_id}/versions/{version_id}/restore",
    response_model=PipelineEditor,
    dependencies=[Depends(require_csrf)],
)
async def restore(
    pipeline_id: UUID,
    version_id: UUID,
    payload: RestoreRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> PipelineEditor:
    return await restore_version(db, context, pipeline_id, version_id, payload.expected_version)


@router.post(
    "/{pipeline_id}/runs",
    response_model=RunResponse,
    status_code=202,
    dependencies=[Depends(require_csrf)],
)
async def run_create(
    pipeline_id: UUID,
    payload: RunCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> RunResponse:
    # Authorization is resource-level (operator+) inside create_run; monthly run
    # quota is enforced separately there so ACL operators are not blocked by
    # broad pipeline.execute while still consuming pipeline_runs.monthly.
    return await create_run(db, context, pipeline_id, payload.pipeline_version_id)


@router.get("/{pipeline_id}/runs", response_model=RunListPage)
async def runs(
    pipeline_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> RunListPage:
    return await list_runs(db, context, pipeline_id, limit)


@router.get("/{pipeline_id}/runs/{run_id}", response_model=RunDetail)
async def run_show(
    pipeline_id: UUID,
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> RunDetail:
    return await run_detail(db, context, pipeline_id, run_id)


@router.post(
    "/{pipeline_id}/runs/{run_id}/cancel",
    response_model=RunResponse,
    dependencies=[Depends(require_csrf)],
)
async def run_cancel(
    pipeline_id: UUID,
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> RunResponse:
    return await cancel_run(db, context, pipeline_id, run_id)


@router.post(
    "/{pipeline_id}/runs/{run_id}/retry",
    response_model=RunResponse,
    dependencies=[Depends(require_csrf)],
)
async def run_retry(
    pipeline_id: UUID,
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> RunResponse:
    # Same split as run_create: resource operator check + quota in retry_run.
    return await retry_run(db, context, pipeline_id, run_id)


@router.get("/{pipeline_id}/runs/{run_id}/artifacts", response_model=list[ArtifactResponse])
async def artifacts(
    pipeline_id: UUID,
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> list[ArtifactResponse]:
    return await list_artifacts(db, context, pipeline_id, run_id)


@router.post(
    "/{pipeline_id}/runs/{run_id}/artifacts/{artifact_id}/download-url",
    response_model=DownloadLink,
    dependencies=[Depends(require_csrf)],
)
async def artifact_link(
    pipeline_id: UUID,
    run_id: UUID,
    artifact_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DownloadLink:
    allowed = await list_artifacts(db, context, pipeline_id, run_id)
    if artifact_id not in {item.id for item in allowed}:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    assert context.workspace_id is not None
    token = DownloadTokens(
        settings.pipeline_download_signing_key, settings.PIPELINE_DOWNLOAD_TOKEN_TTL_SECONDS
    ).create(
        DownloadClaims(artifact_id, context.organization_id, context.workspace_id, context.user_id)
    )
    return DownloadLink(
        url=str(request.url_for("artifact_download")) + f"?token={token}",
        expires_in_seconds=settings.PIPELINE_DOWNLOAD_TOKEN_TTL_SECONDS,
    )


@artifact_router.get("/download", name="artifact_download")
async def artifact_download(
    token: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    try:
        claims = await DownloadTokens(
            settings.pipeline_download_signing_key, settings.PIPELINE_DOWNLOAD_TOKEN_TTL_SECONDS
        ).consume(token, request.app.state.redis.client, settings.JOB_QUEUE_PREFIX)
    except ArtifactStorageError as exc:
        raise ApplicationError(
            code="INVALID_DOWNLOAD_TOKEN",
            message="The download link is invalid or expired.",
            status_code=403,
        ) from exc
    if (
        claims.user_id != context.user_id
        or claims.organization_id != context.organization_id
        or claims.workspace_id != context.workspace_id
    ):
        raise ApplicationError(
            code="INVALID_DOWNLOAD_TOKEN",
            message="The download link is invalid or expired.",
            status_code=403,
        )
    artifact = await db.scalar(
        select(PipelineArtifact).where(
            PipelineArtifact.id == claims.artifact_id,
            PipelineArtifact.organization_id == claims.organization_id,
            PipelineArtifact.workspace_id == claims.workspace_id,
            PipelineArtifact.expires_at > func.now(),
        )
    )
    if artifact is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    try:
        path = PipelineArtifactStorage(settings.PIPELINE_ARTIFACT_ROOT).path(artifact.storage_key)
    except ArtifactStorageError as exc:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        ) from exc
    suffix = "json" if artifact.content_type == "application/json" else "csv"
    await record_audit(
        db,
        "pipeline.artifact.downloaded",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="pipeline_artifact",
        resource_id=artifact.id,
    )
    await db.commit()
    return FileResponse(
        path, media_type=artifact.content_type, filename=f"pipeline-result-{artifact.id}.{suffix}"
    )


# --- Pipeline run schedules (post-Core P1) ---------------------------------
# Resource-level authorization happens inside the service (viewer to read,
# operator to mutate), mirroring the on-demand run endpoints.


@router.get("/{pipeline_id}/schedules", response_model=list[PipelineScheduleResponse])
async def schedules_index(
    pipeline_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> list[PipelineScheduleResponse]:
    return await list_schedules(db, context, pipeline_id)


@router.post(
    "/{pipeline_id}/schedules",
    response_model=PipelineScheduleResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def schedule_create(
    pipeline_id: UUID,
    payload: PipelineScheduleCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> PipelineScheduleResponse:
    return await create_schedule(db, context, pipeline_id, payload)


@router.put(
    "/{pipeline_id}/schedules/{schedule_id}",
    response_model=PipelineScheduleResponse,
    dependencies=[Depends(require_csrf)],
)
async def schedule_update(
    pipeline_id: UUID,
    schedule_id: UUID,
    payload: PipelineScheduleUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> PipelineScheduleResponse:
    return await update_schedule(db, context, pipeline_id, schedule_id, payload)


@router.delete(
    "/{pipeline_id}/schedules/{schedule_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def schedule_delete(
    pipeline_id: UUID,
    schedule_id: UUID,
    expected_version: Annotated[int, Query(ge=1)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> Response:
    await delete_schedule(db, context, pipeline_id, schedule_id, expected_version)
    return Response(status_code=204)


@router.get(
    "/{pipeline_id}/schedules/{schedule_id}/runs",
    response_model=list[PipelineScheduleRunResponse],
)
async def schedule_runs(
    pipeline_id: UUID,
    schedule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(pipeline_capability)],
) -> list[PipelineScheduleRunResponse]:
    return await list_schedule_runs(db, context, pipeline_id, schedule_id)
