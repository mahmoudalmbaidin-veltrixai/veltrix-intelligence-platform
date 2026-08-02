"""B7 parser, execution registry, and artifact-boundary security tests."""

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.pipelines.execution import normalize, transform, validate_rows
from vip_api.pipelines.formula import evaluate, parse_formula, referenced_fields
from vip_api.pipelines.registry import NODE_REGISTRY
from vip_api.pipelines.schemas import NodeInput
from vip_api.pipelines.storage import (
    ArtifactStorageError,
    DownloadClaims,
    DownloadTokens,
    PipelineArtifactStorage,
)
from vip_api.pipelines.validation import _typed_config_issues
from vip_api.pipelines.worker import heartbeat_lease


def test_safe_formula_parser_builds_ast_and_evaluates_without_eval() -> None:
    expression = parse_formula("round([revenue] * 1.15, 2) >= 100")
    assert evaluate(expression, {"revenue": 100}) is True
    with pytest.raises(ApplicationError):
        parse_formula('round([revenue], 2) + evil("payload")')


def test_formula_fields_and_allowlisted_functions() -> None:
    expression = parse_formula("coalesce([revenue], 0) * 2")
    assert referenced_fields(expression) == {"revenue"}
    assert evaluate(expression, {"revenue": 21}) == 42
    with pytest.raises(ApplicationError) as raised:
        parse_formula('__import__("os")')
    assert raised.value.code == "INVALID_FORMULA"


def test_pipeline_preserves_database_numerics_for_formulas() -> None:
    revenue = Decimal("1250000.50")
    assert normalize(revenue) is revenue
    filtered = transform(
        NodeInput(
            key="filter",
            type="filter",
            title="Positive revenue",
            x=0,
            y=0,
            config={"formula": "[revenue] > 0"},
        ),
        [[{"revenue": revenue}]],
    )
    calculated = transform(
        NodeInput(
            key="formula",
            type="formula",
            title="Adjusted revenue",
            x=0,
            y=0,
            config={"field": "adjusted_revenue", "formula": "round([revenue] * 1.1, 2)"},
        ),
        [filtered],
    )
    assert calculated == [
        {"revenue": Decimal("1250000.50"), "adjusted_revenue": Decimal("1375000.55")}
    ]


def test_row_validation_preserves_valid_rows_and_rejection_reasons() -> None:
    node = NodeInput(
        key="validate",
        type="row-validation",
        title="Validate source rows",
        x=0,
        y=0,
        config={
            "rules": [
                {"formula": "not isempty([customer])", "reason": "CUSTOMER_REQUIRED"},
                {"formula": "tonumber([amount]) >= 0", "reason": "AMOUNT_NON_NEGATIVE"},
            ]
        },
    )
    valid, rejected = validate_rows(
        node,
        [
            {"id": "1", "customer": "Ada", "amount": "12.50"},
            {"id": "2", "customer": "", "amount": "9"},
            {"id": "3", "customer": "Lin", "amount": "-1"},
        ],
    )
    assert valid == [{"id": "1", "customer": "Ada", "amount": "12.50"}]
    assert rejected == [
        {
            "id": "2",
            "customer": "",
            "amount": "9",
            "_invalid_reasons": ["CUSTOMER_REQUIRED"],
        },
        {
            "id": "3",
            "customer": "Lin",
            "amount": "-1",
            "_invalid_reasons": ["AMOUNT_NON_NEGATIVE"],
        },
    ]


def test_formula_comparisons_coerce_mixed_numeric_types() -> None:
    assert evaluate(parse_formula("[quantity] > 0"), {"quantity": 3}) is True
    assert evaluate(parse_formula("[quantity] <= 3.0"), {"quantity": 3}) is True
    assert evaluate(parse_formula("[discount] < 30"), {"discount": Decimal("12.5")}) is True


def test_non_division_operations_do_not_evaluate_an_unused_division() -> None:
    assert evaluate(parse_formula("[price] * 0"), {"price": Decimal("25.00")}) == 0
    assert evaluate(parse_formula("[price] - 0"), {"price": Decimal("25.00")}) == 25


