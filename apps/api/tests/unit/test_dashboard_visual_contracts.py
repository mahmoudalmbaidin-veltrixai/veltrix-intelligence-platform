from __future__ import annotations

from collections.abc import Mapping

from vip_api.dashboards.visual_contracts import (
    SCATTER_CONFIGURATION_ERROR,
    flatten_pivot,
    pivot_contract,
    scatter_configuration_error,
    scatter_contract,
)


def test_pivot_builds_deterministic_region_quarter_matrix() -> None:
    columns: list[dict[str, object]] = [
        {"key": "region", "label": "Region", "role": "dimension"},
        {"key": "quarter", "label": "Quarter", "role": "dimension"},
        {"key": "revenue", "label": "Revenue", "role": "metric"},
    ]
    rows: list[Mapping[str, object]] = [
        {"region": "Region A", "quarter": "Q1", "revenue": 111},
        {"region": "Region A", "quarter": "Q2", "revenue": 222},
        {"region": "Region B", "quarter": "Q1", "revenue": 333},
        {"region": "Region B", "quarter": "Q2", "revenue": 444},
    ]

    contract = pivot_contract(["region", "quarter"], ["revenue"], columns, rows)
    rendered_columns, rendered_rows = flatten_pivot(contract)

    assert contract["row_fields"] == ["region"]
    assert contract["column_fields"] == ["quarter"]
    assert [column["label"] for column in rendered_columns] == ["Region", "Q1", "Q2"]
    assert rendered_rows == [
        {"region": "Region A", "__pivot_value_0": 111, "__pivot_value_1": 222},
        {"region": "Region B", "__pivot_value_0": 333, "__pivot_value_1": 444},
    ]


def test_pivot_preserves_multiple_measures_and_null_cells() -> None:
    columns: list[dict[str, object]] = [
        {"key": "region", "label": "Region"},
        {"key": "quarter", "label": "Quarter"},
        {"key": "revenue", "label": "Revenue"},
        {"key": "profit", "label": "Profit"},
    ]
    rows: list[Mapping[str, object]] = [
        {"region": "Long Region A", "quarter": "Q1", "revenue": 10, "profit": 2},
        {"region": "Long Region A", "quarter": "Q2", "revenue": None, "profit": -3},
    ]

    rendered_columns, rendered_rows = flatten_pivot(
        pivot_contract(["region", "quarter"], ["revenue", "profit"], columns, rows)
    )

    assert [column["label"] for column in rendered_columns] == [
        "Region",
        "Q1 · Revenue",
        "Q1 · Profit",
        "Q2 · Revenue",
        "Q2 · Profit",
    ]
    assert list(rendered_rows[0].values()) == ["Long Region A", 10, 2, None, -3]


def test_scatter_uses_configured_metric_order_and_omits_null_pairs() -> None:
    columns: list[dict[str, object]] = [
        {"key": "group", "data_type": "string"},
        {"key": "profit", "data_type": "decimal"},
        {"key": "revenue", "data_type": "integer"},
        {"key": "unrelated", "data_type": "integer"},
    ]
    rows: list[Mapping[str, object]] = [
        {"group": "A", "profit": -2, "revenue": 10, "unrelated": 999},
        {"group": "B", "profit": None, "revenue": 20, "unrelated": 888},
        {"group": "A", "profit": 4, "revenue": 30, "unrelated": 777},
    ]

    contract = scatter_contract(["revenue", "profit"], ["group"], columns, rows)

    assert contract["valid"] is True
    assert contract["x_field"] == "revenue"
    assert contract["y_field"] == "profit"
    assert contract["points"] == [
        {"x": 10.0, "y": -2.0, "group": "A"},
        {"x": 30.0, "y": 4.0, "group": "A"},
    ]


def test_scatter_rejects_missing_or_non_numeric_xy() -> None:
    assert scatter_configuration_error(["x"]) == SCATTER_CONFIGURATION_ERROR
    contract = scatter_contract(
        ["x", "y"],
        [],
        [{"key": "x", "data_type": "string"}, {"key": "y", "data_type": "integer"}],
        [{"x": "alpha", "y": 2}],
    )
    assert contract == {
        "valid": False,
        "error": SCATTER_CONFIGURATION_ERROR,
        "points": [],
    }
