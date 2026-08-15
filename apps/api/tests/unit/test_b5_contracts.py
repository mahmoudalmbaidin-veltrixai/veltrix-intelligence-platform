"""B5 contract, compiler, limit, and injection safety tests."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from vip_api.datasets.discovery import normalize_postgresql_type
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.datasets.schemas import DatasetCreate, QualityRuleCreate
from vip_api.datasets.services import source_key
from vip_api.governance.policies import SYSTEM_PERMISSION_KEYS
from vip_api.semantic.models import SemanticDimension, SemanticMeasure, SemanticMetric
from vip_api.semantic.query import PostgreSQLSemanticQueryCompiler, quote_identifier
from vip_api.semantic.schemas import QueryFilter, SemanticQueryRequest

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_b5_permissions_are_registered() -> None:
    assert {
        "dataset.discover",
        "dataset.quality.manage",
        "dataset.lineage.manage",
        "semantic_model.publish",
        "semantic.query",
        "glossary.approve",
    } <= SYSTEM_PERMISSION_KEYS


def test_source_identity_is_deterministic_and_connection_specific() -> None:
    connection = uuid4()
    first = source_key(connection, "VIP", "Public", "Orders", "table")
    assert first == source_key(connection, "vip", "public", "orders", "table")
    assert first != source_key(uuid4(), "vip", "public", "orders", "table")


def test_discovery_type_normalization_fails_safe() -> None:
    assert normalize_postgresql_type("NUMERIC") == "decimal"
    assert normalize_postgresql_type("timestamp with time zone") == "datetime"
    assert normalize_postgresql_type("extension_specific") == "unknown"


def test_arbitrary_sql_quality_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError):
        QualityRuleCreate(
            rule_type="not_null",
            name="unsafe",
            configuration={"sql": "DROP TABLE datasets"},
        )


def test_dataset_create_requires_an_explicit_writable_destination_opt_in() -> None:
    common = {
        "connection_id": uuid4(),
        "dataset_type": "table",
        "source_schema": "public",
        "source_name": "curated_output",
    }
    assert DatasetCreate(**common).is_read_only is True
    assert DatasetCreate(**common, is_read_only=False).is_read_only is False


def test_query_contract_rejects_raw_sql_and_malicious_keys() -> None:
    with pytest.raises(ValidationError):
        SemanticQueryRequest.model_validate(
            {
                "semantic_model_id": str(uuid4()),
                "metrics": ["revenue; DROP TABLE datasets"],
                "dimensions": [],
                "filters": [],
                "sql": "SELECT * FROM secrets",
            }
        )
    with pytest.raises(ValidationError):
        QueryFilter(field="country", operator="between", value=["one"])


def test_identifier_quoting_escapes_metadata_names() -> None:
    assert quote_identifier('order"value') == '"order""value"'
    with pytest.raises(ValueError):
        quote_identifier("bad\x00name")


def test_postgresql_compiler_binds_values_and_emits_one_read_only_select() -> None:
    organization_id, workspace_id, dataset_id, field_id, model_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    dataset = Dataset(
        id=dataset_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        connection_id=uuid4(),
        dataset_type="table",
        source_schema="public",
        source_name="orders",
        source_key="safe",
        qualified_name="public.orders",
        display_name="Orders",
        source_object_type="table",
    )
    field = DatasetField(
        id=field_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        source_name="country",
        display_name="Country",
        ordinal_position=1,
        physical_data_type="text",
        normalized_data_type="string",
        is_nullable=False,
    )
    measure = SemanticMeasure(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        semantic_model_id=model_id,
        dataset_id=dataset_id,
        key="orders",
        name="Orders",
        aggregation="count",
        data_type="integer",
    )
    metric = SemanticMetric(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        semantic_model_id=model_id,
        key="order_count",
        name="Order Count",
        metric_type="measure",
        base_measure_id=measure.id,
    )
    dimension = SemanticDimension(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        semantic_model_id=model_id,
        dataset_id=dataset_id,
        field_id=field_id,
        key="country",
        name="Country",
        dimension_type="categorical",
        data_type="string",
    )
    malicious_value = "x'; DROP TABLE datasets; --"
    request = SemanticQueryRequest(
        semantic_model_id=model_id,
        metrics=["order_count"],
        dimensions=["country"],
        filters=[QueryFilter(field="country", operator="equals", value=malicious_value)],
        limit=10,
    )
    compiled = PostgreSQLSemanticQueryCompiler().compile(
        request,
        dataset,
        {"country": (dimension, field)},
        {"order_count": (metric, measure, None)},
    )
    assert compiled.statement.startswith("SELECT ")
    assert ";" not in compiled.statement and "--" not in compiled.statement
    assert malicious_value not in compiled.statement
    assert compiled.parameters[0] == malicious_value


def test_postgresql_compiler_emits_safe_ratio_metric() -> None:
    organization_id, workspace_id, dataset_id, model_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    dataset = Dataset(
        id=dataset_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        connection_id=uuid4(),
        dataset_type="table",
        source_schema="public",
        source_name="sales",
        source_key="safe-ratio",
        qualified_name="public.sales",
        display_name="Sales",
        source_object_type="table",
    )
    fields = [
        DatasetField(
            id=uuid4(),
            organization_id=organization_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            source_name=name,
            display_name=name,
            ordinal_position=index,
            physical_data_type="numeric",
            normalized_data_type="decimal",
            is_nullable=False,
        )
        for index, name in enumerate(("gross_profit", "net_revenue"), start=1)
    ]
    measures = [
        SemanticMeasure(
            id=uuid4(),
            organization_id=organization_id,
            workspace_id=workspace_id,
            semantic_model_id=model_id,
            dataset_id=dataset_id,
            key=f"{field.source_name}_sum",
            name=field.display_name,
            aggregation="sum",
            data_type="decimal",
        )
        for field in fields
    ]
    base_metrics = [
        SemanticMetric(
            id=uuid4(),
            organization_id=organization_id,
            workspace_id=workspace_id,
            semantic_model_id=model_id,
            key=field.source_name,
            name=field.display_name,
            metric_type="measure",
            base_measure_id=measure.id,
        )
        for field, measure in zip(fields, measures, strict=True)
    ]
    ratio = SemanticMetric(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        semantic_model_id=model_id,
        key="profit_margin",
        name="Profit Margin",
        metric_type="ratio",
        numerator_metric_id=base_metrics[0].id,
        denominator_metric_id=base_metrics[1].id,
    )
    request = SemanticQueryRequest(
        semantic_model_id=model_id,
        metrics=["profit_margin"],
        dimensions=[],
        limit=10,
    )
    compiled = PostgreSQLSemanticQueryCompiler().compile(
        request,
        dataset,
        {},
        {},
        {
            "profit_margin": (
                ratio,
                (measures[0], fields[0]),
                (measures[1], fields[1]),
            )
        },
    )
    assert (
        '(SUM("gross_profit")) / NULLIF((SUM("net_revenue")), 0) AS "profit_margin"'
        in compiled.statement
    )
    assert compiled.columns[0].data_type == "decimal"


def test_postgresql_compiler_coerces_iso_date_range_parameters() -> None:
    organization_id, workspace_id, dataset_id, model_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    dataset = Dataset(
        id=dataset_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        connection_id=uuid4(),
        dataset_type="table",
        source_schema="public",
        source_name="sales",
        source_key="date-range",
        qualified_name="public.sales",
        display_name="Sales",
        source_object_type="table",
    )
    field = DatasetField(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        source_name="order_date",
        display_name="Order Date",
        ordinal_position=1,
        physical_data_type="date",
        normalized_data_type="date",
        is_nullable=False,
    )
    measure = SemanticMeasure(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        semantic_model_id=model_id,
        dataset_id=dataset_id,
        key="orders",
        name="Orders",
        aggregation="count",
        data_type="integer",
    )
    metric = SemanticMetric(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        semantic_model_id=model_id,
        key="order_count",
        name="Order Count",
        metric_type="measure",
        base_measure_id=measure.id,
    )
    dimension = SemanticDimension(
        id=uuid4(),
        organization_id=organization_id,
        workspace_id=workspace_id,
        semantic_model_id=model_id,
        dataset_id=dataset_id,
        field_id=field.id,
        key="order_date",
        name="Order Date",
        dimension_type="time",
        data_type="date",
    )
    request = SemanticQueryRequest(
        semantic_model_id=model_id,
        metrics=["order_count"],
        filters=[
            QueryFilter(
                field="order_date",
                operator="between",
                value=["2024-01-01", "2024-12-31"],
            )
        ],
    )

    compiled = PostgreSQLSemanticQueryCompiler().compile(
        request,
        dataset,
        {"order_date": (dimension, field)},
        {"order_count": (metric, measure, None)},
    )

    assert '"order_date" BETWEEN $1 AND $2' in compiled.statement
    assert compiled.parameters[:2] == (date(2024, 1, 1), date(2024, 12, 31))
