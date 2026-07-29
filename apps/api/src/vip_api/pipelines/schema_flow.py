"""Pure schema propagation and structured validation for schema-aware nodes.

This models how a column schema flows through a pipeline graph so that Select
and Rename nodes can be validated against their *real* upstream columns at
validate/publish time — matching the deterministic worker execution semantics
in ``execution.py`` (Select keeps exactly ``config.columns`` in order; Rename
maps ``config.renames`` keys).

The functions are deliberately free of database/IO so they are exhaustively
unit-testable. ``validate_graph`` supplies the resolved source schemas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vip_api.pipelines.schemas import EdgeInput, NodeInput, ValidationIssue

# Output-name rule for user-authored names (Rename targets). Mirrors the
# frontend NodeRenameMap validation so client and server agree.
_VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Codes treated as hard errors (block publish); the rest are surfaced as warnings.
ERROR_CODES = frozenset(
    {"PIPELINE_COLUMN_NOT_FOUND", "PIPELINE_RENAME_COLLISION", "PIPELINE_INVALID_COLUMN_NAME"}
)

# Nodes that pass their input schema through unchanged.
_PASSTHROUGH = frozenset({"filter", "sort", "deduplicate", "null-handling", "row-validation"})
# Nodes whose output schema this module cannot model precisely; downstream nodes
# then receive an unknown schema and skip schema-aware checks (never false errors).
_OPAQUE = frozenset({"join", "aggregate", "pivot", "unpivot", "output-dataset", "file-export"})


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    data_type: str = "string"
    nullable: bool = True


def _dedupe(columns: list[Column]) -> list[Column]:
    """Union columns by name, preserving first-seen order (like the worker)."""
    seen: dict[str, Column] = {}
    for column in columns:
        seen.setdefault(column.name, column)
    return list(seen.values())


def select_output(
    node_key: str, incoming: list[Column], config: dict[str, object]
) -> tuple[list[Column] | None, list[ValidationIssue]]:
    requested = config.get("columns")
    if not isinstance(requested, list):
        return None, []  # shape errors are raised by _typed_config_issues
    issues: list[ValidationIssue] = []
    by_name = {column.name: column for column in incoming}
    seen: set[str] = set()
    for name in requested:
        if not isinstance(name, str):
            continue
        if name in seen:
            issues.append(
                ValidationIssue(
                    code="PIPELINE_DUPLICATE_COLUMN",
                    message=f"The column is selected more than once: {name}",
                    node_key=node_key,
                    field="config.columns",
                )
            )
        seen.add(name)
        if name not in by_name:
            issues.append(
                ValidationIssue(
                    code="PIPELINE_COLUMN_NOT_FOUND",
                    message=f"The selected column no longer exists in the upstream schema: {name}",
                    node_key=node_key,
                    field="config.columns",
                )
            )
    # Output order matches worker execution: the order of config.columns, existing only.
    output = [by_name[name] for name in dict.fromkeys(requested) if name in by_name]
    if not output:
        issues.append(
            ValidationIssue(
                code="PIPELINE_EMPTY_OUTPUT_SCHEMA",
                message="Select keeps no columns; downstream nodes receive an empty schema.",
                node_key=node_key,
                field="config.columns",
            )
        )
    return output, issues


def rename_output(
    node_key: str, incoming: list[Column], config: dict[str, object]
) -> tuple[list[Column] | None, list[ValidationIssue]]:
    renames = config.get("renames")
    if not isinstance(renames, dict):
        return None, []
    issues: list[ValidationIssue] = []
    by_name = {column.name: column for column in incoming}
    for source, target in renames.items():
        if source not in by_name:
            issues.append(
                ValidationIssue(
                    code="PIPELINE_COLUMN_NOT_FOUND",
                    message=f"The renamed column no longer exists in the upstream schema: {source}",
                    node_key=node_key,
                    field="config.renames",
                )
            )
        if not isinstance(target, str) or not target.strip() or not _VALID_NAME.match(target):
            issues.append(
                ValidationIssue(
                    code="PIPELINE_INVALID_COLUMN_NAME",
                    message=(
                        f"“{target}” is not a valid column name "
                        "(use letters, numbers and underscore)."
                    ),
                    node_key=node_key,
                    field="config.renames",
                )
            )
    # Data type and nullability are preserved; only the name changes.
    output = [
        Column(renames.get(column.name, column.name), column.data_type, column.nullable)
        for column in incoming
    ]
    counts: dict[str, int] = {}
    for column in output:
        counts[column.name] = counts.get(column.name, 0) + 1
    for name, count in counts.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    code="PIPELINE_RENAME_COLLISION",
                    message=f"The rename produces a duplicate output column: {name}",
                    node_key=node_key,
                    field="config.renames",
                )
            )
    return output, issues


def propagate(
    order: list[str],
    node_map: dict[str, NodeInput],
    edges: list[EdgeInput],
    source_schemas: dict[str, list[Column] | None],
) -> tuple[dict[str, list[Column] | None], list[ValidationIssue]]:
    """Walk the graph in topological order, computing each node's output schema
    and collecting structured Select/Rename validation issues.

    ``None`` means the schema at that node is unknown (e.g. an unresolved source
    or an opaque transform); nodes with an unknown input skip schema checks.
    """
    incoming: dict[str, list[str]] = {key: [] for key in node_map}
    for edge in edges:
        if edge.source in node_map and edge.target in node_map:
            incoming[edge.target].append(edge.source)

    schemas: dict[str, list[Column] | None] = {}
    issues: list[ValidationIssue] = []

    for key in order:
        node = node_map[key]
        if node.type == "source-dataset":
            schemas[key] = source_schemas.get(key)
            continue

        upstream = [schemas.get(source) for source in incoming.get(key, [])]
        if not upstream or any(schema is None for schema in upstream):
            input_schema: list[Column] | None = None
        else:
            input_schema = _dedupe([column for schema in upstream for column in schema or []])

        if input_schema is None:
            schemas[key] = None
            continue

        if node.type == "select-columns":
            output, node_issues = select_output(key, input_schema, node.config)
            issues.extend(node_issues)
            schemas[key] = output
        elif node.type == "rename-columns":
            output, node_issues = rename_output(key, input_schema, node.config)
            issues.extend(node_issues)
            schemas[key] = output
        elif node.type == "type-convert":
            target = node.config.get("target_type")
            field = node.config.get("field")
            schemas[key] = [
                Column(c.name, str(target), c.nullable)
                if c.name == field and isinstance(target, str)
                else c
                for c in input_schema
            ]
        elif node.type == "formula":
            field = node.config.get("field")
            if isinstance(field, str) and field:
                schemas[key] = [c for c in input_schema if c.name != field] + [
                    Column(field, "number")
                ]
            else:
                schemas[key] = input_schema
        elif node.type == "union" or node.type in _PASSTHROUGH:
            schemas[key] = input_schema
        else:  # _OPAQUE and anything unmodelled
            schemas[key] = None

    return schemas, issues
