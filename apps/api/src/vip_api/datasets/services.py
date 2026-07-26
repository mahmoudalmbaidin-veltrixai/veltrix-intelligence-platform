"""Dataset catalog orchestration with tenant, secret, and audit boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.secrets import SecretProvider
from vip_api.core.errors import ApplicationError
from vip_api.datasets.discovery import MetadataDiscoveryAdapterRegistry
from vip_api.datasets.models import (
    Dataset,
    DatasetField,
    DatasetLineageEdge,
    DatasetQualityEvaluation,
    DatasetQualityResult,
    DatasetQualityRule,
)
from vip_api.datasets.repositories import DatasetRepository
from vip_api.datasets.schemas import (
    DatasetCreate,
    DatasetFieldResponse,
    DatasetFieldUpdate,
    DatasetListResponse,
    DatasetResponse,
    DatasetUpdate,
    DiscoveryRequest,
    DiscoveryResult,
    LineageCreate,
    LineageEdgeResponse,
    LineageGraph,
    QualityEvaluationResponse,
    QualityResultResponse,
    QualityRuleCreate,
    QualityRuleResponse,
    QualitySummary,
)
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import consume_quota


def _scope(context: AuthorizationContext) -> tuple[UUID, UUID]:
    if context.workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    return context.organization_id, context.workspace_id


def source_key(connection_id: UUID, catalog: str, schema: str, name: str, object_type: str) -> str:
    raw = "\x1f".join(
        (str(connection_id), catalog.casefold(), schema.casefold(), name.casefold(), object_type)
    )
    return sha256(raw.encode()).hexdigest()


async def _connection(
    db: AsyncSession, context: AuthorizationContext, connection_id: UUID
) -> tuple[Connection, ConnectionType]:
    org, ws = _scope(context)
    row = (
        (
            await db.execute(
                select(Connection, ConnectionType)
                .join(ConnectionType, ConnectionType.id == Connection.connection_type_id)
                .where(
                    Connection.id == connection_id,
                    Connection.organization_id == org,
                    Connection.workspace_id == ws,
                    Connection.archived_at.is_(None),
                )
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    connection, kind = row
    if connection.status != "active" or not kind.is_enabled:
        raise ApplicationError(
            code="CONNECTION_UNAVAILABLE",
            message="The selected connection is unavailable.",
            status_code=422,
        )
    return connection, kind


async def list_datasets(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    page: int,
    page_size: int,
    search: str | None,
    status: str | None,
) -> DatasetListResponse:
    org, ws = _scope(context)
    items, total = await DatasetRepository(db, org, ws).list_scoped(
        page=page, page_size=page_size, search=search, status=status
    )
    return DatasetListResponse(
        items=[DatasetResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


async def get_dataset(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID
) -> DatasetResponse:
    org, ws = _scope(context)
    item = await DatasetRepository(db, org, ws).get(dataset_id)
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    return DatasetResponse.model_validate(item)


async def create_dataset(
    db: AsyncSession, context: AuthorizationContext, payload: DatasetCreate
) -> DatasetResponse:
    org, ws = _scope(context)
    await _connection(db, context, payload.connection_id)
    key = source_key(
        payload.connection_id,
        payload.source_catalog,
        payload.source_schema,
        payload.source_name,
        payload.dataset_type,
    )
    existing = await db.scalar(
        select(Dataset).where(
            Dataset.organization_id == org, Dataset.workspace_id == ws, Dataset.source_key == key
        )
    )
    if existing is not None:
        return DatasetResponse.model_validate(existing)
    await consume_quota(db, context, "datasets.max")
    item = Dataset(
        organization_id=org,
        workspace_id=ws,
        connection_id=payload.connection_id,
        dataset_type=payload.dataset_type,
        source_catalog=payload.source_catalog,
        source_schema=payload.source_schema,
        source_name=payload.source_name,
        source_key=key,
        qualified_name=".".join(
            filter(None, (payload.source_catalog, payload.source_schema, payload.source_name))
        ),
        display_name=payload.display_name or payload.source_name,
        description=payload.description,
        source_object_type=payload.dataset_type,
        is_read_only=payload.is_read_only,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
        last_discovered_at=datetime.now(UTC),
    )
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "dataset.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="dataset",
        resource_id=item.id,
    )
    await db.commit()
    return DatasetResponse.model_validate(item)


async def update_dataset(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID, payload: DatasetUpdate
) -> DatasetResponse:
    org, ws = _scope(context)
    item = await DatasetRepository(db, org, ws).get(dataset_id)
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    if item.version != payload.version:
        raise ApplicationError(
            code="VERSION_CONFLICT",
            message="The resource was changed by another request.",
            status_code=409,
        )
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if "documentation_url" in changes and changes["documentation_url"] is not None:
        changes["documentation_url"] = str(changes["documentation_url"])
    for key, value in changes.items():
        setattr(item, key, value)
    item.version += 1
    item.updated_by_user_id = context.user_id
    await record_audit(
        db,
        "dataset.updated",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="dataset",
        resource_id=item.id,
        metadata={"fields": sorted(changes)},
    )
    await db.commit()
    return DatasetResponse.model_validate(item)


async def archive_dataset(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID
) -> None:
    org, ws = _scope(context)
    item = await DatasetRepository(db, org, ws).get(dataset_id)
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    item.status = "archived"
    item.archived_at = datetime.now(UTC)
    item.version += 1
    await record_audit(
        db,
        "dataset.archived",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="dataset",
        resource_id=item.id,
    )
    await db.commit()


async def list_fields(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID
) -> list[DatasetFieldResponse]:
    org, ws = _scope(context)
    if await DatasetRepository(db, org, ws).get(dataset_id) is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    return [
        DatasetFieldResponse.model_validate(item)
        for item in await DatasetRepository(db, org, ws).fields(dataset_id)
    ]


async def update_field(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
    field_id: UUID,
    payload: DatasetFieldUpdate,
) -> DatasetFieldResponse:
    org, ws = _scope(context)
    item = await db.scalar(
        select(DatasetField).where(
            DatasetField.id == field_id,
            DatasetField.dataset_id == dataset_id,
            DatasetField.organization_id == org,
            DatasetField.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    if item.version != payload.version:
        raise ApplicationError(
            code="VERSION_CONFLICT",
            message="The resource was changed by another request.",
            status_code=409,
        )
    for key, value in payload.model_dump(exclude_unset=True, exclude={"version"}).items():
        setattr(item, key, value)
    item.version += 1
    await record_audit(
        db,
        "dataset.field.updated",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="dataset_field",
        resource_id=item.id,
    )
    await db.commit()
    return DatasetFieldResponse.model_validate(item)


async def discover(
    db: AsyncSession,
    context: AuthorizationContext,
    payload: DiscoveryRequest,
    provider: SecretProvider,
    registry: MetadataDiscoveryAdapterRegistry,
) -> DiscoveryResult:
    org, ws = _scope(context)
    connection, kind = await _connection(db, context, payload.connection_id)
    if "metadata_discovery" not in kind.capabilities or connection.secret_id is None:
        raise ApplicationError(
            code="DISCOVERY_UNSUPPORTED",
            message="Metadata discovery is not supported for this connection.",
            status_code=422,
        )
    await consume_quota(db, context, "metadata_discoveries.per_day")
    credentials = await provider.read_secret(
        db,
        organization_id=org,
        workspace_id=ws,
        connection_id=connection.id,
        secret_id=connection.secret_id,
    )
    discovered, truncated = await registry.get(kind.key).discover(
        connection.configuration,
        credentials,
        catalog=payload.catalog,
        schemas=payload.schemas,
        object_types=list(payload.include_object_types),
        include_names=payload.include_names,
        exclude_names=payload.exclude_names,
    )
    persisted: list[Dataset] = []
    now = datetime.now(UTC)
    for obj in discovered:
        key = source_key(connection.id, obj.catalog, obj.schema, obj.name, obj.object_type)
        item = await db.scalar(
            select(Dataset).where(
                Dataset.organization_id == org,
                Dataset.workspace_id == ws,
                Dataset.source_key == key,
            )
        )
        if item is None:
            item = Dataset(
                organization_id=org,
                workspace_id=ws,
                connection_id=connection.id,
                dataset_type=obj.object_type,
                source_catalog=obj.catalog,
                source_schema=obj.schema,
                source_name=obj.name,
                source_key=key,
                qualified_name=f"{obj.catalog}.{obj.schema}.{obj.name}",
                display_name=obj.name,
                source_object_type=obj.object_type,
                row_count_estimate=obj.estimated_row_count,
                size_bytes_estimate=obj.estimated_size_bytes,
                created_by_user_id=context.user_id,
                updated_by_user_id=context.user_id,
            )
            db.add(item)
            await db.flush()
        item.discovery_status = "discovered"
        item.last_discovered_at = now
        item.last_metadata_refresh_at = now
        if payload.persist:
            existing_fields = {
                field.source_name: field
                for field in await DatasetRepository(db, org, ws).fields(item.id)
            }
            for field in obj.fields:
                target = existing_fields.get(field.name)
                if target is None:
                    target = DatasetField(
                        organization_id=org,
                        workspace_id=ws,
                        dataset_id=item.id,
                        source_name=field.name,
                        display_name=field.name,
                        ordinal_position=field.ordinal_position,
                        physical_data_type=field.physical_type,
                        normalized_data_type=field.normalized_type,
                        role="timestamp"
                        if field.normalized_type in {"date", "datetime"}
                        else "attribute",
                        is_nullable=field.nullable,
                        max_length=field.max_length,
                        precision=field.precision,
                        scale=field.scale,
                    )
                    db.add(target)
                else:
                    target.ordinal_position = field.ordinal_position
                    target.physical_data_type = field.physical_type
                    target.normalized_data_type = field.normalized_type
                    target.is_nullable = field.nullable
            persisted.append(item)
    await record_audit(
        db,
        "dataset.discovery.succeeded",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="connection",
        resource_id=connection.id,
        metadata={
            "object_count": len(discovered),
            "persisted_count": len(persisted),
            "truncated": truncated,
        },
    )
    await db.commit()
    return DiscoveryResult(
        datasets=[DatasetResponse.model_validate(item) for item in persisted],
        discovered_count=len(discovered),
        persisted_count=len(persisted),
        truncated=truncated,
        warnings=[],
        correlation_id=context.correlation_id,
    )


async def quality_summary(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID
) -> QualitySummary:
    org, ws = _scope(context)
    if await DatasetRepository(db, org, ws).get(dataset_id) is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    latest = await db.scalar(
        select(DatasetQualityEvaluation)
        .where(
            DatasetQualityEvaluation.organization_id == org,
            DatasetQualityEvaluation.workspace_id == ws,
            DatasetQualityEvaluation.dataset_id == dataset_id,
            DatasetQualityEvaluation.completed_at.is_not(None),
        )
        .order_by(DatasetQualityEvaluation.created_at.desc())
        .limit(1)
    )
    if latest is None:
        total = int(
            await db.scalar(
                select(func.count())
                .select_from(DatasetQualityRule)
                .where(
                    DatasetQualityRule.organization_id == org,
                    DatasetQualityRule.workspace_id == ws,
                    DatasetQualityRule.dataset_id == dataset_id,
                    DatasetQualityRule.is_enabled.is_(True),
                )
            )
            or 0
        )
        return QualitySummary(
            status="not_evaluated",
            score=None,
            total_rules=total,
            passing=0,
            warning=0,
            failing=0,
            not_evaluated=total,
        )
    return QualitySummary(
        status=latest.status,
        score=latest.score,
        total_rules=latest.total_rules,
        passing=latest.passing,
        warning=latest.warning,
        failing=latest.failing,
        not_evaluated=latest.unknown,
    )


async def create_quality_evaluation(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
) -> DatasetQualityEvaluation:
    org, ws = _scope(context)
    await get_dataset(db, context, dataset_id)
    item = DatasetQualityEvaluation(
        organization_id=org,
        workspace_id=ws,
        dataset_id=dataset_id,
        created_by_user_id=context.user_id,
    )
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "dataset.quality_evaluation.queued",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="dataset_quality_evaluation",
        resource_id=item.id,
        metadata={"dataset_id": str(dataset_id)},
    )
    await db.commit()
    return item


async def list_quality_evaluations(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
    *,
    limit: int = 50,
) -> list[QualityEvaluationResponse]:
    org, ws = _scope(context)
    await get_dataset(db, context, dataset_id)
    rows = (
        await db.scalars(
            select(DatasetQualityEvaluation)
            .where(
                DatasetQualityEvaluation.organization_id == org,
                DatasetQualityEvaluation.workspace_id == ws,
                DatasetQualityEvaluation.dataset_id == dataset_id,
            )
            .order_by(DatasetQualityEvaluation.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [QualityEvaluationResponse.model_validate(row) for row in rows]


async def list_quality_rules(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID
) -> list[QualityRuleResponse]:
    org, ws = _scope(context)
    await get_dataset(db, context, dataset_id)
    rows = (
        await db.scalars(
            select(DatasetQualityRule)
            .where(
                DatasetQualityRule.organization_id == org,
                DatasetQualityRule.workspace_id == ws,
                DatasetQualityRule.dataset_id == dataset_id,
            )
            .order_by(DatasetQualityRule.name)
        )
    ).all()
    return [QualityRuleResponse.model_validate(row) for row in rows]


async def create_quality_rule(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID, payload: QualityRuleCreate
) -> QualityRuleResponse:
    org, ws = _scope(context)
    await get_dataset(db, context, dataset_id)
    if (
        payload.field_id
        and await db.scalar(
            select(DatasetField.id).where(
                DatasetField.id == payload.field_id,
                DatasetField.dataset_id == dataset_id,
                DatasetField.organization_id == org,
                DatasetField.workspace_id == ws,
            )
        )
        is None
    ):
        raise ApplicationError(
            code="INVALID_FIELD",
            message="The selected field is not part of this dataset.",
            status_code=422,
        )
    item = DatasetQualityRule(
        organization_id=org,
        workspace_id=ws,
        dataset_id=dataset_id,
        field_id=payload.field_id,
        rule_type=payload.rule_type,
        name=payload.name,
        description=payload.description,
        configuration=payload.configuration,
        severity=payload.severity,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
    )
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "dataset.quality_rule.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="quality_rule",
        resource_id=item.id,
    )
    await db.commit()
    return QualityRuleResponse.model_validate(item)


async def update_quality_rule(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
    rule_id: UUID,
    payload: QualityRuleCreate,
) -> QualityRuleResponse:
    org, ws = _scope(context)
    item = await db.scalar(
        select(DatasetQualityRule).where(
            DatasetQualityRule.id == rule_id,
            DatasetQualityRule.dataset_id == dataset_id,
            DatasetQualityRule.organization_id == org,
            DatasetQualityRule.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.updated_by_user_id = context.user_id
    await record_audit(
        db,
        "dataset.quality_rule.updated",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="quality_rule",
        resource_id=item.id,
    )
    await db.commit()
    return QualityRuleResponse.model_validate(item)


async def list_quality_results(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID
) -> list[QualityResultResponse]:
    org, ws = _scope(context)
    await get_dataset(db, context, dataset_id)
    rows = (
        await db.scalars(
            select(DatasetQualityResult)
            .join(DatasetQualityRule, DatasetQualityRule.id == DatasetQualityResult.quality_rule_id)
            .where(
                DatasetQualityResult.organization_id == org,
                DatasetQualityResult.workspace_id == ws,
                DatasetQualityRule.dataset_id == dataset_id,
            )
            .order_by(DatasetQualityResult.evaluated_at.desc())
            .limit(500)
        )
    ).all()
    return [QualityResultResponse.model_validate(row) for row in rows]


async def delete_quality_rule(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID, rule_id: UUID
) -> None:
    org, ws = _scope(context)
    item = await db.scalar(
        select(DatasetQualityRule).where(
            DatasetQualityRule.id == rule_id,
            DatasetQualityRule.dataset_id == dataset_id,
            DatasetQualityRule.organization_id == org,
            DatasetQualityRule.workspace_id == ws,
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await record_audit(
        db,
        "dataset.quality_rule.deleted",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="quality_rule",
        resource_id=rule_id,
    )
    await db.commit()


async def create_lineage(
    db: AsyncSession, context: AuthorizationContext, source_id: UUID, payload: LineageCreate
) -> LineageEdgeResponse:
    org, ws = _scope(context)
    if source_id == payload.target_dataset_id:
        raise ApplicationError(
            code="INVALID_LINEAGE", message="A dataset cannot reference itself.", status_code=422
        )
    if (
        await DatasetRepository(db, org, ws).get(source_id) is None
        or await DatasetRepository(db, org, ws).get(payload.target_dataset_id) is None
    ):
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    item = DatasetLineageEdge(
        organization_id=org,
        workspace_id=ws,
        source_dataset_id=source_id,
        target_dataset_id=payload.target_dataset_id,
        lineage_type=payload.lineage_type,
        description=payload.description,
        created_by_user_id=context.user_id,
    )
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "dataset.lineage.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="lineage_edge",
        resource_id=item.id,
    )
    await db.commit()
    return LineageEdgeResponse.model_validate(item)


async def delete_lineage(
    db: AsyncSession, context: AuthorizationContext, dataset_id: UUID, edge_id: UUID
) -> None:
    org, ws = _scope(context)
    item = await db.scalar(
        select(DatasetLineageEdge).where(
            DatasetLineageEdge.id == edge_id,
            DatasetLineageEdge.organization_id == org,
            DatasetLineageEdge.workspace_id == ws,
            or_(
                DatasetLineageEdge.source_dataset_id == dataset_id,
                DatasetLineageEdge.target_dataset_id == dataset_id,
            ),
        )
    )
    if item is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    await db.delete(item)
    await record_audit(
        db,
        "dataset.lineage.deleted",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="lineage_edge",
        resource_id=edge_id,
    )
    await db.commit()


async def lineage_graph(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
    *,
    direction: str,
    depth: int,
    max_nodes: int,
) -> LineageGraph:
    org, ws = _scope(context)
    root = await DatasetRepository(db, org, ws).get(dataset_id)
    if root is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    nodes: dict[UUID, Dataset] = {root.id: root}
    edges: dict[UUID, DatasetLineageEdge] = {}
    frontier = {root.id}
    truncated = False
    for _ in range(depth):
        conditions = []
        if direction in {"downstream", "both"}:
            conditions.append(DatasetLineageEdge.source_dataset_id.in_(frontier))
        if direction in {"upstream", "both"}:
            conditions.append(DatasetLineageEdge.target_dataset_id.in_(frontier))
        if not conditions:
            break
        rows = list(
            (
                await db.scalars(
                    select(DatasetLineageEdge).where(
                        DatasetLineageEdge.organization_id == org,
                        DatasetLineageEdge.workspace_id == ws,
                        or_(*conditions),
                    )
                )
            ).all()
        )
        next_ids = {
            value for row in rows for value in (row.source_dataset_id, row.target_dataset_id)
        } - set(nodes)
        if len(nodes) + len(next_ids) > max_nodes:
            next_ids = set(list(sorted(next_ids, key=str))[: max_nodes - len(nodes)])
            truncated = True
        if next_ids:
            for item in (
                await db.scalars(
                    select(Dataset).where(
                        Dataset.organization_id == org,
                        Dataset.workspace_id == ws,
                        Dataset.id.in_(next_ids),
                    )
                )
            ).all():
                nodes[item.id] = item
        for row in rows:
            if row.source_dataset_id in nodes and row.target_dataset_id in nodes:
                edges[row.id] = row
        frontier = next_ids
        if not frontier or truncated:
            break
    return LineageGraph(
        nodes=[DatasetResponse.model_validate(item) for item in nodes.values()],
        edges=[LineageEdgeResponse.model_validate(item) for item in edges.values()],
        truncated=truncated,
        max_depth=depth,
    )
