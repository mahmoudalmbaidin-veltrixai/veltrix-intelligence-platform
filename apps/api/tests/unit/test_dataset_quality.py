"""Deterministic dataset-quality rule execution coverage."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import asyncpg  # type: ignore[import-untyped]
import pytest

from vip_api.datasets.models import DatasetField, DatasetQualityRule
from vip_api.datasets.quality import _evaluate_rule


class Driver:
    def __init__(self, result: int) -> None:
        self.result = result
        self.statements: list[str] = []

    async def fetchval(self, statement: str, *_parameters: object) -> int:
        self.statements.append(statement)
        return self.result

    async def fetch(self, _statement: str) -> list[dict[str, object]]:
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rule_type", "configuration"),
    [
        ("not_null", {}),
        ("unique", {}),
        ("accepted_values", {"values": ["active", "inactive"]}),
        ("range", {"min": 0, "max": 100}),
        ("regex", {"pattern": "^[A-Z]+$"}),
        ("freshness", {"max_age_hours": 24}),
    ],
)
async def test_supported_quality_rules_execute_and_never_report_false_passes(
    rule_type: str, configuration: dict[str, object]
) -> None:
    driver = Driver(3)
    rule = SimpleNamespace(
        rule_type=rule_type,
        configuration=configuration,
        severity="error",
    )
    field = SimpleNamespace(source_name="governed_field")
    status, failures, _observed, _expected, _issues = await _evaluate_rule(
        cast(asyncpg.Connection, driver),
        '"public"."dataset"',
        cast(DatasetQualityRule, rule),
        cast(DatasetField, field),
        100,
    )
    assert status == "failing"
    assert failures == 3
    assert driver.statements


@pytest.mark.asyncio
async def test_custom_reference_uses_only_resolved_governed_identifiers() -> None:
    driver = Driver(0)
    rule = SimpleNamespace(
        rule_type="custom_reference",
        configuration={},
        severity="warning",
    )
    field = SimpleNamespace(source_name="customer_id")
    status, failures, _observed, expected, _issues = await _evaluate_rule(
        cast(asyncpg.Connection, driver),
        '"public"."orders"',
        cast(DatasetQualityRule, rule),
        cast(DatasetField, field),
        100,
        ('"public"."customers"', '"id"'),
    )
    assert status == "passing"
    assert failures == 0
    assert expected and "reference dataset" in expected
    assert '"public"."customers"' in driver.statements[0]


@pytest.mark.asyncio
async def test_invalid_rule_configuration_is_unknown_not_passing() -> None:
    driver = Driver(0)
    rule = SimpleNamespace(
        rule_type="accepted_values",
        configuration={"values": []},
        severity="warning",
    )
    field = SimpleNamespace(source_name="status")
    status, failures, *_rest = await _evaluate_rule(
        cast(asyncpg.Connection, driver),
        '"public"."orders"',
        cast(DatasetQualityRule, rule),
        cast(DatasetField, field),
        100,
    )
    assert status == "unknown"
    assert failures is None
    assert not driver.statements
