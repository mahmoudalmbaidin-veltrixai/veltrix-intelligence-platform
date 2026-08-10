"""Tenant-scoped pipeline aggregate, version, and run services."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import utc_now
from vip_api.core.errors import ApplicationError
from vip_api.governance import resource_access_service
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import consume_quota
from vip_api.pipelines.models import (
    Pipeline,
    PipelineArtifact,
    PipelineEdge,
    PipelineNode,
    PipelineNodeRun,
    PipelineOutboxEvent,
    PipelineRun,
    PipelineRunLog,
    PipelineVersion,
)
from vip_api.pipelines.schemas import (
    ArtifactResponse,
    EdgeInput,
    ListPage,
    LogResponse,
    NodeInput,
    NodeRunResponse,
    PipelineAccess,
    PipelineCreate,
    PipelineEditor,
    PipelineEditorSave,
    PipelineSummary,
    RunDetail,
    RunListPage,
    RunResponse,
    ValidationResponse,
    VersionResponse,
)
from vip_api.pipelines.validation import validate_graph


def _scope(context: AuthorizationContext) -> tuple[UUID, UUID]:
    if context.workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=400
        )
    return context.organization_id, context.workspace_id


def _slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:100]
    return value or "pipeline"


def _reject_unpersistable_draft(validation: ValidationResponse) -> None:
    unsafe = {"UNSUPPORTED_NODE_TYPE", "UNKNOWN_CONFIG_FIELD"}
    unavailable_sources = {
        "DATASET_NOT_FOUND",
        "SOURCE_UNAVAILABLE",
        "SOURCE_SCHEMA_CHANGED",
        "SOURCE_FIELD_NOT_FOUND",
    }
    codes = {issue.code for issue in validation.errors}
    if codes & unavailable_sources:
        raise ApplicationError(
            code="PIPELINE_SOURCE_UNAVAILABLE",
            message="A selected dataset is unavailable, changed, or no longer accessible.",
            status_code=422,
        )
    if codes & unsafe:
        raise ApplicationError(
            code="INVALID_PIPELINE",
            message="The pipeline contains unsupported configuration.",
            status_code=422,
        )


async def _authorize_pipeline(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    action_level: str,
) -> None:
    """Authoritative per-resource pipeline decision via the centralized evaluator.

    Combines role-derived level, direct/group ACL grants, ownership, explicit
    deny and expiration into a single decision so a resource ACL *elevates*
    access without the broad workspace permission. An explicit deny yields a
    ``403 RESOURCE_ACCESS_DENIED``; any other denial (no grant, expired,
    insufficient level) yields a non-disclosing ``404``.
    """
    decision = await resource_access_service.check_access(
        db,
        resource_type="pipeline",
        resource_id=pipeline_id,
        action_level=action_level,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        role_permissions=context.permissions,
    )
    if decision.allowed:
        return
    if decision.reason == "EXPLICIT_DENY":
        raise ApplicationError(
            code="RESOURCE_ACCESS_DENIED",
            message="Access to this resource is denied by an explicit permission rule.",
            status_code=403,
        )
    raise ApplicationError(
        code="NOT_FOUND", message="The requested resource was not found.", status_code=404
    )


async def pipeline_access(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    *,
    is_platform_admin: bool = False,
) -> PipelineAccess:
    """Resolve the caller's effective pipeline access for client-side UI states.

    Uses the same centralized evaluator that enforces every action, so the
    returned capability flags exactly mirror what the backend will allow —
    the frontend consumes this to render viewer/operator/developer/owner (and
    denied) states, never as the security boundary itself.
    """
    result = await resource_access_service.effective_access(
        db,
        resource_type="pipeline",
        resource_id=pipeline_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        is_platform_admin=is_platform_admin,
        role_permissions=context.permissions,
    )
    allowed = set(result.allowed_levels)
    return PipelineAccess(
        level=result.level,
        allowed_levels=result.allowed_levels,
        can_view="viewer" in allowed,
        can_run="operator" in allowed,
        can_edit="developer" in allowed,
        can_manage="owner" in allowed,
        source=result.source,
        reason=result.reason,
    )


async def _pipeline(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    *,
    action_level: str = "viewer",
) -> Pipeline:
    org, ws = _scope(context)
    item = await db.scalar(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.organization_id == org,
            Pipeline.workspace_id == ws,
            Pipeline.archived_at.is_(None),
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await _authorize_pipeline(db, context, item.id, action_level)
    return item


async def _summary(db: AsyncSession, item: Pipeline) -> PipelineSummary:
    node_count = (
        await db.scalar(
            select(func.count())
            .select_from(PipelineNode)
            .where(PipelineNode.pipeline_id == item.id)
        )
        or 0
    )
    latest_run = await db.scalar(
        select(PipelineRun)
        .where(
            PipelineRun.pipeline_id == item.id,
            PipelineRun.organization_id == item.organization_id,
            PipelineRun.workspace_id == item.workspace_id,
        )
        .order_by(PipelineRun.created_at.desc())
        .limit(1)
    )
    published = (
        await db.get(PipelineVersion, item.published_version_id)
        if item.published_version_id
        else None
    )
    return PipelineSummary(
        id=item.id,
        name=item.name,
        description=item.description,
        slug=item.slug,
        status=item.status,
        tags=item.tags,
        row_version=item.row_version,
        published_version=published.version_number if published else None,
        node_count=node_count,
        last_run_at=latest_run.created_at if latest_run else None,
        last_run_status=latest_run.status if latest_run else None,
        updated_at=item.updated_at,
    )


async def require_pipeline_access(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    action_level: str = "viewer",
) -> Pipeline:
    """Resource-aware access guard that *elevates* as well as restricts.

    Unlike ``_pipeline``'s deny-only ``enforce_resource_guard``, this runs the
    centralized evaluator so a user who holds a resource ACL grant (direct or via
    group) can reach the pipeline even without the broad ``pipeline.read``
    workspace permission. Role-derived level, ownership, explicit deny and
    expiration are all honoured by the single evaluator. A denied decision is
    reported as a non-disclosing 404.
    """
    return await _pipeline(db, context, pipeline_id, action_level=action_level)


async def list_pipelines(
    db: AsyncSession, context: AuthorizationContext, limit: int = 100
) -> ListPage:
    org, ws = _scope(context)
    query = select(Pipeline).where(
        Pipeline.organization_id == org,
        Pipeline.workspace_id == ws,
        Pipeline.archived_at.is_(None),
    )
    # Users with a broad workspace pipeline role see every pipeline (unchanged).
    # Otherwise the collection is filtered to resources reachable through
    # ownership or a non-expired ACL allow (direct or group), minus viewer-level
    # denies — matching the centralized evaluator's visibility semantics.
    subjects = {context.user_id} | await resource_access_service.group_ids_for_user(
        db, org, context.user_id
    )
    allowed_ids, denied_ids = resource_access_service.collection_visibility_subqueries(
        "pipeline", subjects, now=datetime.now(UTC)
    )
    query = query.where(Pipeline.id.notin_(denied_ids))
    if resource_access_service.role_level("pipeline", context.permissions) is None:
        query = query.where(
            or_(Pipeline.owner_user_id == context.user_id, Pipeline.id.in_(allowed_ids)),
        )
    rows = (await db.scalars(query.order_by(Pipeline.updated_at.desc()).limit(limit))).all()
    return ListPage(items=[await _summary(db, item) for item in rows])


async def create_pipeline(
    db: AsyncSession, context: AuthorizationContext, payload: PipelineCreate
) -> PipelineEditor:
    org, ws = _scope(context)
    validation = await validate_graph(db, context, payload.nodes, payload.edges)
    # Drafts may be incomplete, but unsafe contracts and stale/inaccessible
    # governed source references are never persisted.
    _reject_unpersistable_draft(validation)
    base = _slug(payload.name)
    slug = base
    suffix = 2
    while await db.scalar(
        select(Pipeline.id).where(
            Pipeline.organization_id == org, Pipeline.workspace_id == ws, Pipeline.slug == slug
        )
    ):
        slug = f"{base[:94]}-{suffix}"
        suffix += 1
    item = Pipeline(
        organization_id=org,
        workspace_id=ws,
        slug=slug,
        name=payload.name.strip(),
        description=payload.description,
        owner_user_id=context.user_id,
        tags=payload.tags,
        canvas=payload.canvas,
    )
    db.add(item)
    await db.flush()
    for node in payload.nodes:
        db.add(
            PipelineNode(
                id=node.id,
                organization_id=org,
                workspace_id=ws,
                pipeline_id=item.id,
                node_key=node.key,
                node_type=node.type,
                title=node.title,
                position_x=node.x,
                position_y=node.y,
                configuration=node.config,
            )
        )
    for edge in payload.edges:
        db.add(
            PipelineEdge(
                id=edge.id,
                organization_id=org,
                workspace_id=ws,
                pipeline_id=item.id,
                edge_key=edge.key,
                source_node_key=edge.source,
                target_node_key=edge.target,
                source_port=edge.source_port,
                target_port=edge.target_port,
            )
        )
    await record_audit(
        db,
        "pipeline.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="pipeline",
        resource_id=item.id,
    )
    await db.commit()
    return await get_editor(db, context, item.id)


async def get_editor(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    *,
    is_platform_admin: bool = False,
) -> PipelineEditor:
    item = await _pipeline(db, context, pipeline_id)
    nodes = (
        await db.scalars(
            select(PipelineNode)
            .where(PipelineNode.pipeline_id == item.id)
            .order_by(PipelineNode.node_key)
        )
    ).all()
    edges = (
        await db.scalars(
            select(PipelineEdge)
            .where(PipelineEdge.pipeline_id == item.id)
            .order_by(PipelineEdge.edge_key)
        )
    ).all()
    return PipelineEditor(
        pipeline=await _summary(db, item),
        canvas=item.canvas,
        nodes=[
            NodeInput(
                id=n.id,
                key=n.node_key,
                type=n.node_type,
                title=n.title,
                x=n.position_x,
                y=n.position_y,
                config=n.configuration,
            )
            for n in nodes
        ],
        edges=[
            EdgeInput(
                id=e.id,
                key=e.edge_key,
                source=e.source_node_key,
                target=e.target_node_key,
                source_port=e.source_port,
                target_port=e.target_port,
            )
            for e in edges
        ],
        access=await pipeline_access(db, context, item.id, is_platform_admin=is_platform_admin),
    )


async def save_editor(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, payload: PipelineEditorSave
) -> PipelineEditor:
    item = await _pipeline(db, context, pipeline_id, action_level="developer")
    if item.row_version != payload.expected_version:
        raise ApplicationError(
            code="VERSION_CONFLICT",
            message="The pipeline changed after it was loaded. Reload before saving.",
            status_code=409,
        )
    validation = await validate_graph(db, context, payload.nodes, payload.edges)
    _reject_unpersistable_draft(validation)
    org, ws = _scope(context)
    await db.execute(delete(PipelineEdge).where(PipelineEdge.pipeline_id == item.id))
    await db.execute(delete(PipelineNode).where(PipelineNode.pipeline_id == item.id))
    for node in payload.nodes:
        db.add(
            PipelineNode(
                id=node.id,
                organization_id=org,
                workspace_id=ws,
                pipeline_id=item.id,
                node_key=node.key,
                node_type=node.type,
                title=node.title,
                position_x=node.x,
                position_y=node.y,
                configuration=node.config,
            )
        )
    for edge in payload.edges:
        db.add(
            PipelineEdge(
                id=edge.id,
                organization_id=org,
                workspace_id=ws,
                pipeline_id=item.id,
                edge_key=edge.key,
                source_node_key=edge.source,
                target_node_key=edge.target,
                source_port=edge.source_port,
                target_port=edge.target_port,
            )
        )
    item.name, item.description, item.tags, item.canvas = (
        payload.name.strip(),
        payload.description,
        payload.tags,
        payload.canvas,
    )
    item.slug = item.slug or _slug(item.name)
    # A saved draft diverges from any previously published version, so the
    # pipeline returns to the ``draft`` state — this is what re-enables Publish for
    # a subsequent immutable version. The last published version stays viewable
    # and runnable via ``published_version_id`` (unchanged here), and existing runs
    # keep their original ``pipeline_version_id`` linkage.
    item.status = "draft"
    item.row_version += 1
    item.updated_at = utc_now()
    await record_audit(
        db,
        "pipeline.draft.saved",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="pipeline",
        resource_id=item.id,
        metadata={"row_version": item.row_version, "node_count": len(payload.nodes)},
    )
    await db.commit()
    return await get_editor(db, context, item.id)


async def validate_pipeline(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID
) -> ValidationResponse:
    # Validation is a Developer capability (it validates draft edits).
    await _pipeline(db, context, pipeline_id, action_level="developer")
    editor = await get_editor(db, context, pipeline_id)
    return await validate_graph(db, context, editor.nodes, editor.edges)


def _snapshot(editor: PipelineEditor) -> dict[str, object]:
    return {
        "schema_version": 1,
        "pipeline": {
            "name": editor.pipeline.name,
            "description": editor.pipeline.description,
            "tags": editor.pipeline.tags,
        },
        "canvas": editor.canvas,
        "nodes": [n.model_dump(mode="json") for n in editor.nodes],
        "edges": [e.model_dump(mode="json") for e in editor.edges],
    }


async def publish_pipeline(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    expected_version: int,
    change_summary: str,
) -> VersionResponse:
    item = await _pipeline(db, context, pipeline_id, action_level="developer")
    if item.row_version != expected_version:
        raise ApplicationError(
            code="VERSION_CONFLICT",
            message="The pipeline changed after it was loaded.",
            status_code=409,
        )
    validation = await validate_pipeline(db, context, pipeline_id)
    if not validation.valid or not validation.topological_order:
        raise ApplicationError(
            code="PIPELINE_INVALID",
            message="Resolve pipeline validation errors before publishing.",
            status_code=422,
        )
    editor = await get_editor(db, context, pipeline_id)
    snapshot = _snapshot(editor)
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    number = (
        await db.scalar(
            select(func.max(PipelineVersion.version_number)).where(
                PipelineVersion.pipeline_id == item.id
            )
        )
        or 0
    ) + 1
    version = PipelineVersion(
        organization_id=item.organization_id,
        workspace_id=item.workspace_id,
        pipeline_id=item.id,
        version_number=number,
        snapshot=snapshot,
        content_sha256=hashlib.sha256(canonical).hexdigest(),
        change_summary=change_summary,
        created_by_user_id=context.user_id,
    )
    db.add(version)
    await db.flush()
    item.published_version_id = version.id
    item.status = "published"
    item.row_version += 1
    await record_audit(
        db,
        "pipeline.published",
        actor_user_id=context.user_id,
        organization_id=item.organization_id,
        workspace_id=item.workspace_id,
        resource_type="pipeline",
        resource_id=item.id,
        metadata={"version": number, "content_sha256": version.content_sha256},
    )
    await db.commit()
    await db.refresh(version)
    return VersionResponse.model_validate(version)


async def list_versions(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID
) -> list[VersionResponse]:
    item = await _pipeline(db, context, pipeline_id)
    rows = (
        await db.scalars(
            select(PipelineVersion)
            .where(
                PipelineVersion.pipeline_id == item.id,
                PipelineVersion.organization_id == item.organization_id,
                PipelineVersion.workspace_id == item.workspace_id,
            )
            .order_by(PipelineVersion.version_number.desc())
        )
    ).all()
    return [VersionResponse.model_validate(row) for row in rows]


async def restore_version(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    version_id: UUID,
    expected_version: int,
) -> PipelineEditor:
    item = await _pipeline(db, context, pipeline_id, action_level="developer")
    if item.row_version != expected_version:
        raise ApplicationError(
            code="VERSION_CONFLICT",
            message="The pipeline changed after it was loaded.",
            status_code=409,
        )
    version = await db.scalar(
        select(PipelineVersion).where(
            PipelineVersion.id == version_id,
            PipelineVersion.pipeline_id == item.id,
            PipelineVersion.organization_id == item.organization_id,
            PipelineVersion.workspace_id == item.workspace_id,
        )
    )
    if version is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    snapshot = version.snapshot
    meta = cast(dict[str, object], snapshot["pipeline"])
    canvas = cast(dict[str, object], snapshot.get("canvas", {}))
    snapshot_nodes = cast(list[object], snapshot["nodes"])
    snapshot_edges = cast(list[object], snapshot["edges"])
    payload = PipelineEditorSave(
        name=str(meta["name"]),
        description=str(meta.get("description", "")),
        tags=cast(list[str], meta.get("tags", [])),
        expected_version=expected_version,
        canvas=canvas,
        nodes=[NodeInput.model_validate(n) for n in snapshot_nodes],
        edges=[EdgeInput.model_validate(e) for e in snapshot_edges],
    )
    result = await save_editor(db, context, pipeline_id, payload)
    await record_audit(
        db,
        "pipeline.version.restored",
        actor_user_id=context.user_id,
        organization_id=item.organization_id,
        workspace_id=item.workspace_id,
        resource_type="pipeline",
        resource_id=item.id,
        metadata={"source_version": version.version_number},
        commit=True,
    )
    return result


async def archive_pipeline(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, expected_version: int
) -> None:
    item = await _pipeline(db, context, pipeline_id, action_level="owner")
    if item.row_version != expected_version:
        raise ApplicationError(
            code="VERSION_CONFLICT",
            message="The pipeline changed after it was loaded.",
            status_code=409,
        )
    item.archived_at = utc_now()
    item.status = "archived"
    item.row_version += 1
    await record_audit(
        db,
        "pipeline.archived",
        actor_user_id=context.user_id,
        organization_id=item.organization_id,
        workspace_id=item.workspace_id,
        resource_type="pipeline",
        resource_id=item.id,
    )
    await db.commit()


def run_response(run: PipelineRun) -> RunResponse:
    return RunResponse.model_validate(run)


async def create_run(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    version_id: UUID | None = None,
    *,
    trigger: str = "manual",
) -> RunResponse:
    item = await _pipeline(db, context, pipeline_id, action_level="operator")
    selected = version_id or item.published_version_id
    if selected is None:
        raise ApplicationError(
            code="PIPELINE_NOT_PUBLISHED",
            message="Publish the pipeline before running it.",
            status_code=422,
        )
    version = await db.scalar(
        select(PipelineVersion).where(
            PipelineVersion.id == selected,
            PipelineVersion.pipeline_id == item.id,
            PipelineVersion.organization_id == item.organization_id,
            PipelineVersion.workspace_id == item.workspace_id,
        )
    )
    if version is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested version was not found.", status_code=404
        )
    # Quota is orthogonal to resource authorization: an ACL operator may run
    # without broad pipeline.execute, but still consumes monthly run quota.
    await consume_quota(db, context, "pipeline_runs.monthly")
    run = PipelineRun(
        organization_id=item.organization_id,
        workspace_id=item.workspace_id,
        pipeline_id=item.id,
        pipeline_version_id=version.id,
        requested_by_user_id=context.user_id,
        correlation_id=context.correlation_id,
        trigger=trigger,
    )
    db.add(run)
    await db.flush()
    db.add(
        PipelineOutboxEvent(
            organization_id=item.organization_id,
            workspace_id=item.workspace_id,
            run_id=run.id,
            event_type="pipeline.run.queued",
            attempt_number=1,
            payload={
                "run_id": str(run.id),
                "organization_id": str(item.organization_id),
                "workspace_id": str(item.workspace_id),
            },
        )
    )
    await record_audit(
        db,
        "pipeline.run.queued",
        actor_user_id=context.user_id,
        organization_id=item.organization_id,
        workspace_id=item.workspace_id,
        resource_type="pipeline_run",
        resource_id=run.id,
        metadata={"pipeline_id": str(item.id), "version": version.version_number},
    )
    await db.commit()
    await db.refresh(run)
    return run_response(run)


async def _run(
    db: AsyncSession,
    context: AuthorizationContext,
    pipeline_id: UUID,
    run_id: UUID,
    *,
    action_level: str = "viewer",
) -> PipelineRun:
    org, ws = _scope(context)
    run = await db.scalar(
        select(PipelineRun).where(
            PipelineRun.id == run_id,
            PipelineRun.pipeline_id == pipeline_id,
            PipelineRun.organization_id == org,
            PipelineRun.workspace_id == ws,
        )
    )
    if run is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await _authorize_pipeline(db, context, pipeline_id, action_level)
    return run


async def list_runs(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, limit: int = 100
) -> RunListPage:
    item = await _pipeline(db, context, pipeline_id)
    rows = (
        await db.scalars(
            select(PipelineRun)
            .where(
                PipelineRun.pipeline_id == item.id,
                PipelineRun.organization_id == item.organization_id,
                PipelineRun.workspace_id == item.workspace_id,
            )
            .order_by(PipelineRun.created_at.desc())
            .limit(limit)
        )
    ).all()
    return RunListPage(items=[run_response(row) for row in rows])


async def run_detail(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, run_id: UUID
) -> RunDetail:
    run = await _run(db, context, pipeline_id, run_id)
    nodes = (
        await db.scalars(
            select(PipelineNodeRun)
            .where(
                PipelineNodeRun.run_id == run.id,
                PipelineNodeRun.attempt_number == run.current_attempt,
                PipelineNodeRun.organization_id == run.organization_id,
                PipelineNodeRun.workspace_id == run.workspace_id,
            )
            .order_by(PipelineNodeRun.started_at)
        )
    ).all()
    logs = (
        await db.scalars(
            select(PipelineRunLog)
            .where(
                PipelineRunLog.run_id == run.id,
                PipelineRunLog.organization_id == run.organization_id,
                PipelineRunLog.workspace_id == run.workspace_id,
            )
            .order_by(PipelineRunLog.sequence)
            .limit(1000)
        )
    ).all()
    return RunDetail(
        **run_response(run).model_dump(),
        nodes=[NodeRunResponse.model_validate(n) for n in nodes],
        logs=[LogResponse.model_validate(log) for log in logs],
    )


async def cancel_run(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, run_id: UUID
) -> RunResponse:
    run = await _run(db, context, pipeline_id, run_id, action_level="operator")
    if run.status not in {"queued", "running", "retrying"}:
        raise ApplicationError(
            code="RUN_NOT_CANCELLABLE",
            message="This run can no longer be cancelled.",
            status_code=409,
        )
    run.cancellation_requested = True
    if run.status in {"queued", "retrying"}:
        run.status = "cancelled"
        run.completed_at = utc_now()
    await record_audit(
        db,
        "pipeline.run.cancel.requested",
        actor_user_id=context.user_id,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        resource_type="pipeline_run",
        resource_id=run.id,
    )
    await db.commit()
    await db.refresh(run)
    return run_response(run)


async def retry_run(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, run_id: UUID
) -> RunResponse:
    run = await _run(db, context, pipeline_id, run_id, action_level="operator")
    if run.status != "failed":
        raise ApplicationError(
            code="RUN_NOT_RETRYABLE", message="Only failed runs can be retried.", status_code=409
        )
    if run.current_attempt >= run.max_attempts:
        raise ApplicationError(
            code="RUN_RETRY_LIMIT", message="The run retry limit has been reached.", status_code=409
        )
    await consume_quota(db, context, "pipeline_runs.monthly")
    next_attempt = run.current_attempt + 1
    run.status = "retrying"
    run.progress = 0
    run.rows_processed = 0
    run.result_summary = {}
    run.cancellation_requested = False
    run.safe_error_code = None
    run.safe_error_message = None
    run.available_at = utc_now()
    run.completed_at = None
    db.add(
        PipelineOutboxEvent(
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            run_id=run.id,
            event_type="pipeline.run.retry.queued",
            attempt_number=next_attempt,
            payload={
                "run_id": str(run.id),
                "organization_id": str(run.organization_id),
                "workspace_id": str(run.workspace_id),
            },
        )
    )
    await record_audit(
        db,
        "pipeline.run.retry.queued",
        actor_user_id=context.user_id,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        resource_type="pipeline_run",
        resource_id=run.id,
        metadata={"attempt": next_attempt},
    )
    await db.commit()
    await db.refresh(run)
    return run_response(run)


async def list_artifacts(
    db: AsyncSession, context: AuthorizationContext, pipeline_id: UUID, run_id: UUID
) -> list[ArtifactResponse]:
    run = await _run(db, context, pipeline_id, run_id)
    rows = (
        await db.scalars(
            select(PipelineArtifact).where(
                PipelineArtifact.run_id == run.id,
                PipelineArtifact.organization_id == run.organization_id,
                PipelineArtifact.workspace_id == run.workspace_id,
                PipelineArtifact.expires_at > datetime.now(UTC),
            )
        )
    ).all()
    return [ArtifactResponse.model_validate(row) for row in rows]