def test_registry_contains_no_arbitrary_code_or_network_nodes() -> None:
    assert not (
        {"sql-transform", "python-transform", "source-rest", "shell"} & NODE_REGISTRY.keys()
    )


def test_source_dataset_schema_snapshot_is_strictly_validated() -> None:
    valid = NodeInput(
        key="source",
        type="source-dataset",
        title="Orders",
        x=0,
        y=0,
        config={
            "source_type": "dataset",
            "dataset_id": str(uuid4()),
            "dataset_version": 2,
            "columns": ["order_id"],
            "schema_snapshot": [{"name": "order_id", "type": "bigint", "nullable": False}],
            "row_limit": 1000,
        },
    )
    assert _typed_config_issues(valid) == []

    invalid = valid.model_copy(
        update={"config": {**valid.config, "schema_snapshot": [{"name": "order_id"}]}}
    )
    issues = _typed_config_issues(invalid)
    assert issues
    assert issues[0].field == "config.schema_snapshot"


def test_artifact_storage_rejects_paths_and_token_is_tenant_bound(tmp_path: Path) -> None:
    storage = PipelineArtifactStorage(str(tmp_path))
    with pytest.raises(ArtifactStorageError):
        storage.write("../../secret.csv", b"data")
    claims = DownloadClaims(uuid4(), uuid4(), uuid4(), uuid4())
    signer = DownloadTokens("unit-test-signing-key", 300)
    assert signer.verify(signer.create(claims)) == claims
    with pytest.raises(ArtifactStorageError):
        DownloadTokens("other-signing-key", 300).verify(signer.create(claims))
    key = f"{uuid4()}/{uuid4()}/{uuid4()}/{uuid4()}.csv"
    storage.write(key, b"data")
    assert storage.path(key).read_bytes() == b"data"
    storage.delete(key)
    with pytest.raises(ArtifactStorageError):
        storage.path(key)


@pytest.mark.asyncio
async def test_pipeline_download_token_is_single_use_and_tenant_qualified() -> None:
    class RedisStub:
        def __init__(self) -> None:
            self.keys: set[str] = set()

        async def set(self, key: str, _value: str, *, ex: int, nx: bool) -> bool:
            assert ex > 0 and nx
            if key in self.keys:
                return False
            self.keys.add(key)
            return True

    claims = DownloadClaims(uuid4(), uuid4(), uuid4(), uuid4())
    signer = DownloadTokens("unit-test-signing-key", 300)
    token = signer.create(claims)
    redis = cast(Redis, RedisStub())

    assert await signer.consume(token, redis, "vip:jobs") == claims
    with pytest.raises(ArtifactStorageError):
        await signer.consume(token, redis, "vip:jobs")


@pytest.mark.asyncio
async def test_pipeline_worker_renews_active_lease(settings: Settings) -> None:
    class Result:
        rowcount = 1

    class Session:
        def __init__(self) -> None:
            self.executions = 0
            self.commits = 0

        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def execute(self, _statement: object) -> Result:
            self.executions += 1
            return Result()

        async def commit(self) -> None:
            self.commits += 1

        async def rollback(self) -> None:
            return None

    class SessionFactory:
        def __init__(self, session: Session) -> None:
            self.session = session

        def __call__(self) -> Session:
            return self.session

    class DatabaseStub:
        def __init__(self, session: Session) -> None:
            self.session_factory = SessionFactory(session)

    session = Session()
    stop = asyncio.Event()
    task = asyncio.create_task(
        heartbeat_lease(
            cast(Database, DatabaseStub(session)),
            uuid4(),
            "worker:test",
            settings.model_copy(update={"PIPELINE_WORKER_LEASE_SECONDS": 0.03}),
            stop,
        )
    )
    await asyncio.sleep(0.3)
    stop.set()
    await task
    assert session.executions >= 1
    assert session.commits == session.executions
