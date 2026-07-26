"""Safe bounded CSV ingestion into a tenant-selected PostgreSQL connection."""

from __future__ import annotations

import asyncio
import csv
import io
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.network import UnsafeDestinationError, validate_host
from vip_api.connections.secrets import SecretProvider
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.datasets.discovery import MetadataDiscoveryAdapterRegistry
from vip_api.datasets.models import Dataset
from vip_api.datasets.schemas import CsvIngestRequest, DiscoveryRequest, DiscoveryResult
from vip_api.datasets.services import _connection, discover
from vip_api.files.models import PlatformFile
from vip_api.files.storage import StorageProviderError, storage_provider
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext

HEADER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _quote(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _parse(payload: CsvIngestRequest) -> tuple[list[str], list[list[str | None]]]:
    if "\x00" in payload.csv_content:
        raise ApplicationError(
            code="CSV_INVALID", message="The CSV contains an invalid null byte.", status_code=422
        )
    reader = csv.reader(io.StringIO(payload.csv_content, newline=""))
    try:
        headers = [item.strip() for item in next(reader)]
    except StopIteration as exc:
        raise ApplicationError(
            code="CSV_EMPTY", message="The CSV must include a header row.", status_code=422
        ) from exc
    if not headers or len(headers) > 200 or len(set(headers)) != len(headers):
        raise ApplicationError(
            code="CSV_HEADERS_INVALID",
            message="CSV headers must be unique and contain at most 200 columns.",
            status_code=422,
        )
    if any(not HEADER.fullmatch(item) for item in headers):
        raise ApplicationError(
            code="CSV_HEADERS_INVALID",
            message="CSV headers must use letters, numbers, and underscores.",
            status_code=422,
        )
    rows: list[list[str | None]] = []
    for number, row in enumerate(reader, start=2):
        if number > 50_001:
            raise ApplicationError(
                code="CSV_ROW_LIMIT",
                message="Interactive CSV ingestion is limited to 50,000 rows.",
                status_code=422,
            )
        if len(row) != len(headers):
            raise ApplicationError(
                code="CSV_ROW_INVALID",
                message=f"CSV row {number} has an unexpected column count.",
                status_code=422,
            )
        rows.append([value if value != "" else None for value in row])
    if not rows:
        raise ApplicationError(
            code="CSV_EMPTY", message="The CSV must include at least one data row.", status_code=422
        )
    return headers, rows


def _column_type(
    values: list[str | None],
) -> tuple[str, Callable[[str | None], object]]:
    present = [value for value in values if value is not None]
    if present and all(value.lower() in {"true", "false"} for value in present):
        return "BOOLEAN", lambda value: None if value is None else value.lower() == "true"
    if present and all(re.fullmatch(r"-?\d+", value) for value in present):
        return "BIGINT", lambda value: None if value is None else int(value)
    try:
        if present:
            for value in present:
                Decimal(value)
            return "NUMERIC(24,6)", lambda value: None if value is None else Decimal(value)
    except InvalidOperation:
        pass
    try:
        if present:
            for value in present:
                date.fromisoformat(value)
            return "DATE", lambda value: None if value is None else date.fromisoformat(value)
    except ValueError:
        pass
    return "TEXT", lambda value: value


async def ingest_csv(
    db: AsyncSession,
    context: AuthorizationContext,
    payload: CsvIngestRequest,
    provider: SecretProvider,
    registry: MetadataDiscoveryAdapterRegistry,
    settings: Settings,
) -> DiscoveryResult:
    connection, kind = await _connection(db, context, payload.connection_id)
    workspace_id = context.workspace_id
    if workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    if kind.key != "postgresql" or connection.secret_id is None:
        raise ApplicationError(
            code="CSV_INGEST_UNSUPPORTED",
            message="Interactive CSV ingestion requires a PostgreSQL connection.",
            status_code=422,
        )
    headers, rows = _parse(payload)
    credentials = await provider.read_secret(
        db,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        connection_id=connection.id,
        secret_id=connection.secret_id,
    )
    host = str(connection.configuration["host"])
    port = int(str(connection.configuration["port"]))
    try:
        await validate_host(host, port, settings)
    except UnsafeDestinationError as exc:
        raise ApplicationError(
            code="CSV_INGEST_DESTINATION_BLOCKED",
            message="The connection destination is not allowed.",
            status_code=422,
        ) from exc
    types = [_column_type([row[index] for row in rows]) for index in range(len(headers))]
    converted = [[types[index][1](value) for index, value in enumerate(row)] for row in rows]
    driver: asyncpg.Connection[asyncpg.Record] | None = None
    try:
        driver = await asyncio.wait_for(
            asyncpg.connect(
                host=host,
                port=port,
                database=str(connection.configuration["database"]),
                user=str(connection.configuration["username"]),
                password=credentials["password"],
                ssl=str(connection.configuration["ssl_mode"]),
                command_timeout=settings.METADATA_DISCOVERY_TIMEOUT_SECONDS,
                server_settings={"application_name": "vip-csv-ingestion"},
            ),
            settings.METADATA_DISCOVERY_TIMEOUT_SECONDS,
        )
        assert driver is not None
        table = f"{_quote(payload.source_schema)}.{_quote(payload.source_name)}"
        columns = ", ".join(
            f"{_quote(header)} {types[index][0]}" for index, header in enumerate(headers)
        )
        parameters = ", ".join(f"${index + 1}" for index in range(len(headers)))
        async with driver.transaction():
            await driver.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote(payload.source_schema)}")
            await driver.execute(f"CREATE TABLE {table} ({columns})")
            await driver.executemany(
                f"INSERT INTO {table} VALUES ({parameters})",  # noqa: S608
                converted,
            )
    except asyncpg.DuplicateTableError as exc:
        raise ApplicationError(
            code="DATASET_TABLE_CONFLICT",
            message="A table with this name already exists.",
            status_code=409,
        ) from exc
    except (OSError, asyncpg.PostgresError) as exc:
        raise ApplicationError(
            code="CSV_INGEST_FAILED",
            message="The CSV could not be written to the selected connection.",
            status_code=502,
        ) from exc
    finally:
        if driver is not None:
            await driver.close(timeout=2)
    result = await discover(
        db,
        context,
        DiscoveryRequest(
            connection_id=payload.connection_id,
            schemas=[payload.source_schema],
            include_object_types=["table"],
            include_names=[payload.source_name],
            persist=True,
        ),
        provider,
        registry,
    )
    if result.datasets:
        dataset = await db.get(Dataset, result.datasets[0].id)
        if dataset is not None:
            dataset.display_name = payload.display_name or payload.source_name
            dataset.description = payload.description
            dataset.row_count_estimate = len(rows)
            dataset.version += 1
            await record_audit(
                db,
                "dataset.csv_ingested",
                actor_user_id=context.user_id,
                organization_id=context.organization_id,
                workspace_id=workspace_id,
                resource_type="dataset",
                resource_id=dataset.id,
                metadata={"rows": len(rows), "columns": len(headers)},
            )
            await db.commit()
            result.datasets[0] = result.datasets[0].model_copy(
                update={
                    "display_name": dataset.display_name,
                    "description": dataset.description,
                    "row_count_estimate": len(rows),
                    "version": dataset.version,
                }
            )
    return result


