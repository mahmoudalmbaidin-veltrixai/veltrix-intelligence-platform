"""Select/Rename parity: the real worker transform (execution.transform) must
agree with schema_flow propagation on columns, order, names, types-by-value and
nullability, for representative data.

Scope note: this exercises the actual per-node worker transform used by
execute_snapshot (not a mock). The source DB read (read_dataset) and the Redis
run queue are I/O plumbing covered by connection/worker infrastructure tests and
are documented as a remaining validation item; this test locks the transform
semantics that the Select/Rename validation is built to mirror.
"""

from __future__ import annotations

import datetime as dt

import pytest

from vip_api.pipelines.execution import transform
from vip_api.pipelines.schema_flow import Column, propagate
from vip_api.pipelines.schemas import EdgeInput, NodeInput

pytestmark = pytest.mark.unit

# Representative rows: numeric, string, date, nullable, duplicate-looking values,
# and a valid-but-unusual column name.
ROWS = [
    {
        "id": 1,
        "name": "Ada",
        "signup_date": dt.date(2024, 1, 5),
        "score": 10,
        "status": "active",
        "order_total_2024": 100,
    },
    {
        "id": 2,
        "name": "Grace",
        "signup_date": dt.date(2024, 2, 9),
        "score": None,  # nullable
        "status": "active",  # duplicate-looking value
        "order_total_2024": 250,
    },
]
SOURCE_COLS = [
    Column("id", "integer", False),
    Column("name", "string", True),
    Column("signup_date", "date", True),
    Column("score", "integer", True),
    Column("status", "string", True),
    Column("order_total_2024", "integer", True),
]


def _node(key: str, node_type: str, config: dict) -> NodeInput:
    return NodeInput(key=key, type=node_type, title=key, x=0, y=0, config=config)


def _propagate_names(order, nodes, edges) -> list[str]:
    node_map = {n.key: n for n in nodes}
    schemas, _ = propagate(order, node_map, edges, {"src": SOURCE_COLS})
    return [c.name for c in schemas[order[-1]] or []]


def test_select_keep_transform_matches_propagation() -> None:
    node = _node("sel", "select-columns", {"columns": ["id", "status", "order_total_2024"]})
    out = transform(node, [ROWS])
    # worker output columns == configured kept columns, in order
    assert [list(row.keys()) for row in out] == [["id", "status", "order_total_2024"]] * len(ROWS)
    # values preserved exactly (including duplicate-looking + numeric)
    assert out[0] == {"id": 1, "status": "active", "order_total_2024": 100}
    # propagation agrees on the output schema
    names = _propagate_names(
        ["src", "sel"],
        [_node("src", "source-dataset", {}), node],
        [EdgeInput(key="e", source="src", target="sel")],
    )
    assert names == ["id", "status", "order_total_2024"]


def test_select_remove_semantics_via_keep_list() -> None:
    # "Remove score+signup_date" is expressed as the kept-list the FE emits.
    kept = ["id", "name", "status", "order_total_2024"]
    node = _node("sel", "select-columns", {"columns": kept})
    out = transform(node, [ROWS])
    assert list(out[1].keys()) == kept
    assert "score" not in out[1] and "signup_date" not in out[1]


def test_rename_transform_preserves_values_types_and_order() -> None:
    node = _node("ren", "rename-columns", {"renames": {"name": "full_name", "score": "points"}})
    out = transform(node, [ROWS])
    # order preserved, only names change; the nullable value stays None
    assert list(out[1].keys()) == [
        "id",
        "full_name",
        "signup_date",
        "points",
        "status",
        "order_total_2024",
    ]
    assert out[1]["points"] is None  # nullability preserved
    assert out[0]["full_name"] == "Ada"  # value + type preserved
    assert isinstance(out[0]["signup_date"], dt.date)
    names = _propagate_names(
        ["src", "ren"],
        [_node("src", "source-dataset", {}), node],
        [EdgeInput(key="e", source="src", target="ren")],
    )
    assert names == ["id", "full_name", "signup_date", "points", "status", "order_total_2024"]


def test_select_then_rename_chain_parity() -> None:
    sel = _node("sel", "select-columns", {"columns": ["id", "name"]})
    ren = _node("ren", "rename-columns", {"renames": {"name": "customer_name"}})
    stage1 = transform(sel, [ROWS])
    stage2 = transform(ren, [stage1])
    assert [list(r.keys()) for r in stage2] == [["id", "customer_name"]] * len(ROWS)
    assert stage2[0] == {"id": 1, "customer_name": "Ada"}
    names = _propagate_names(
        ["src", "sel", "ren"],
        [_node("src", "source-dataset", {}), sel, ren],
        [
            EdgeInput(key="e1", source="src", target="sel"),
            EdgeInput(key="e2", source="sel", target="ren"),
        ],
    )
    assert names == ["id", "customer_name"]  # lineage: name -> customer_name preserved


def test_rename_then_select_chain_parity() -> None:
    ren = _node("ren", "rename-columns", {"renames": {"name": "customer_name"}})
    sel = _node("sel", "select-columns", {"columns": ["customer_name", "id"]})
    stage1 = transform(ren, [ROWS])
    stage2 = transform(sel, [stage1])
    assert [list(r.keys()) for r in stage2] == [["customer_name", "id"]] * len(ROWS)
    names = _propagate_names(
        ["src", "ren", "sel"],
        [_node("src", "source-dataset", {}), ren, sel],
        [
            EdgeInput(key="e1", source="src", target="ren"),
            EdgeInput(key="e2", source="ren", target="sel"),
        ],
    )
    assert names == ["customer_name", "id"]
