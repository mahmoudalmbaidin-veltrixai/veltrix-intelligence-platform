"""Pure semantic contracts shared by dashboard query and export rendering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

SCATTER_CONFIGURATION_ERROR = "Scatter chart requires numeric X and Y fields."
SCATTER_NO_DATA = "Scatter chart has no rows with both X and Y values."

_NUMERIC_TYPES = frozenset(
    {
        "decimal",
        "float",
        "integer",
        "number",
        "numeric",
        "currency",
        "percent",
    }
)


def scatter_configuration_error(metric_keys: Sequence[str]) -> str | None:
    """Return the stable public validation message for an incomplete Scatter."""

    return None if len(metric_keys) >= 2 else SCATTER_CONFIGURATION_ERROR


def scatter_contract(
    metric_keys: Sequence[str],
    dimension_keys: Sequence[str],
    columns: Sequence[Mapping[str, object]],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build configured, null-safe Scatter points without inferring other metrics.

    Metric order is the analytical contract: the first metric is X, the second
    is Y, and an optional first dimension supplies point grouping/labels. Null
    or non-numeric X/Y pairs are omitted rather than silently converted to zero.
    """

    error = scatter_configuration_error(metric_keys)
    if error:
        return {"valid": False, "error": error, "points": []}

    x_key, y_key = metric_keys[:2]
    by_key = {
        str(column.get("key") or column.get("name") or column.get("field") or ""): column
        for column in columns
    }
    for key in (x_key, y_key):
        column = by_key.get(key)
        if column is None:
            return {"valid": False, "error": SCATTER_CONFIGURATION_ERROR, "points": []}
        data_type = str(column.get("data_type") or column.get("dataType") or "").lower()
        if data_type and data_type not in _NUMERIC_TYPES:
            return {"valid": False, "error": SCATTER_CONFIGURATION_ERROR, "points": []}

    group_key = dimension_keys[0] if dimension_keys else None
    points: list[dict[str, object]] = []
    for row in rows:
        x_value = _number(row.get(x_key))
        y_value = _number(row.get(y_key))
        if x_value is None or y_value is None:
            continue
        points.append(
            {
                "x": x_value,
                "y": y_value,
                "group": row.get(group_key) if group_key else None,
            }
        )

    return {
        "valid": True,
        "error": None if points else SCATTER_NO_DATA,
        "x_field": x_key,
        "y_field": y_key,
        "group_field": group_key,
        "points": points,
    }


def pivot_contract(
    dimension_keys: Sequence[str],
    metric_keys: Sequence[str],
    columns: Sequence[Mapping[str, object]],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build VIP's canonical Pivot matrix from an ordered semantic query.

    With two or more dimensions, the final dimension is the column axis and
    preceding dimensions form the row axis. A single dimension remains a
    backwards-compatible row-only Pivot. Every metric becomes a value column
    for each distinct column-axis tuple. Ordering is stable and follows query
    result order; absent combinations are represented as null cells.
    """

    row_fields = list(dimension_keys[:-1] if len(dimension_keys) > 1 else dimension_keys)
    column_fields = list(dimension_keys[-1:] if len(dimension_keys) > 1 else [])
    value_fields = list(metric_keys)
    labels = {
        str(column.get("key") or column.get("name") or column.get("field") or ""): str(
            column.get("label")
            or column.get("key")
            or column.get("name")
            or column.get("field")
            or ""
        )
        for column in columns
    }

    row_tuples = _stable_tuples(rows, row_fields)
    column_tuples = _stable_tuples(rows, column_fields) if column_fields else [tuple()]
    values: dict[tuple[tuple[object, ...], tuple[object, ...]], Mapping[str, object]] = {}
    for row in rows:
        row_tuple = tuple(row.get(key) for key in row_fields)
        column_tuple = tuple(row.get(key) for key in column_fields)
        values[(row_tuple, column_tuple)] = row

    headers: list[dict[str, object]] = []
    for column_tuple in column_tuples:
        for metric in value_fields:
            parts = [str(value) if value is not None else "—" for value in column_tuple]
            if len(value_fields) > 1 or not parts:
                parts.append(labels.get(metric, metric))
            headers.append(
                {
                    "column_values": list(column_tuple),
                    "metric": metric,
                    "label": " · ".join(parts),
                }
            )

    matrix_rows: list[dict[str, object]] = []
    for row_tuple in row_tuples:
        cells: list[object] = []
        for column_tuple in column_tuples:
            source = values.get((row_tuple, column_tuple), {})
            cells.extend(source.get(metric) for metric in value_fields)
        matrix_rows.append({"row_values": list(row_tuple), "cells": cells})

    return {
        "row_fields": row_fields,
        "column_fields": column_fields,
        "value_fields": value_fields,
        "row_headers": [{"key": key, "label": labels.get(key, key)} for key in row_fields],
        "column_headers": headers,
        "rows": matrix_rows,
    }


def flatten_pivot(
    contract: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Project the canonical matrix into renderer columns and rows."""

    row_headers = cast(list[dict[str, object]], contract.get("row_headers", []))
    column_headers = cast(list[dict[str, object]], contract.get("column_headers", []))
    matrix_rows = cast(list[dict[str, object]], contract.get("rows", []))
    columns: list[dict[str, object]] = [
        {"key": str(header["key"]), "label": str(header["label"]), "role": "dimension"}
        for header in row_headers
    ]
    columns.extend(
        {
            "key": f"__pivot_value_{index}",
            "label": str(header.get("label") or header.get("metric") or "Value"),
            "role": "metric",
        }
        for index, header in enumerate(column_headers)
    )
    rows: list[dict[str, object]] = []
    for item in matrix_rows:
        row = {
            str(header["key"]): value
            for header, value in zip(
                row_headers, cast(list[object], item.get("row_values", [])), strict=False
            )
        }
        row.update(
            {
                f"__pivot_value_{index}": value
                for index, value in enumerate(cast(list[object], item.get("cells", [])))
            }
        )
        rows.append(row)
    return columns, rows


def _stable_tuples(
    rows: Sequence[Mapping[str, object]], fields: Sequence[str]
) -> list[tuple[object, ...]]:
    seen: set[tuple[object, ...]] = set()
    values: list[tuple[object, ...]] = []
    for row in rows:
        value = tuple(row.get(key) for key in fields)
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None