async def ingest_csv_file(
    db: AsyncSession,
    context: AuthorizationContext,
    file_id: UUID,
    connection_id: UUID,
    source_schema: str,
    source_name: str,
    display_name: str | None,
    description: str,
    provider: SecretProvider,
    registry: MetadataDiscoveryAdapterRegistry,
    settings: Settings,
) -> DiscoveryResult:
    workspace_id = context.workspace_id
    if workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    item = await db.scalar(
        select(PlatformFile).where(
            PlatformFile.id == file_id,
            PlatformFile.organization_id == context.organization_id,
            PlatformFile.workspace_id == workspace_id,
            PlatformFile.status == "ready",
            PlatformFile.is_deleted.is_(False),
        )
    )
    if item is None or item.storage_key is None:
        raise ApplicationError(
            code="FILE_NOT_FOUND", message="The uploaded file is unavailable.", status_code=404
        )
    if item.extension != ".csv" or item.mime_type not in {"text/csv", "application/csv"}:
        raise ApplicationError(
            code="CSV_FILE_REQUIRED",
            message="Pipeline dataset registration currently supports validated CSV files.",
            status_code=422,
        )
    chunks: list[bytes] = []
    size = 0
    try:
        store = storage_provider(item.storage_provider, settings.FILE_STORAGE_ROOT)
        async for chunk in store.stream(item.storage_key, settings.FILE_STREAM_CHUNK_BYTES):
            size += len(chunk)
            if size > 5_000_000:
                raise ApplicationError(
                    code="CSV_FILE_TOO_LARGE",
                    message="Interactive CSV registration is limited to 5 MB.",
                    status_code=413,
                )
            chunks.append(chunk)
    except StorageProviderError as exc:
        raise ApplicationError(
            code="FILE_STORAGE_UNAVAILABLE",
            message="The uploaded file is temporarily unavailable.",
            status_code=503,
        ) from exc
    try:
        csv_content = b"".join(chunks).decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ApplicationError(
            code="CSV_ENCODING_INVALID",
            message="The CSV must use UTF-8 encoding.",
            status_code=422,
        ) from exc
    result = await ingest_csv(
        db,
        context,
        CsvIngestRequest(
            connection_id=connection_id,
            source_schema=source_schema,
            source_name=source_name,
            display_name=display_name,
            description=description,
            csv_content=csv_content,
        ),
        provider,
        registry,
        settings,
    )
    if result.datasets:
        await record_audit(
            db,
            "dataset.file_registered",
            actor_user_id=context.user_id,
            organization_id=context.organization_id,
            workspace_id=workspace_id,
            resource_type="dataset",
            resource_id=result.datasets[0].id,
            metadata={"file_id": str(item.id), "file_sha256": item.sha256},
        )
        await db.commit()
    return result
