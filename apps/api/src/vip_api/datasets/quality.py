"""Tenant-scoped, read-only dataset quality evaluation."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.network import UnsafeDestinationError, validate_host
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings
from vip_api.datasets.models import (
    Dataset,
    DatasetField,
    DatasetQualityEvaluation,
    DatasetQualityResult,
    DatasetQualityRule,
)
from vip_api.jobs.retry import PermanentJobError, RetryableJobError

_MAX_ISSUES = 20


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)[:500]


def _status(failures: int, severity: str) -> str:
    if failures == 0:
        return "passing"
    return "failing" if severity in {"error", "critical"} else "warning"


async def _driver(
    db: AsyncSession,
    evaluation: DatasetQualityEvaluation,
    settings: Settings,
    provider: DatabaseEncryptedSecretProvider,
) -> tuple[Dataset, asyncpg.Connection[asyncpg.Record]]:
    dataset = await db.scalar(
        select(Dataset).where(
            Dataset.id == evaluation.dataset_id,
            Dataset.organization_id == evaluation.organization_id,
            Dataset.workspace_id == evaluation.workspace_id,
            Dataset.archived_at.is_(None),
        )
    )
    if dataset is None:
        raise PermanentJobError("QUALITY_DATASET_NOT_FOUND", "The dataset is unavailable.")
    row = (
        (
            await db.execute(
                select(Connection, ConnectionType)
                .join(ConnectionType, ConnectionType.id == Connection.connection_type_id)
                .where(
                    Connection.id == dataset.connection_id,
                    Connection.organization_id == evaluation.organization_id,
                    Connection.workspace_id == evaluation.workspace_id,
                    Connection.status == "active",
                    Connection.archived_at.is_(None),
                )
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None or row[1].key != "postgresql" or row[0].secret_id is None:
        raise PermanentJobError(
            "QUALITY_CONNECTION_UNAVAILABLE",
            "Quality evaluation requires an active PostgreSQL connection.",
        )
    connection = row[0]
    assert connection.secret_id is not None
    credentials = await provider.read_secret(
        db,
        organization_id=evaluation.organization_id,
        workspace_id=evaluation.workspace_id,
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
                command_timeout=settings.PIPELINE_RUN_TIMEOUT_SECONDS,
                server_settings={"application_name": "vip-quality-worker"},
            ),
            15,
        )
    except UnsafeDestinationError as exc:
        raise PermanentJobError(
            "QUALITY_DESTINATION_BLOCKED", "The connection destination is not allowed."
        ) from exc
    except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
        raise RetryableJobError(
            "QUALITY_SOURCE_UNAVAILABLE", "The dataset source is temporarily unavailable."
        ) from exc
    return dataset, driver


async def _evaluate_rule(
    driver: asyncpg.Connection[asyncpg.Record],
    table: str,
    rule: DatasetQualityRule,
    field: DatasetField | None,
    sample_size: int,
    reference: tuple[str, str] | None = None,
) -> tuple[str, int | None, str | None, str | None, list[dict[str, object]]]:
    column = _quote(field.source_name) if field else None
    config = rule.configuration
    statement: str
    parameters: list[object] = []
    expected: str | None = None
    if rule.rule_type == "not_null" and column:
        statement = f"SELECT count(*) FROM {table} WHERE {column} IS NULL"  # noqa: S608
        expected = "0 null values"
    elif rule.rule_type == "unique" and column:
        statement = (
            f"SELECT coalesce(sum(n - 1), 0) FROM "  # noqa: S608
            f"(SELECT count(*) n FROM {table} GROUP BY {column} HAVING count(*) > 1) q"
        )
        expected = "0 duplicate values"
    elif rule.rule_type == "accepted_values" and column:
        values = config.get("values")
        if not isinstance(values, list) or not values:
            return "unknown", None, None, None, []
        parameters.append([str(value) for value in values])
        statement = (
            f"SELECT count(*) FROM {table} "  # noqa: S608
            f"WHERE {column} IS NOT NULL AND {column}::text <> ALL($1::text[])"
        )
        expected = f"one of {', '.join(str(value) for value in values[:10])}"
    elif rule.rule_type == "range" and column:
        clauses: list[str] = []
        if config.get("min") is not None:
            parameters.append(config["min"])
            clauses.append(f"{column} < ${len(parameters)}")
        if config.get("max") is not None:
            parameters.append(config["max"])
            clauses.append(f"{column} > ${len(parameters)}")
        if not clauses:
            return "unknown", None, None, None, []
        statement = f"SELECT count(*) FROM {table} WHERE {' OR '.join(clauses)}"  # noqa: S608
        expected = f"between {config.get('min', 'unbounded')} and {config.get('max', 'unbounded')}"
    elif rule.rule_type == "regex" and column:
        pattern = config.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return "unknown", None, None, None, []
        statement = (
            f"SELECT count(*) FROM {table} WHERE {column} IS NOT NULL "  # noqa: S608
            f"AND NOT ({column}::text ~ $1)"
        )
        parameters.append(pattern)
        expected = f"matches {pattern[:100]}"
    elif rule.rule_type == "freshness" and column:
        hours = config.get("max_age_hours")
        if not isinstance(hours, int | float) or hours <= 0:
            return "unknown", None, None, None, []
        statement = (
            f"SELECT CASE WHEN max({column}) >= now() "  # noqa: S608
            f"- ($1::double precision * interval '1 hour') "
            f"THEN 0 ELSE 1 END FROM {table}"
        )
        parameters.append(float(hours))
        expected = f"newer than {hours} hours"
    elif rule.rule_type == "row_count":
        minimum, maximum = config.get("min"), config.get("max")
        count = sample_size
        failures = int(
            (isinstance(minimum, int | float) and count < minimum)
            or (isinstance(maximum, int | float) and count > maximum)
        )
        expected = (
            f"between {minimum if minimum is not None else 0} "
            f"and {maximum if maximum is not None else 'unbounded'} rows"
        )
        return _status(failures, rule.severity), failures, str(count), expected, []
    elif rule.rule_type == "custom_reference" and column and reference:
        reference_table, reference_column = reference
        statement = (
            f"SELECT count(*) FROM {table} source "  # noqa: S608
            f"WHERE source.{column} IS NOT NULL AND NOT EXISTS "
            f"(SELECT 1 FROM {reference_table} reference "
            f"WHERE reference.{reference_column} = source.{column})"
        )
        expected = "value exists in the governed reference dataset"
    else:
        return "unknown", None, None, None, []
    failures = int(await driver.fetchval(statement, *parameters) or 0)
    issues: list[dict[str, object]] = []
    if failures and column and rule.rule_type not in {"unique", "custom_reference"}:
        # Samples are bounded and contain only the governed field value, never full records.
        predicate = statement.split(" WHERE ", 1)[1] if " WHERE " in statement else ""
        if predicate and "$" not in predicate:
            rows = await driver.fetch(
                f"SELECT {column} AS value FROM {table} WHERE {predicate} LIMIT {_MAX_ISSUES}"  # noqa: S608
            )
            issues = [{"value": _safe_value(row["value"])} for row in rows]
    return _status(failures, rule.severity), failures, str(failures), expected, issues


async def evaluate(
    db: AsyncSession,
    evaluation_id: UUID,
    settings: Settings,
    provider: DatabaseEncryptedSecretProvider,
) -> dict[str, object]:
    evaluation = await db.scalar(
        select(DatasetQualityEvaluation).where(DatasetQualityEvaluation.id == evaluation_id)
    )
    if evaluation is None:
        raise PermanentJobError(
            "QUALITY_EVALUATION_NOT_FOUND", "The quality evaluation was not found."
        )
    evaluation.status = "running"
    evaluation.started_at = datetime.now(UTC)
    await db.commit()
    dataset, driver = await _driver(db, evaluation, settings, provider)
    rules = list(
        (
            await db.scalars(
                select(DatasetQualityRule).where(
                    DatasetQualityRule.organization_id == evaluation.organization_id,
                    DatasetQualityRule.workspace_id == evaluation.workspace_id,
                    DatasetQualityRule.dataset_id == evaluation.dataset_id,
                    DatasetQualityRule.is_enabled.is_(True),
                )
            )
        ).all()
    )
    field_ids = {rule.field_id for rule in rules if rule.field_id}
    fields = {
        item.id: item
        for item in (
            await db.scalars(
                select(DatasetField).where(
                    DatasetField.organization_id == evaluation.organization_id,
                    DatasetField.workspace_id == evaluation.workspace_id,
                    DatasetField.dataset_id == evaluation.dataset_id,
                    DatasetField.id.in_(field_ids),
                )
            )
        ).all()
    }
    references: dict[UUID, tuple[str, str]] = {}
    for rule in rules:
        if rule.rule_type != "custom_reference":
            continue
        try:
            reference_dataset_id = UUID(str(rule.configuration["reference_dataset_id"]))
            reference_field_id = UUID(str(rule.configuration["reference_field_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        reference_row = (
            (
                await db.execute(
                    select(Dataset, DatasetField)
                    .join(DatasetField, DatasetField.dataset_id == Dataset.id)
                    .where(
                        Dataset.id == reference_dataset_id,
                        Dataset.organization_id == evaluation.organization_id,
                        Dataset.workspace_id == evaluation.workspace_id,
                        Dataset.connection_id == dataset.connection_id,
                        Dataset.status == "active",
                        Dataset.archived_at.is_(None),
                        DatasetField.id == reference_field_id,
                        DatasetField.organization_id == evaluation.organization_id,
                        DatasetField.workspace_id == evaluation.workspace_id,
                    )
                )
            )
            .tuples()
            .one_or_none()
        )
        if reference_row:
            reference_dataset, reference_field = reference_row
            references[rule.id] = (
                f"{_quote(reference_dataset.source_schema)}."
                f"{_quote(reference_dataset.source_name)}",
                _quote(reference_field.source_name),
            )
    table = f"{_quote(dataset.source_schema)}.{_quote(dataset.source_name)}"
    counts = {"passing": 0, "warning": 0, "failing": 0, "unknown": 0}
    try:
        async with driver.transaction(readonly=True):
            sample_size = int(await driver.fetchval(f"SELECT count(*) FROM {table}") or 0)  # noqa: S608
            for rule in rules:
                started = time.monotonic()
                field = fields.get(rule.field_id) if rule.field_id is not None else None
                status, failures, observed, expected, issues = await _evaluate_rule(
                    driver, table, rule, field, sample_size, references.get(rule.id)
                )
                counts[status] += 1
                rule.status = status
                db.add(
                    DatasetQualityResult(
                        organization_id=evaluation.organization_id,
                        workspace_id=evaluation.workspace_id,
                        quality_rule_id=rule.id,
                        evaluation_id=evaluation.id,
                        status=status,
                        observed_value=observed,
                        expected_value=expected,
                        failure_count=failures,
                        sample_size=sample_size,
                        safe_message=(
                            "Rule configuration could not be evaluated."
                            if status == "unknown"
                            else f"{failures or 0} issue(s) detected."
                        ),
                        execution_reference=str(evaluation.id),
                        issue_details=issues,
                        duration_ms=round((time.monotonic() - started) * 1000),
                    )
                )
    except asyncpg.PostgresError as exc:
        evaluation.status = "failed"
        dataset.quality_status = "unknown"
        await db.commit()
        raise RetryableJobError(
            "QUALITY_QUERY_FAILED", "Quality evaluation could not query the dataset."
        ) from exc
    finally:
        await driver.close(timeout=2)
    total = len(rules)
    score = round(100 * counts["passing"] / total) if total else None
    overall = (
        "failing"
        if counts["failing"]
        else "warning"
        if counts["warning"]
        else "unknown"
        if counts["unknown"] or not rules
        else "passing"
    )
    evaluation.status = overall
    evaluation.score = score
    evaluation.total_rules = total
    evaluation.passing = counts["passing"]
    evaluation.warning = counts["warning"]
    evaluation.failing = counts["failing"]
    evaluation.unknown = counts["unknown"]
    evaluation.completed_at = datetime.now(UTC)
    dataset.quality_status = overall
    await db.commit()
    return {"evaluation_id": str(evaluation.id), "status": overall, "score": score}
