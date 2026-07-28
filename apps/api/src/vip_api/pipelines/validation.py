"""Authoritative graph and typed node configuration validation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.models import Connection
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.governance.context import AuthorizationContext
from vip_api.pipelines.formula import parse_formula
from vip_api.pipelines.registry import NODE_REGISTRY
from vip_api.pipelines.schemas import EdgeInput, NodeInput, ValidationIssue, ValidationResponse

_CONFIG_KEYS: dict[str, frozenset[str]] = {
    "source-dataset": frozenset(
        {
            "source_type",
            "dataset_id",
            "dataset_version",
            "schema_snapshot",
            "columns",
            "aliases",
            "row_limit",
        }
    ),
    "select-columns": frozenset({"columns"}),
    "rename-columns": frozenset({"renames"}),
    "filter": frozenset({"formula"}),
    "sort": frozenset({"fields"}),
    "join": frozenset({"left_field", "right_field", "join_type"}),
    "union": frozenset({"distinct"}),
    "aggregate": frozenset({"group_by", "aggregations"}),
    "formula": frozenset({"field", "formula"}),
    "row-validation": frozenset({"rules"}),
    "type-convert": frozenset({"field", "target_type"}),
    "deduplicate": frozenset({"fields"}),
    "null-handling": frozenset({"field", "strategy", "value"}),
    "output-dataset": frozenset({"dataset_id", "write_mode"}),
    "file-export": frozenset({"format", "filename"}),
}


def _typed_config_issues(node: NodeInput) -> list[ValidationIssue]:
    config, kind = node.config, node.type
    issues: list[ValidationIssue] = []

    def invalid(field: str, message: str) -> None:
        issues.append(
            ValidationIssue(
                code="INVALID_NODE_CONFIG", message=message, node_key=node.key, field=field
            )
        )

    def string(field: str, *, required: bool = True) -> str | None:
        value = config.get(field)
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value.strip() or len(value) > 255:
            invalid(f"config.{field}", f"{field} must be a non-empty bounded string.")
            return None
        return value

    def strings(field: str, *, required: bool = True) -> list[str] | None:
        value = config.get(field)
        if value is None and not required:
            return None
        if (
            not isinstance(value, list)
            or (required and not value)
            or len(value) > 250
            or any(not isinstance(item, str) or not item or len(item) > 255 for item in value)
        ):
            invalid(f"config.{field}", f"{field} must contain bounded field names.")
            return None
        return value

    if kind == "source-dataset":
        if config.get("source_type", "dataset") != "dataset":
            invalid(
                "config.source_type",
                "Persisted pipeline sources must reference a registered governed dataset.",
            )
        strings("columns", required=False)
        version = config.get("dataset_version")
        if version is not None and (
            isinstance(version, bool) or not isinstance(version, int) or version < 1
        ):
            invalid("config.dataset_version", "dataset_version must be a positive integer.")
        snapshot = config.get("schema_snapshot")
        if snapshot is not None and (
            not isinstance(snapshot, list)
            or len(snapshot) > 250
            or any(
                not isinstance(item, dict)
                or set(item) != {"name", "type", "nullable"}
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("type"), str)
                or not isinstance(item.get("nullable"), bool)
                for item in snapshot
            )
        ):
            invalid(
                "config.schema_snapshot",
                "schema_snapshot must contain bounded name, type, and nullable field metadata.",
            )
        aliases = config.get("aliases")
        if aliases is not None and (
            not isinstance(aliases, dict)
            or any(
                not isinstance(key, str) or not isinstance(value, str) or not key or not value
                for key, value in aliases.items()
            )
        ):
            invalid("config.aliases", "aliases must map source fields to bounded output names.")
        limit = config.get("row_limit", 10000)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_000_000:
            invalid("config.row_limit", "row_limit must be between 1 and 1000000.")
    elif kind in {"select-columns", "deduplicate"}:
        strings("columns" if kind == "select-columns" else "fields")
    elif kind == "rename-columns":
        value = config.get("renames")
        if (
            not isinstance(value, dict)
            or not value
            or any(
                not isinstance(key, str) or not isinstance(target, str) or not key or not target
                for key, target in value.items()
            )
        ):
            invalid("config.renames", "renames must map source fields to output fields.")
    elif kind == "sort":
        value = config.get("fields")
        mapping_valid = (
            isinstance(value, dict)
            and bool(value)
            and all(
                isinstance(key, str) and direction in {"asc", "desc"}
                for key, direction in value.items()
            )
        )
        list_valid = (
            isinstance(value, list)
            and bool(value)
            and all(
                isinstance(item, dict)
                and set(item) == {"field", "direction"}
                and isinstance(item.get("field"), str)
                and item.get("direction") in {"asc", "desc"}
                for item in value
            )
        )
        if not (mapping_valid or list_valid):
            invalid("config.fields", "Sort fields must map field names to asc or desc.")
    elif kind == "join":
        string("left_field")
        string("right_field")
        if config.get("join_type") not in {"inner", "left", "full"}:
            invalid("config.join_type", "join_type must be inner, left, or full.")
    elif kind == "union":
        if not isinstance(config.get("distinct", False), bool):
            invalid("config.distinct", "distinct must be a boolean.")
    elif kind == "aggregate":
        strings("group_by", required=False)
        values = config.get("aggregations")
        if (
            not isinstance(values, list)
            or not values
            or any(
                not isinstance(item, dict)
                or set(item) != {"field", "operation", "alias"}
                or not isinstance(item.get("field"), str)
                or item.get("operation") not in {"count", "sum", "min", "max", "average"}
                or not isinstance(item.get("alias"), str)
                for item in values
            )
        ):
            invalid("config.aggregations", "Aggregations must use approved fields and operations.")
    elif kind == "formula":
        string("field")
    elif kind == "row-validation":
        rules = config.get("rules")
        if (
            not isinstance(rules, list)
            or not 1 <= len(rules) <= 50
            or any(
                not isinstance(rule, dict)
                or set(rule) != {"formula", "reason"}
                or not isinstance(rule.get("formula"), str)
                or not 1 <= len(rule["formula"]) <= 4096
                or not isinstance(rule.get("reason"), str)
                or not 1 <= len(rule["reason"]) <= 255
                for rule in rules
            )
        ):
            invalid(
                "config.rules",
                "rules must contain 1 to 50 bounded formula and reason pairs.",
            )
    elif kind == "type-convert":
        string("field")
        if config.get("target_type") not in {"string", "integer", "number", "boolean"}:
            invalid("config.target_type", "The target type is unsupported.")
    elif kind == "null-handling":
        string("field")
        if config.get("strategy") not in {"drop", "replace"}:
            invalid("config.strategy", "The null strategy must be drop or replace.")
    elif kind == "file-export":
        filename = string("filename", required=False)
        if filename and ("/" in filename or "\\" in filename or ".." in filename):
            invalid("config.filename", "Artifact labels cannot contain paths.")
    return issues


async def validate_graph(
    db: AsyncSession, context: AuthorizationContext, nodes: list[NodeInput], edges: list[EdgeInput]
) -> ValidationResponse:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    node_map = {node.key: node for node in nodes}
    if len(node_map) != len(nodes):
        errors.append(
            ValidationIssue(code="DUPLICATE_NODE_KEY", message="Node keys must be unique.")
        )
    edge_keys = {edge.key for edge in edges}
    if len(edge_keys) != len(edges):
        errors.append(
            ValidationIssue(code="DUPLICATE_EDGE_KEY", message="Edge keys must be unique.")
        )
    incoming: dict[str, list[str]] = {key: [] for key in node_map}
    outgoing: dict[str, list[str]] = {key: [] for key in node_map}
    for edge in edges:
        if edge.source not in node_map or edge.target not in node_map:
            errors.append(
                ValidationIssue(
                    code="UNKNOWN_EDGE_NODE",
                    message="An edge references an unknown node.",
                    field=edge.key,
                )
            )
            continue
        if edge.source == edge.target:
            errors.append(
                ValidationIssue(
                    code="SELF_EDGE",
                    message="A node cannot connect to itself.",
                    node_key=edge.source,
                )
            )
        incoming[edge.target].append(edge.source)
        outgoing[edge.source].append(edge.target)
    dataset_refs: list[tuple[str, UUID]] = []
    for node in nodes:
        definition = NODE_REGISTRY.get(node.type)
        if definition is None:
            errors.append(
                ValidationIssue(
                    code="UNSUPPORTED_NODE_TYPE",
                    message="This node type is not approved for execution.",
                    node_key=node.key,
                )
            )
            continue
        unknown = set(node.config) - _CONFIG_KEYS[node.type]
        if unknown:
            errors.append(
                ValidationIssue(
                    code="UNKNOWN_CONFIG_FIELD",
                    message=f"Unsupported configuration field: {sorted(unknown)[0]}",
                    node_key=node.key,
                )
            )
        errors.extend(_typed_config_issues(node))
        count = len(incoming[node.key])
        if not definition.min_inputs <= count <= definition.max_inputs:
            errors.append(
                ValidationIssue(
                    code="INVALID_INPUT_COUNT",
                    message=(
                        f"Node requires {definition.min_inputs} to {definition.max_inputs} inputs."
                    ),
                    node_key=node.key,
                )
            )
        if node.type == "source-dataset" and not outgoing[node.key]:
            errors.append(
                ValidationIssue(
                    code="SOURCE_DISCONNECTED",
                    message="Connect the source to a downstream node before publishing.",
                    node_key=node.key,
                )
            )
        if node.type in {"source-dataset", "output-dataset"}:
            try:
                dataset_refs.append((node.key, UUID(str(node.config.get("dataset_id", "")))))
            except ValueError:
                errors.append(
                    ValidationIssue(
                        code="INVALID_DATASET_REFERENCE",
                        message="A tenant dataset is required.",
                        node_key=node.key,
                        field="config.dataset_id",
                    )
                )
        if node.type in {"filter", "formula"}:
            formula = node.config.get("formula")
            if not isinstance(formula, str):
                errors.append(
                    ValidationIssue(
                        code="FORMULA_REQUIRED", message="A formula is required.", node_key=node.key
                    )
                )
            else:
                try:
                    parse_formula(formula)
                except Exception as exc:
                    errors.append(
                        ValidationIssue(
                            code="INVALID_FORMULA",
                            message=str(exc),
                            node_key=node.key,
                            field="config.formula",
                        )
                    )
        if node.type == "row-validation":
            rules = node.config.get("rules")
            if isinstance(rules, list):
                for index, rule in enumerate(rules):
                    if not isinstance(rule, dict) or not isinstance(rule.get("formula"), str):
                        continue
                    try:
                        parse_formula(rule["formula"])
                    except Exception as exc:
                        errors.append(
                            ValidationIssue(
                                code="INVALID_FORMULA",
                                message=str(exc),
                                node_key=node.key,
                                field=f"config.rules.{index}.formula",
                            )
                        )
        if node.type == "file-export" and node.config.get("format") not in {"csv", "json"}:
            errors.append(
                ValidationIssue(
                    code="INVALID_EXPORT_FORMAT",
                    message="Only CSV and JSON artifacts are supported.",
                    node_key=node.key,
                )
            )
        if node.type == "output-dataset" and node.config.get("write_mode") not in {
            "append",
            "replace",
        }:
            errors.append(
                ValidationIssue(
                    code="INVALID_WRITE_MODE",
                    message="Write mode must be append or replace.",
                    node_key=node.key,
                )
            )
    org, ws = context.organization_id, context.workspace_id
    if ws is not None and dataset_refs:
        wanted = {dataset_id for _, dataset_id in dataset_refs}
        found_rows = (
            await db.scalars(
                select(Dataset).where(
                    Dataset.organization_id == org,
                    Dataset.workspace_id == ws,
                    Dataset.id.in_(wanted),
                    Dataset.archived_at.is_(None),
                )
            )
        ).all()
        found = {item.id for item in found_rows}
        datasets_by_id = {item.id: item for item in found_rows}
        connection_ids = {item.connection_id for item in found_rows}
        active_connections = set(
            (
                await db.scalars(
                    select(Connection.id).where(
                        Connection.organization_id == org,
                        Connection.workspace_id == ws,
                        Connection.id.in_(connection_ids),
                        Connection.status == "active",
                        Connection.archived_at.is_(None),
                    )
                )
            ).all()
        )
        fields = (
            await db.scalars(
                select(DatasetField).where(
                    DatasetField.organization_id == org,
                    DatasetField.workspace_id == ws,
                    DatasetField.dataset_id.in_(wanted),
                )
            )
        ).all()
        fields_by_dataset: dict[UUID, dict[str, DatasetField]] = {}
        for field in fields:
            fields_by_dataset.setdefault(field.dataset_id, {})[field.source_name] = field
        for node_key, dataset_id in dataset_refs:
            if dataset_id not in found:
                errors.append(
                    ValidationIssue(
                        code="DATASET_NOT_FOUND",
                        message="The referenced dataset is unavailable in this workspace.",
                        node_key=node_key,
                    )
                )
                continue
            node = node_map[node_key]
            if node.type != "source-dataset":
                continue
            dataset = datasets_by_id[dataset_id]
            if dataset.status != "active" or dataset.connection_id not in active_connections:
                errors.append(
                    ValidationIssue(
                        code="SOURCE_UNAVAILABLE",
                        message="The source dataset or its connection is not active.",
                        node_key=node_key,
                    )
                )
            expected_version = node.config.get("dataset_version")
            if expected_version is not None and expected_version != dataset.version:
                errors.append(
                    ValidationIssue(
                        code="SOURCE_SCHEMA_CHANGED",
                        message=(
                            "The source dataset changed after this pipeline source was configured."
                        ),
                        node_key=node_key,
                        field="config.dataset_version",
                    )
                )
            current_fields = fields_by_dataset.get(dataset_id, {})
            selected = node.config.get("columns")
            if isinstance(selected, list):
                missing = sorted(set(selected) - set(current_fields))
                if missing:
                    errors.append(
                        ValidationIssue(
                            code="SOURCE_FIELD_NOT_FOUND",
                            message=f"The source field is unavailable: {missing[0]}",
                            node_key=node_key,
                            field="config.columns",
                        )
                    )
            snapshot = node.config.get("schema_snapshot")
            if isinstance(snapshot, list):
                for item in snapshot:
                    if not isinstance(item, dict):
                        continue
                    current = current_fields.get(str(item.get("name")))
                    if current is None or current.physical_data_type != item.get("type"):
                        errors.append(
                            ValidationIssue(
                                code="SOURCE_SCHEMA_CHANGED",
                                message=f"The source schema changed at field: {item.get('name')}",
                                node_key=node_key,
                                field="config.schema_snapshot",
                            )
                        )
                        break
    indegree = {key: len(values) for key, values in incoming.items()}
    queue = sorted(key for key, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while queue:
        key = queue.pop(0)
        order.append(key)
        for target in sorted(outgoing[key]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(node_map):
        errors.append(
            ValidationIssue(code="PIPELINE_CYCLE", message="Pipeline graphs must be acyclic.")
        )
    if nodes and not any(
        NODE_REGISTRY.get(node.type, None) and NODE_REGISTRY[node.type].category == "output"
        for node in nodes
    ):
        warnings.append(
            ValidationIssue(code="NO_OUTPUT", message="The pipeline has no output node.")
        )
    return ValidationResponse(
        valid=not errors, errors=errors, warnings=warnings, topological_order=order
    )
