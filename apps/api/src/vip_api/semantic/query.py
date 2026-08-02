"""Safe PostgreSQL semantic planner, compiler, and bounded read-only executor."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.network import UnsafeDestinationError, validate_host
from vip_api.connections.secrets import SecretProvider
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.governance import resource_access_service
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import consume_quota
from vip_api.semantic.models import (
    SemanticDimension,
    SemanticMeasure,
    SemanticMetric,
    SemanticModel,
)
from vip_api.semantic.schemas import (
    QueryColumn,
    QueryExecution,
    SemanticQueryRequest,
    SemanticQueryResult,
)


@dataclass(frozen=True, slots=True)
class CompiledReadOnlyQuery:
    statement: str
    parameters: tuple[object, ...]
    columns: tuple[QueryColumn, ...]
    referenced_dataset_id: UUID
    fingerprint_material: str


def quote_identifier(value: str) -> str:
    """Quote a metadata-resolved identifier; never call with browser-provided text."""
    if not value or "\x00" in value:
        raise ValueError("Invalid metadata identifier")
    return '"' + value.replace('"', '""') + '"'


_AGGREGATIONS = {
    "sum": "SUM",
    "count": "COUNT",
    "count_distinct": "COUNT",
    "average": "AVG",
    "min": "MIN",
    "max": "MAX",
}
_OPERATORS = {
    "equals": "=",
    "not_equals": "<>",
    "greater_than": ">",
    "greater_than_or_equal": ">=",
    "less_than": "<",
    "less_than_or_equal": "<=",
}


class PostgreSQLSemanticQueryCompiler:
    def compile(
        self,
        request: SemanticQueryRequest,
        dataset: Dataset,
        dimensions: dict[str, tuple[SemanticDimension, DatasetField]],
        metrics: dict[str, tuple[SemanticMetric, SemanticMeasure, DatasetField | None]],
        ratio_metrics: dict[
            str,
            tuple[
                SemanticMetric,
                tuple[SemanticMeasure, DatasetField | None],
                tuple[SemanticMeasure, DatasetField | None],
            ],
        ]
        | None = None,
    ) -> CompiledReadOnlyQuery:
        ratio_metrics = ratio_metrics or {}

        def measure_expression(measure: SemanticMeasure, field: DatasetField | None) -> str:
            aggregation = _AGGREGATIONS[measure.aggregation]
            if measure.aggregation == "count" and field is None:
                return "COUNT(*)"
            assert field is not None
            if measure.aggregation == "count_distinct":
                return f"COUNT(DISTINCT {quote_identifier(field.source_name)})"
            return f"{aggregation}({quote_identifier(field.source_name)})"

        selected: list[str] = []
        groups: list[str] = []
        columns: list[QueryColumn] = []
        for key in request.dimensions:
            dimension, field = dimensions[key]
            expression = quote_identifier(field.source_name)
            alias = quote_identifier(key)
            selected.append(f"{expression} AS {alias}")
            groups.append(expression)
            columns.append(
                QueryColumn(
                    key=key,
                    label=dimension.name,
                    data_type=dimension.data_type,
                    role="dimension",
                    format=dimension.format or {},
                )
            )
        for key in request.metrics:
            if key in metrics:
                metric, measure, metric_field = metrics[key]
                expression = measure_expression(measure, metric_field)
                data_type = measure.data_type
            else:
                metric, numerator, denominator = ratio_metrics[key]
                numerator_expression = measure_expression(*numerator)
                denominator_expression = measure_expression(*denominator)
                expression = f"({numerator_expression}) / NULLIF(({denominator_expression}), 0)"
                data_type = "decimal"
            selected.append(f"{expression} AS {quote_identifier(key)}")
            columns.append(
                QueryColumn(
                    key=key,
                    label=metric.name,
                    data_type=data_type,
                    role="metric",
                    format=metric.format or {},
                )
            )
        parameters: list[object] = []
        where: list[str] = []
        all_fields = {key: pair[1] for key, pair in dimensions.items()}
        for item in request.filters:
            field = all_fields[item.field]
            identifier = quote_identifier(field.source_name)
            if item.operator in {"is_null", "is_not_null"}:
                where.append(
                    f"{identifier} IS {'NOT ' if item.operator == 'is_not_null' else ''}NULL"
                )
            elif item.operator in {"in", "not_in"}:
                assert isinstance(item.value, list)
                placeholders = []
                for value in item.value:
                    parameters.append(value)
                    placeholders.append(f"${len(parameters)}")
                where.append(
                    f"{identifier} {'NOT ' if item.operator == 'not_in' else ''}IN "
                    f"({', '.join(placeholders)})"
                )
            elif item.operator == "between":
                assert isinstance(item.value, list)
                parameters.extend(item.value)
                where.append(f"{identifier} BETWEEN ${len(parameters) - 1} AND ${len(parameters)}")
            elif item.operator in {"contains", "starts_with", "ends_with"}:
                value = str(item.value)
                parameters.append(
                    f"%{value}%"
                    if item.operator == "contains"
                    else f"{value}%"
                    if item.operator == "starts_with"
                    else f"%{value}"
                )
                where.append(f"{identifier} LIKE ${len(parameters)}")
            else:
                parameters.append(item.value)
                where.append(f"{identifier} {_OPERATORS[item.operator]} ${len(parameters)}")
        # Only server-resolved metadata identifiers reach this compiler. Values remain parameters.
        source = (
            f"{quote_identifier(dataset.source_schema)}.{quote_identifier(dataset.source_name)}"
        )
        statement = f"SELECT {', '.join(selected)} FROM {source}"  # noqa: S608
        if where:
            statement += " WHERE " + " AND ".join(where)
        if groups:
            statement += " GROUP BY " + ", ".join(groups)
        if request.order_by:
            statement += " ORDER BY " + ", ".join(
                f"{quote_identifier(item.field)} {item.direction.upper()}"
                for item in request.order_by
            )
        parameters.extend((request.limit, request.offset))
        statement += f" LIMIT ${len(parameters) - 1} OFFSET ${len(parameters)}"
        if ";" in statement or "--" in statement or "/*" in statement:
            raise RuntimeError("Compiler emitted an unsafe statement")
        return CompiledReadOnlyQuery(
            statement,
            tuple(parameters),
            tuple(columns),
            dataset.id,
            f"{dataset.id}:{','.join(request.metrics)}:{','.join(request.dimensions)}:{len(request.filters)}",
        )


def _normalize(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


async def execute_query(
    db: AsyncSession,
    context: AuthorizationContext,
    request: SemanticQueryRequest,
    settings: Settings,
    provider: SecretProvider,
) -> SemanticQueryResult:
    if context.workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    org, ws = context.organization_id, context.workspace_id
    if (
        len(request.metrics) > settings.SEMANTIC_QUERY_MAX_METRICS
        or len(request.dimensions) > settings.SEMANTIC_QUERY_MAX_DIMENSIONS
        or len(request.filters) > settings.SEMANTIC_QUERY_MAX_FILTERS
        or len(request.order_by) > settings.SEMANTIC_QUERY_MAX_ORDER_FIELDS
    ):
        raise ApplicationError(
            code="QUERY_LIMIT_EXCEEDED",
            message="The semantic query exceeds a configured limit.",
            status_code=422,
        )
    for item in request.filters:
        if isinstance(item.value, list) and len(item.value) > settings.SEMANTIC_QUERY_MAX_IN_VALUES:
            raise ApplicationError(
                code="QUERY_LIMIT_EXCEEDED",
                message="A filter contains too many values.",
                status_code=422,
            )
    limit = request.limit or settings.SEMANTIC_QUERY_DEFAULT_LIMIT
    if (
        limit > settings.SEMANTIC_QUERY_MAX_LIMIT
        or request.offset > settings.SEMANTIC_QUERY_MAX_OFFSET
    ):
        raise ApplicationError(
            code="QUERY_LIMIT_EXCEEDED",
            message="The semantic query exceeds a configured limit.",
            status_code=422,
        )
    request.limit = limit
    model = await db.scalar(
        select(SemanticModel).where(
            SemanticModel.id == request.semantic_model_id,
            SemanticModel.organization_id == org,
            SemanticModel.workspace_id == ws,
            SemanticModel.status == "published",
        )
    )
    if model is None:
        raise ApplicationError(
            code="NOT_FOUND", message="The requested resource was not found.", status_code=404
        )
    # A user must never EXECUTE a semantic model they cannot access. This is the
    # single chokepoint for every execution path (direct query, dashboard widgets,
    # dashboard exports, scheduled delivery, background workers), so enforcing the
    # centralized query-level decision here covers them all. The decision is live —
    # a revoked grant or new deny blocks future executions immediately. Explicit
    # deny -> 403; no grant / insufficient level -> non-disclosing 404.
    await resource_access_service.authorize_resource(
        db,
        context,
        resource_type="semantic_model",
        resource_id=model.id,
        action_level="query",
    )
    dataset = await db.scalar(
        select(Dataset).where(
            Dataset.id == model.primary_dataset_id,
            Dataset.organization_id == org,
            Dataset.workspace_id == ws,
            Dataset.status == "active",
        )
    )
    if dataset is None:
        raise ApplicationError(
            code="SEMANTIC_MODEL_INVALID",
            message="The semantic model is not queryable.",
            status_code=422,
        )
    dim_rows = (
        (
            await db.execute(
                select(SemanticDimension, DatasetField)
                .join(DatasetField, DatasetField.id == SemanticDimension.field_id)
                .where(
                    SemanticDimension.semantic_model_id == model.id,
                    SemanticDimension.organization_id == org,
                    SemanticDimension.workspace_id == ws,
                )
            )
        )
        .tuples()
        .all()
    )
    dimensions = {
        item.key: (item, field)
        for item, field in dim_rows
        if not item.is_hidden and not field.is_hidden and not field.is_sensitive
    }
    if any(key not in dimensions for key in request.dimensions) or any(
        item.field not in dimensions for item in request.filters
    ):
        raise ApplicationError(
            code="QUERY_FIELD_INVALID",
            message="A requested dimension is unavailable.",
            status_code=422,
        )
    measure_rows = (
        (
            await db.execute(
                select(SemanticMetric, SemanticMeasure, DatasetField)
                .join(SemanticMeasure, SemanticMeasure.id == SemanticMetric.base_measure_id)
                .outerjoin(DatasetField, DatasetField.id == SemanticMeasure.field_id)
                .where(
                    SemanticMetric.semantic_model_id == model.id,
                    SemanticMetric.organization_id == org,
                    SemanticMetric.workspace_id == ws,
                    SemanticMetric.metric_type == "measure",
                )
            )
        )
        .tuples()
        .all()
    )
    metrics: dict[str, tuple[SemanticMetric, SemanticMeasure, DatasetField | None]] = {
        metric.key: (metric, measure, field)
        for metric, measure, field in measure_rows
        if not measure.is_hidden
        and (field is None or (not field.is_hidden and not field.is_sensitive))
    }
    measure_metrics_by_id = {item[0].id: item for item in metrics.values()}
    ratio_rows = (
        (
            await db.execute(
                select(SemanticMetric).where(
                    SemanticMetric.semantic_model_id == model.id,
                    SemanticMetric.organization_id == org,
                    SemanticMetric.workspace_id == ws,
                    SemanticMetric.metric_type == "ratio",
                )
            )
        )
        .scalars()
        .all()
    )
    ratio_metrics: dict[
        str,
        tuple[
            SemanticMetric,
            tuple[SemanticMeasure, DatasetField | None],
            tuple[SemanticMeasure, DatasetField | None],
        ],
    ] = {}
    for metric in ratio_rows:
        if metric.numerator_metric_id is None or metric.denominator_metric_id is None:
            continue
        numerator = measure_metrics_by_id.get(metric.numerator_metric_id)
        denominator = measure_metrics_by_id.get(metric.denominator_metric_id)
        if numerator is not None and denominator is not None:
            ratio_metrics[metric.key] = (
                metric,
                (numerator[1], numerator[2]),
                (denominator[1], denominator[2]),
            )
    if any(key not in metrics and key not in ratio_metrics for key in request.metrics):
        raise ApplicationError(
            code="QUERY_METRIC_INVALID",
            message="A requested metric is unavailable.",
            status_code=422,
        )
    allowed_order = set(request.dimensions) | set(request.metrics)
    if any(item.field not in allowed_order for item in request.order_by):
        raise ApplicationError(
            code="QUERY_ORDER_INVALID",
            message="A requested order field is unavailable.",
            status_code=422,
        )
    datasets_used = {pair[0].dataset_id for pair in dimensions.values()} | {
        pair[1].dataset_id for pair in metrics.values()
    }
    datasets_used |= {
        measure.dataset_id for ratio in ratio_metrics.values() for measure, _field in ratio[1:]
    }
    if datasets_used - {dataset.id}:
        raise ApplicationError(
            code="AMBIGUOUS_JOIN_PATH",
            message="The semantic query does not have one approved join path.",
            status_code=422,
        )
    row = (
        (
            await db.execute(
                select(Connection, ConnectionType)
                .join(ConnectionType, ConnectionType.id == Connection.connection_type_id)
                .where(
                    Connection.id == dataset.connection_id,
                    Connection.organization_id == org,
                    Connection.workspace_id == ws,
                    Connection.status == "active",
                    Connection.archived_at.is_(None),
                )
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None or "read_only_analytics" not in row[1].capabilities or row[0].secret_id is None:
        raise ApplicationError(
            code="QUERY_CONNECTION_UNAVAILABLE",
            message="The semantic query connection is unavailable.",
            status_code=422,
        )
    connection, kind = row
    secret_id = connection.secret_id
    assert secret_id is not None
    if kind.key != "postgresql":
        raise ApplicationError(
            code="QUERY_CONNECTOR_UNSUPPORTED",
            message="Read-only analytics is unsupported for this connection.",
            status_code=422,
        )
    compiled = PostgreSQLSemanticQueryCompiler().compile(
        request, dataset, dimensions, metrics, ratio_metrics
    )
    await consume_quota(db, context, "semantic_queries.per_day")
    credentials = await provider.read_secret(
        db,
        organization_id=org,
        workspace_id=ws,
        connection_id=connection.id,
        secret_id=secret_id,
    )
    host, port = str(connection.configuration["host"]), cast(int, connection.configuration["port"])
    try:
        await validate_host(host, port, settings)
    except UnsafeDestinationError as exc:
        raise ApplicationError(
            code="QUERY_DESTINATION_BLOCKED",
            message="The query destination is not allowed.",
            status_code=422,
        ) from exc
    started = time.perf_counter()
    driver: asyncpg.Connection[asyncpg.Record] | None = None
    query_id = uuid4()
    try:
        driver = await asyncio.wait_for(
            asyncpg.connect(
                host=host,
                port=port,
                database=str(connection.configuration["database"]),
                user=str(connection.configuration["username"]),
                password=credentials["password"],
                ssl=str(connection.configuration["ssl_mode"]),
                command_timeout=settings.SEMANTIC_QUERY_TIMEOUT_SECONDS,
                server_settings={"application_name": "vip-semantic-query"},
            ),
            settings.SEMANTIC_QUERY_TIMEOUT_SECONDS,
        )
        assert driver is not None
        async with driver.transaction(readonly=True):
            records = await asyncio.wait_for(
                driver.fetch(compiled.statement, *compiled.parameters),
                settings.SEMANTIC_QUERY_TIMEOUT_SECONDS,
            )
    except TimeoutError as exc:
        raise ApplicationError(
            code="QUERY_TIMEOUT", message="The semantic query timed out.", status_code=504
        ) from exc
    except (OSError, asyncpg.PostgresError) as exc:
        raise ApplicationError(
            code="QUERY_EXECUTION_FAILED",
            message="The semantic query could not be completed.",
            status_code=502,
        ) from exc
    finally:
        if driver is not None:
            await driver.close(timeout=2)
    rows = [
        {column.key: _normalize(record[column.key]) for column in compiled.columns}
        for record in records
    ]
    if (
        len(json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode())
        > settings.SEMANTIC_QUERY_MAX_RESULT_BYTES
    ):
        raise ApplicationError(
            code="QUERY_RESULT_TOO_LARGE",
            message="The semantic query result exceeds the allowed size.",
            status_code=422,
        )
    duration = round((time.perf_counter() - started) * 1000)
    await record_audit(
        db,
        "semantic_query.succeeded",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="semantic_model",
        resource_id=model.id,
        metadata={
            "query_id": str(query_id),
            "metric_count": len(request.metrics),
            "dimension_count": len(request.dimensions),
            "filter_count": len(request.filters),
            "limit": limit,
            "duration_ms": duration,
            "row_count": len(rows),
            "truncated": len(rows) == limit,
        },
    )
    await db.commit()
    return SemanticQueryResult(
        query_id=query_id,
        semantic_model={"id": str(model.id), "key": model.key},
        columns=list(compiled.columns),
        rows=rows,
        row_count=len(rows),
        truncated=len(rows) == limit,
        execution=QueryExecution(duration_ms=duration, executed_at=datetime.now(UTC)),
        correlation_id=context.correlation_id,
    )
