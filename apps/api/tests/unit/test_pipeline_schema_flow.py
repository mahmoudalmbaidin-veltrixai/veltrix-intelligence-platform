"""Unit coverage for schema propagation + Select/Rename structured validation."""

from __future__ import annotations

import pytest

from vip_api.pipelines.schema_flow import (
    Column,
    propagate,
    rename_output,
    select_output,
)
from vip_api.pipelines.schemas import EdgeInput, NodeInput, ValidationIssue

pytestmark = pytest.mark.unit

COLS = [
    Column("id", "integer", False),
    Column("name", "string", True),
    Column("email", "string", True),
]


def _codes(issues: list[ValidationIssue]) -> list[str]:
    return [issue.code for issue in issues]


# --- Select ---


def test_select_keeps_requested_columns_in_config_order() -> None:
    out, issues = select_output("s", COLS, {"columns": ["email", "id"]})
    assert issues == []
    assert [c.name for c in out or []] == ["email", "id"]  # matches worker execution order


def test_select_missing_column_is_structured_error() -> None:
    out, issues = select_output("s", COLS, {"columns": ["id", "ghost"]})
    assert "PIPELINE_COLUMN_NOT_FOUND" in _codes(issues)
    assert issues[-1].field == "config.columns" or issues[0].field == "config.columns"
    assert [c.name for c in out or []] == ["id"]  # ghost dropped from output


def test_select_duplicate_column_is_flagged() -> None:
    _, issues = select_output("s", COLS, {"columns": ["id", "id"]})
    assert "PIPELINE_DUPLICATE_COLUMN" in _codes(issues)


def test_select_zero_output_is_flagged() -> None:
    _, issues = select_output("s", COLS, {"columns": ["ghost"]})
    assert "PIPELINE_EMPTY_OUTPUT_SCHEMA" in _codes(issues)


# --- Rename ---


def test_rename_preserves_type_and_nullability() -> None:
    out, issues = rename_output("r", COLS, {"renames": {"name": "full_name"}})
    assert issues == []
    renamed = {c.name: c for c in out or []}
    assert "full_name" in renamed
    assert renamed["full_name"].data_type == "string"
    assert renamed["full_name"].nullable is True
    assert [c.name for c in out or []] == ["id", "full_name", "email"]  # order preserved


def test_rename_missing_source_is_error() -> None:
    _, issues = rename_output("r", COLS, {"renames": {"ghost": "x"}})
    assert "PIPELINE_COLUMN_NOT_FOUND" in _codes(issues)


def test_rename_invalid_target_name_is_error() -> None:
    _, issues = rename_output("r", COLS, {"renames": {"name": "bad name!"}})
    assert "PIPELINE_INVALID_COLUMN_NAME" in _codes(issues)


def test_rename_empty_target_is_error() -> None:
    _, issues = rename_output("r", COLS, {"renames": {"name": "  "}})
    assert "PIPELINE_INVALID_COLUMN_NAME" in _codes(issues)


def test_rename_collision_with_existing_column_is_error() -> None:
    # renaming "name" -> "email" collides with the untouched "email" column
    _, issues = rename_output("r", COLS, {"renames": {"name": "email"}})
    assert "PIPELINE_RENAME_COLLISION" in _codes(issues)


# --- Propagation through the graph ---


def _node(key: str, node_type: str, config: dict[str, object] | None = None) -> NodeInput:
    return NodeInput(key=key, type=node_type, title=key, x=0, y=0, config=config or {})


def test_propagation_source_to_select_to_rename() -> None:
    nodes = {
        "src": _node("src", "source-dataset"),
        "sel": _node("sel", "select-columns", {"columns": ["id", "email"]}),
        "ren": _node("ren", "rename-columns", {"renames": {"email": "email_address"}}),
    }
    edges = [
        EdgeInput(key="e1", source="src", target="sel"),
        EdgeInput(key="e2", source="sel", target="ren"),
    ]
    order = ["src", "sel", "ren"]
    schemas, issues = propagate(order, nodes, edges, {"src": COLS})
    assert issues == []
    assert [c.name for c in schemas["sel"] or []] == ["id", "email"]
    assert [c.name for c in schemas["ren"] or []] == ["id", "email_address"]


def test_propagation_detects_downstream_missing_column_after_select() -> None:
    # Select drops "email"; a later Rename referencing it must fail.
    nodes = {
        "src": _node("src", "source-dataset"),
        "sel": _node("sel", "select-columns", {"columns": ["id"]}),
        "ren": _node("ren", "rename-columns", {"renames": {"email": "x"}}),
    }
    edges = [
        EdgeInput(key="e1", source="src", target="sel"),
        EdgeInput(key="e2", source="sel", target="ren"),
    ]
    _, issues = propagate(["src", "sel", "ren"], nodes, edges, {"src": COLS})
    assert "PIPELINE_COLUMN_NOT_FOUND" in _codes(issues)


def test_unknown_source_schema_skips_checks() -> None:
    # No resolved source schema -> unknown downstream -> no false positives.
    nodes = {
        "src": _node("src", "source-dataset"),
        "sel": _node("sel", "select-columns", {"columns": ["whatever"]}),
    }
    edges = [EdgeInput(key="e1", source="src", target="sel")]
    _, issues = propagate(["src", "sel"], nodes, edges, {})
    assert issues == []


def test_opaque_node_blocks_downstream_schema_inference() -> None:
    # Aggregate output is not modelled, so a downstream Select is not checked.
    nodes = {
        "src": _node("src", "source-dataset"),
        "agg": _node("agg", "aggregate", {"group_by": ["id"], "aggregations": []}),
        "sel": _node("sel", "select-columns", {"columns": ["anything"]}),
    }
    edges = [
        EdgeInput(key="e1", source="src", target="agg"),
        EdgeInput(key="e2", source="agg", target="sel"),
    ]
    _, issues = propagate(["src", "agg", "sel"], nodes, edges, {"src": COLS})
    assert issues == []
