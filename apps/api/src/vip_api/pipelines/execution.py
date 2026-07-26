"""Bounded execution of immutable, validated pipeline snapshots."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.network import validate_host
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.datasets.models import Dataset, DatasetField, DatasetLineageEdge
from vip_api.governance.context import AuthorizationContext
from vip_api.pipelines.formula import evaluate, parse_formula
from vip_api.pipelines.models import (
    PipelineArtifact,
    PipelineNodeRun,
    PipelineRun,
    PipelineRunLog,
    PipelineVersion,
)
from vip_api.pipelines.schemas import EdgeInput, NodeInput
from vip_api.pipelines.storage import PipelineArtifactStorage
from vip_api.pipelines.validation import validate_graph

Rows = list[dict[str, object]]


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def normalize(value: object) -> object:
    if isinstance(value, (datetime, UUID)):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


async def _connection(
    db: AsyncSession, run: PipelineRun, dataset_id: UUID
) -> tuple[Dataset, list[DatasetField], Connection, dict[str, str]]:
    dataset = await db.scalar(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.organization_id == run.organization_id,
            Dataset.workspace_id == run.workspace_id,
            Dataset.archived_at.is_(None),
        )
    )
    if dataset is None:
        raise ApplicationError(
            code="PIPELINE_DATASET_UNAVAILABLE",
            message="A pipeline dataset is unavailable.",
            status_code=422,
        )
    fields = list(
        (
            await db.scalars(
                select(DatasetField)
                .where(
                    DatasetField.dataset_id == dataset.id,
                    DatasetField.organization_id == run.organization_id,
                    DatasetField.workspace_id == run.workspace_id,
                )
                .order_by(DatasetField.ordinal_position)
            )
        ).all()
    )
    row = (
        (
            await db.execute(
                select(Connection, ConnectionType)
                .join(ConnectionType, ConnectionType.id == Connection.connection_type_id)
                .where(
                    Connection.id == dataset.connection_id,
                    Connection.organization_id == run.organization_id,
                    Connection.workspace_id == run.workspace_id,
                    Connection.status == "active",
                    Connection.archived_at.is_(None),
                )
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None or row[1].key != "postgresql" or row[0].secret_id is None:
        raise ApplicationError(
            code="PIPELINE_CONNECTION_UNAVAILABLE",
            message="A pipeline connection is unavailable.",
            status_code=422,
        )
    connection = row[0]
    return dataset, fields, connection, {}


async def _driver(
    db: AsyncSession,
    run: PipelineRun,
    dataset_id: UUID,
    settings: Settings,
    provider: DatabaseEncryptedSecretProvider,
) -> tuple[Dataset, list[DatasetField], asyncpg.Connection[asyncpg.Record]]:
    dataset, fields, connection, _ = await _connection(db, run, dataset_id)
    assert connection.secret_id is not None
    credentials = await provider.read_secret(
        db,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        connection_id=connection.id,
        secret_id=connection.secret_id,
    )
    host, port = (
        str(connection.configuration["host"]),
        int(cast(int, connection.configuration["port"])),
    )
    await validate_host(host, port, settings)
    driver = await asyncio.wait_for(
        asyncpg.connect(
            host=host,
            port=port,
            database=str(connection.configuration["database"]),
            user=str(connection.configuration["username"]),
            password=credentials["password"],
            ssl=str(connection.configuration["ssl_mode"]),
            command_timeout=settings.PIPELINE_RUN_TIMEOUT_SECONDS,
            server_settings={"application_name": "vip-pipeline-worker"},
        ),
        15,
    )
    return dataset, fields, driver


async def read_dataset(
    db: AsyncSession,
    run: PipelineRun,
    config: dict[str, object],
    settings: Settings,
    provider: DatabaseEncryptedSecretProvider,
) -> Rows:
    dataset_id = UUID(str(config["dataset_id"]))
    dataset, fields, driver = await _driver(db, run, dataset_id, settings, provider)
    available = {field.source_name for field in fields}
    requested = config.get("columns")
    columns = list(requested) if isinstance(requested, list) and requested else list(available)
    if not columns or not set(columns) <= available:
        await driver.close()
        raise ApplicationError(
            code="PIPELINE_FIELD_UNAVAILABLE",
            message="A requested dataset field is unavailable.",
            status_code=422,
        )
    limit = min(
        int(str(config.get("row_limit", settings.PIPELINE_RUN_MAX_ROWS))),
        settings.PIPELINE_RUN_MAX_ROWS,
    )
    # Identifiers come exclusively from tenant-scoped B5 catalog records and are quoted here.
    statement = (
        f"SELECT {', '.join(quote_identifier(str(c)) for c in columns)} "  # noqa: S608
        f"FROM {quote_identifier(dataset.source_schema)}."
        f"{quote_identifier(dataset.source_name)} LIMIT $1"
    )
    try:
        async with driver.transaction(readonly=True):
            records = await driver.fetch(statement, limit)
    finally:
        await driver.close(timeout=2)
    return [
        {str(column): normalize(record[str(column)]) for column in columns} for record in records
    ]


async def write_dataset(
    db: AsyncSession,
    run: PipelineRun,
    config: dict[str, object],
    rows: Rows,
    settings: Settings,
    provider: DatabaseEncryptedSecretProvider,
    source_ids: set[UUID],
) -> int:
    dataset_id = UUID(str(config["dataset_id"]))
    dataset, fields, driver = await _driver(db, run, dataset_id, settings, provider)
    if dataset.is_read_only:
        await driver.close()
        raise ApplicationError(
            code="PIPELINE_DATASET_READ_ONLY",
            message="The selected output dataset is read-only.",
            status_code=422,
        )
    columns = [
        field.source_name for field in fields if field.source_name in (rows[0] if rows else {})
    ]
    if rows and not columns:
        await driver.close()
        raise ApplicationError(
            code="PIPELINE_OUTPUT_SCHEMA_MISMATCH",
            message="The output fields do not match the target dataset.",
            status_code=422,
        )
    table = f"{quote_identifier(dataset.source_schema)}.{quote_identifier(dataset.source_name)}"
    try:
        async with driver.transaction():
            if config["write_mode"] == "replace":
                await driver.execute(f"DELETE FROM {table}")  # noqa: S608
            if rows:
                params = ", ".join(f"${i + 1}" for i in range(len(columns)))
                statement = (
                    f"INSERT INTO {table} "  # noqa: S608
                    f"({', '.join(quote_identifier(c) for c in columns)}) VALUES ({params})"
                )
                await driver.executemany(
                    statement, [[row.get(column) for column in columns] for row in rows]
                )
    finally:
        await driver.close(timeout=2)
    dataset.row_count_estimate = len(rows)
    dataset.last_metadata_refresh_at = datetime.now(UTC)
    dataset.version += 1
    for source_id in source_ids - {dataset.id}:
        exists = await db.scalar(
            select(DatasetLineageEdge.id).where(
                DatasetLineageEdge.organization_id == run.organization_id,
                DatasetLineageEdge.workspace_id == run.workspace_id,
                DatasetLineageEdge.source_dataset_id == source_id,
                DatasetLineageEdge.target_dataset_id == dataset.id,
                DatasetLineageEdge.lineage_type == "pipeline",
            )
        )
        if exists is None:
            db.add(
                DatasetLineageEdge(
                    organization_id=run.organization_id,
                    workspace_id=run.workspace_id,
                    source_dataset_id=source_id,
                    target_dataset_id=dataset.id,
                    lineage_type="pipeline",
                    origin="system",
                    description="Generated by a published VIP pipeline version.",
                    created_by_user_id=run.requested_by_user_id,
                    edge_metadata={
                        "pipeline_id": str(run.pipeline_id),
                        "pipeline_version_id": str(run.pipeline_version_id),
                        "run_id": str(run.id),
                    },
                )
            )
    return len(rows)


def transform(node: NodeInput, inputs: list[Rows]) -> Rows:
    rows = [dict(row) for row in (inputs[0] if inputs else [])]
    config = node.config
    if node.type == "select-columns":
        return [
            {str(c): row.get(str(c)) for c in cast(list[object], config["columns"])} for row in rows
        ]
    if node.type == "rename-columns":
        renames = cast(dict[str, str], config["renames"])
        return [{renames.get(k, k): v for k, v in row.items()} for row in rows]
    if node.type == "filter":
        expression = parse_formula(str(config["formula"]))
        return [row for row in rows if bool(evaluate(expression, row))]
    if node.type == "formula":
        expression = parse_formula(str(config["formula"]))
        field = str(config["field"])
        for row in rows:
            row[field] = normalize(evaluate(expression, row))
        return rows
    if node.type == "sort":
        raw_sort = config["fields"]
        sort_specs = (
            [{"field": key, "direction": value} for key, value in raw_sort.items()]
            if isinstance(raw_sort, dict)
            else cast(list[dict[str, object]], raw_sort)
        )
        for sort_spec in reversed(sort_specs):
            rows.sort(
                key=lambda row: (
                    row.get(str(sort_spec["field"])) is None,
                    row.get(str(sort_spec["field"])),
                ),
                reverse=sort_spec.get("direction") == "desc",
            )
        return rows
    if node.type == "deduplicate":
        dedupe_fields = [str(v) for v in cast(list[object], config["fields"])]
        seen: set[tuple[object, ...]] = set()
        deduplicated: Rows = []
        for row in rows:
            key = tuple(row.get(field) for field in dedupe_fields)
            if key not in seen:
                seen.add(key)
                deduplicated.append(row)
        return deduplicated
    if node.type == "null-handling":
        field, strategy = str(config["field"]), str(config["strategy"])
        if strategy == "drop":
            return [row for row in rows if row.get(field) is not None]
        for row in rows:
            if row.get(field) is None:
                row[field] = config.get("value")
        return rows
    if node.type == "type-convert":
        field, target = str(config["field"]), str(config["target_type"])
        converters = {"string": str, "integer": int, "number": float, "boolean": bool}
        if target not in converters:
            raise ApplicationError(
                code="PIPELINE_TYPE_UNSUPPORTED",
                message="The requested conversion type is unsupported.",
                status_code=422,
            )
        for row in rows:
            if row.get(field) is not None:
                row[field] = converters[target](row[field])
        return rows
    if node.type == "union":
        return (
            [dict(row) for group in inputs for row in group]
            if not config.get("distinct")
            else list(
                {
                    json.dumps(row, sort_keys=True, default=str): row
                    for group in inputs
                    for row in group
                }.values()
            )
        )
    if node.type == "join":
        left_key, right_key = str(config["left_field"]), str(config["right_field"])
        index: dict[object, list[dict[str, object]]] = defaultdict(list)
        for row in inputs[1]:
            index[row.get(right_key)].append(row)
        joined: Rows = []
        for left in inputs[0]:
            matches = index.get(left.get(left_key), [])
            if matches:
                joined.extend([{**left, **right} for right in matches])
            elif config.get("join_type") in {"left", "full"}:
                joined.append(left)
        return joined
    if node.type == "aggregate":
        groups = [str(v) for v in cast(list[object], config.get("group_by", []))]
        specs = cast(list[dict[str, object]], config["aggregations"])
        buckets: dict[tuple[object, ...], Rows] = defaultdict(list)
        for row in rows:
            buckets[tuple(row.get(group) for group in groups)].append(row)
        output: Rows = []
        for key, members in buckets.items():
            item = dict(zip(groups, key, strict=True))
            for spec in specs:
                values = [
                    row.get(str(spec["field"]))
                    for row in members
                    if row.get(str(spec["field"])) is not None
                ]
                op = str(spec["operation"])
                alias = str(spec["alias"])
                if op == "count":
                    item[alias] = len(values)
                elif op == "sum":
                    item[alias] = sum(cast(list[int | float], values))
                elif op == "min":
                    comparable = cast(list[float | int | str], values)
                    item[alias] = min(comparable) if comparable else None
                elif op == "max":
                    comparable = cast(list[float | int | str], values)
                    item[alias] = max(comparable) if comparable else None
                elif op == "average":
                    item[alias] = (
                        sum(cast(list[int | float], values)) / len(values) if values else None
                    )
                else:
                    raise ApplicationError(
                        code="PIPELINE_AGGREGATION_UNSUPPORTED",
                        message="An aggregation is unsupported.",
                        status_code=422,
                    )
            output.append(item)
        return output
    return rows


async def execute_snapshot(
    db: AsyncSession,
    context: AuthorizationContext,
    run: PipelineRun,
    version: PipelineVersion,
    settings: Settings,
    provider: DatabaseEncryptedSecretProvider,
    storage: PipelineArtifactStorage,
) -> dict[str, object]:
    nodes = [
        NodeInput.model_validate(item) for item in cast(list[object], version.snapshot["nodes"])
    ]
    edges = [
        EdgeInput.model_validate(item) for item in cast(list[object], version.snapshot["edges"])
    ]
    validation = await validate_graph(db, context, nodes, edges)
    if not validation.valid:
        raise ApplicationError(
            code="PIPELINE_VERSION_INVALID",
            message="The published pipeline version is no longer executable.",
            status_code=422,
        )
    node_map = {node.key: node for node in nodes}
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        incoming[edge.target].append(edge.source)
    results: dict[str, Rows] = {}
    source_ids = {
        UUID(str(node.config["dataset_id"])) for node in nodes if node.type == "source-dataset"
    }
    artifacts: list[str] = []
    for index, key in enumerate(validation.topological_order):
        await db.refresh(run, attribute_names=["cancellation_requested"])
        if run.cancellation_requested:
            raise ApplicationError(
                code="PIPELINE_RUN_CANCELLED",
                message="The pipeline run was cancelled.",
                status_code=409,
            )
        node = node_map[key]
        inputs = [results[source] for source in incoming[key]]
        node_run = await db.scalar(
            select(PipelineNodeRun).where(
                PipelineNodeRun.run_id == run.id,
                PipelineNodeRun.attempt_number == run.current_attempt,
                PipelineNodeRun.node_key == key,
            )
        )
        if node_run is not None:
            node_run.status = "running"
            node_run.started_at = datetime.now(UTC)
            node_run.rows_in = sum(len(group) for group in inputs)
            await db.flush()
        if node.type == "source-dataset":
            rows = await read_dataset(db, run, node.config, settings, provider)
        elif node.type == "output-dataset":
            rows = inputs[0]
            await write_dataset(db, run, node.config, rows, settings, provider, source_ids)
        elif node.type == "file-export":
            rows = inputs[0]
            file_format = str(node.config["format"])
            filename = f"{uuid4()}.{file_format}"
            storage_key = f"{run.organization_id}/{run.workspace_id}/{run.id}/{filename}"
            if file_format == "json":
                content = json.dumps(rows, default=str, separators=(",", ":")).encode()
            else:
                stream = io.StringIO()
                columns = list(rows[0]) if rows else []
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
                content = stream.getvalue().encode()
            if len(content) > settings.PIPELINE_RUN_MAX_RESULT_BYTES:
                raise ApplicationError(
                    code="PIPELINE_ARTIFACT_TOO_LARGE",
                    message="The pipeline artifact exceeds the configured limit.",
                    status_code=422,
                )
            size, digest = storage.write(storage_key, content)
            artifact = PipelineArtifact(
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                run_id=run.id,
                node_key=node.key,
                storage_key=storage_key,
                content_type="application/json" if file_format == "json" else "text/csv",
                size_bytes=size,
                sha256=digest,
                expires_at=datetime.now(UTC)
                + timedelta(hours=settings.PIPELINE_ARTIFACT_RETENTION_HOURS),
            )
            db.add(artifact)
            await db.flush()
            artifacts.append(str(artifact.id))
        else:
            rows = transform(node, inputs)
        results[key] = rows
        if node_run is not None:
            node_run.status = "succeeded"
            node_run.rows_out = len(rows)
            node_run.completed_at = datetime.now(UTC)
        run.progress = round((index + 1) / len(nodes) * 100)
        run.rows_processed += len(rows)
        sequence = (
            await db.scalar(
                select(func.max(PipelineRunLog.sequence)).where(PipelineRunLog.run_id == run.id)
            )
            or 0
        ) + 1
        db.add(
            PipelineRunLog(
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                run_id=run.id,
                sequence=sequence,
                attempt_number=run.current_attempt,
                node_key=node.key,
                level="info",
                message=f"Node '{node.key}' completed.",
            )
        )
        # Progress and safe node logs must be observable while the run is active.
        await db.commit()
    return {
        "output_nodes": [
            key
            for key in validation.topological_order
            if node_map[key].type in {"output-dataset", "file-export"}
        ],
        "artifact_ids": artifacts,
        "rows_processed": run.rows_processed,
    }
