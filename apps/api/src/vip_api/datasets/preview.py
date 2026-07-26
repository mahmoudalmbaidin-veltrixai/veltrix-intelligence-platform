"""Bounded tenant-authorized dataset preview and profiling."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.network import UnsafeDestinationError, validate_host
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.datasets.schemas import (
    DatasetPreviewColumn,
    DatasetPreviewResponse,
    DatasetProfileField,
    DatasetProfileResponse,
)
from vip_api.datasets.services import _connection
from vip_api.governance.context import AuthorizationContext


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _safe(value: object) -> object:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)[:500]


async def _open(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
    provider: DatabaseEncryptedSecretProvider,
    settings: Settings,
) -> tuple[Dataset, list[DatasetField], asyncpg.Connection[asyncpg.Record]]:
    workspace_id = context.workspace_id
    if workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    dataset = await db.scalar(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.organization_id == context.organization_id,
            Dataset.workspace_id == workspace_id,
            Dataset.archived_at.is_(None),
        )
    )
    if dataset is None:
        raise ApplicationError(
            code="DATASET_NOT_FOUND", message="The dataset is unavailable.", status_code=404
        )
    fields = list(
        (
            await db.scalars(
                select(DatasetField)
                .where(
                    DatasetField.dataset_id == dataset.id,
                    DatasetField.organization_id == context.organization_id,
                    DatasetField.workspace_id == workspace_id,
                    DatasetField.is_hidden.is_(False),
                )
                .order_by(DatasetField.ordinal_position)
                .limit(100)
            )
        ).all()
    )
    connection, kind = await _connection(db, context, dataset.connection_id)
    if kind.key != "postgresql" or connection.secret_id is None or connection.status != "active":
        raise ApplicationError(
            code="DATASET_SOURCE_UNAVAILABLE",
            message="The dataset source connection is unavailable.",
            status_code=409,
        )
    credentials = await provider.read_secret(
        db,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        connection_id=connection.id,
        secret_id=connection.secret_id,
    )
    host = str(connection.configuration["host"])
    port = int(cast(int, connection.configuration["port"]))
    try:
        await validate_host(host, port, settings)
        driver = await asyncio.wait_for(
            asyncpg.connect(
                host=host,
                port=port,
                database=str(connection.configuration["database"]),
                user=str(connection.configuration["username"]),
                password=credentials["password"],
                ssl=str(connection.configuration["ssl_mode"]),
                command_timeout=min(settings.METADATA_DISCOVERY_TIMEOUT_SECONDS, 30),
                server_settings={"application_name": "vip-dataset-preview"},
            ),
            min(settings.METADATA_DISCOVERY_TIMEOUT_SECONDS, 30),
        )
    except UnsafeDestinationError as exc:
        raise ApplicationError(
            code="DATASET_SOURCE_BLOCKED",
            message="The dataset source destination is not allowed.",
            status_code=422,
        ) from exc
    except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
        raise ApplicationError(
            code="DATASET_PREVIEW_UNAVAILABLE",
            message="The dataset preview is temporarily unavailable.",
            status_code=503,
        ) from exc
    return dataset, fields, driver


async def preview_dataset(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
    page: int,
    page_size: int,
    provider: DatabaseEncryptedSecretProvider,
    settings: Settings,
) -> DatasetPreviewResponse:
    dataset, fields, driver = await _open(db, context, dataset_id, provider, settings)
    try:
        selected = fields[:50]
        if not selected:
            rows: list[asyncpg.Record] = []
        else:
            columns = ", ".join(_quote(field.source_name) for field in selected)
            table = f"{_quote(dataset.source_schema)}.{_quote(dataset.source_name)}"
            offset = (page - 1) * page_size
            rows = await driver.fetch(
                f"SELECT {columns} FROM {table} LIMIT $1 OFFSET $2",  # noqa: S608
                page_size,
                offset,
            )
        sensitive = {field.source_name for field in selected if field.is_sensitive}
        return DatasetPreviewResponse(
            dataset_id=dataset.id,
            columns=[
                DatasetPreviewColumn(
                    name=field.source_name,
                    display_name=field.display_name,
                    physical_type=field.physical_data_type,
                    normalized_type=field.normalized_data_type,
                    nullable=field.is_nullable,
                    primary_key=field.is_primary_key,
                    unique=field.is_unique,
                    sensitive=field.is_sensitive,
                    classification=field.classification,
                )
                for field in selected
            ],
            rows=[
                {
                    key: ("••••" if key in sensitive and value is not None else _safe(value))
                    for key, value in dict(row).items()
                }
                for row in rows
            ],
            page=page,
            page_size=page_size,
            returned_rows=len(rows),
            masked_fields=sorted(sensitive),
            refreshed_at=datetime.now(UTC),
        )
    except (asyncpg.PostgresError, TimeoutError) as exc:
        raise ApplicationError(
            code="DATASET_PREVIEW_FAILED",
            message="The dataset preview could not be loaded.",
            status_code=502,
        ) from exc
    finally:
        await driver.close(timeout=2)


async def profile_dataset(
    db: AsyncSession,
    context: AuthorizationContext,
    dataset_id: UUID,
    provider: DatabaseEncryptedSecretProvider,
    settings: Settings,
) -> DatasetProfileResponse:
    dataset, fields, driver = await _open(db, context, dataset_id, provider, settings)
    sample_size = 10_000
    table = f"{_quote(dataset.source_schema)}.{_quote(dataset.source_name)}"
    results: list[DatasetProfileField] = []
    observed_sample_size = 0
    try:
        for field in fields[:50]:
            column = _quote(field.source_name)
            orderable = (
                f"{column}::text"
                if field.normalized_data_type in {"json", "array", "object", "boolean", "binary"}
                else column
            )
            row = await driver.fetchrow(
                f"SELECT count(*) sample_count, "  # noqa: S608
                f"count(*) FILTER (WHERE {column} IS NULL) nulls, "
                f"count(DISTINCT {column}::text) distincts, "
                f"min({orderable})::text minimum, max({orderable})::text maximum "
                f"FROM (SELECT {column} FROM {table} LIMIT $1) sampled",
                sample_size,
            )
            assert row is not None
            observed_sample_size = max(observed_sample_size, int(row["sample_count"]))
            results.append(
                DatasetProfileField(
                    name=field.source_name,
                    null_count=int(row["nulls"]),
                    distinct_count=int(row["distincts"]),
                    minimum=None if field.is_sensitive else row["minimum"],
                    maximum=None if field.is_sensitive else row["maximum"],
                )
            )
        return DatasetProfileResponse(
            dataset_id=dataset.id,
            fields=results,
            sample_size=observed_sample_size,
            refreshed_at=datetime.now(UTC),
        )
    except (asyncpg.PostgresError, TimeoutError) as exc:
        raise ApplicationError(
            code="DATASET_PROFILE_FAILED",
            message="The dataset profile could not be loaded.",
            status_code=502,
        ) from exc
    finally:
        await driver.close(timeout=2)
