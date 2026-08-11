"""Deterministic OpenAPI operation manifest for API governance (VIP-BUG-008).

CI compares the live OpenAPI document to a reviewed, committed expected
manifest. Additions, removals, operationId changes, and authentication-level
changes fail until the reviewed manifest is intentionally updated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vip_api.api.operation_coverage import HTTP_METHODS, _scope

MANIFEST_SCHEMA_VERSION = 1
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "contracts" / "api_operation_manifest.json"
)


def normalize_operations(document: dict[str, Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for path, path_item in sorted(document.get("paths", {}).items()):
        for method in sorted(HTTP_METHODS & set(path_item.keys())):
            operation = path_item[method]
            tag = str(operation["tags"][0])
            normalized.append(
                {
                    "operation_id": str(operation["operationId"]),
                    "method": method.upper(),
                    "path": path,
                    "authentication_level": _scope(tag, path),
                    "tag": tag,
                }
            )
    return sorted(
        normalized,
        key=lambda row: (row["path"], row["method"], row["operation_id"]),
    )


def build_manifest(document: dict[str, Any]) -> dict[str, Any]:
    operations = normalize_operations(document)
    by_level: dict[str, int] = {}
    for item in operations:
        level = item["authentication_level"]
        by_level[level] = by_level.get(level, 0) + 1
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "operation_count": len(operations),
        "path_count": len(document.get("paths", {})),
        "authentication_levels": dict(sorted(by_level.items())),
        "operations": operations,
    }


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(document: dict[str, Any], path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    manifest = build_manifest(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def compare_manifests(
    expected: dict[str, Any], actual: dict[str, Any]
) -> dict[str, list[dict[str, str]]]:
    expected_ops = {(item["method"], item["path"]): item for item in expected.get("operations", [])}
    actual_ops = {(item["method"], item["path"]): item for item in actual.get("operations", [])}
    added = [actual_ops[key] for key in sorted(set(actual_ops) - set(expected_ops))]
    removed = [expected_ops[key] for key in sorted(set(expected_ops) - set(actual_ops))]
    changed_ids: list[dict[str, str]] = []
    changed_auth: list[dict[str, str]] = []
    for key in sorted(set(expected_ops) & set(actual_ops)):
        before = expected_ops[key]
        after = actual_ops[key]
        if before["operation_id"] != after["operation_id"]:
            changed_ids.append(
                {
                    "method": after["method"],
                    "path": after["path"],
                    "from": before["operation_id"],
                    "to": after["operation_id"],
                }
            )
        if before["authentication_level"] != after["authentication_level"]:
            changed_auth.append(
                {
                    "method": after["method"],
                    "path": after["path"],
                    "operation_id": after["operation_id"],
                    "from": before["authentication_level"],
                    "to": after["authentication_level"],
                }
            )
    return {
        "added": added,
        "removed": removed,
        "changed_operation_ids": changed_ids,
        "changed_authentication_levels": changed_auth,
    }


def assert_manifest_matches(
    document: dict[str, Any], path: Path = DEFAULT_MANIFEST_PATH
) -> dict[str, Any]:
    expected = load_manifest(path)
    actual = build_manifest(document)
    diff = compare_manifests(expected, actual)
    problems: list[str] = []
    if diff["added"]:
        problems.append(
            "added operations: "
            + ", ".join(f"{item['method']} {item['path']}" for item in diff["added"])
        )
    if diff["removed"]:
        problems.append(
            "removed operations: "
            + ", ".join(f"{item['method']} {item['path']}" for item in diff["removed"])
        )
    if diff["changed_operation_ids"]:
        problems.append(
            "changed operation ids: "
            + ", ".join(
                f"{item['method']} {item['path']} ({item['from']} -> {item['to']})"
                for item in diff["changed_operation_ids"]
            )
        )
    if diff["changed_authentication_levels"]:
        problems.append(
            "changed authentication levels: "
            + ", ".join(
                f"{item['method']} {item['path']} ({item['from']} -> {item['to']})"
                for item in diff["changed_authentication_levels"]
            )
        )
    if problems:
        raise AssertionError(
            "OpenAPI operation manifest drift detected. Review and update "
            f"{path.as_posix()} after intentional API changes.\n" + "\n".join(problems)
        )
    return actual
