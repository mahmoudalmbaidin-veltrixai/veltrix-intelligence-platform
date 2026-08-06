"""Build the deterministic production API operation certification map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
SUPPORTED_DIMENSIONS = frozenset(
    {
        "openapi_contract",
        "public_probe",
        "unauthenticated_probe",
        "authenticated_probe",
        "authenticated_success",
        "response_schema_validated",
        "invalid_uuid_probe",
        "invalid_payload_probe",
        "empty_payload_probe",
        "payload_lower_bound",
        "payload_upper_bound",
        "restricted_role_probe",
        "forbidden_observed",
        "direct_acl_allow",
        "direct_acl_deny",
        "group_acl_allow",
        "group_acl_deny",
        "explicit_deny",
        "expired_access",
        "suspended_user_probe",
        "suspended_user_rejected",
        "cross_tenant_header_probe",
        "cross_tenant_resource_probe",
        "cross_tenant_isolated",
        "ownership_allow",
        "ownership_denial",
        "pagination_boundary",
        "filtering_validation",
        "sorting_validation",
        "secret_non_disclosure",
        "signed_url_validation",
        "rate_limit_behavior",
        "idempotency",
        "safe_error_envelope",
    }
)
PUBLIC_PATHS = {
    "/health",
    "/ready",
    "/api/v1/version",
    "/auth/login",
    "/auth/password-reset/request",
    "/auth/password-reset/confirm",
}
SUSPENDED_EXEMPT_PATHS = {"/auth/logout"}
TAG_TESTS = {
    "authentication": [
        "integration/test_authentication.py",
        "integration/test_password_recovery.py",
    ],
    "tenancy": ["integration/test_tenancy.py"],
    "governance": ["integration/test_governance.py", "integration/test_resource_permissions.py"],
    "roles": ["integration/test_custom_roles.py", "integration/test_role_assignment_security.py"],
    "access": [
        "integration/test_resource_guard_enforcement.py",
        "integration/test_resource_authorization_domains.py",
    ],
    "platform-admin": ["integration/test_platform_infrastructure.py"],
    "platform-catalogs": ["integration/test_platform_infrastructure.py"],
    "operations": ["integration/test_platform_infrastructure.py"],
    "connections": ["integration/test_connections.py"],
    "datasets": ["integration/test_dataset_certification.py"],
    "semantic-models": [
        "integration/test_semantic_republish.py",
        "integration/test_semantic_audit.py",
    ],
    "semantic-query": ["integration/test_semantic_republish.py"],
    "pipelines": [
        "integration/test_pipeline_persistence.py",
        "integration/test_pipeline_action_matrix.py",
        "integration/test_pipeline_schema_validation.py",
    ],
    "pipeline artifacts": ["integration/test_pipeline_persistence.py"],
    "dashboards": [
        "integration/test_dashboard_persistence.py",
        "integration/test_dashboard_lifecycle_integrity.py",
    ],
    "dashboard exports and deliveries": [
        "unit/test_dashboard_delivery.py",
        "integration/test_dashboard_delivery_scheduler.py",
    ],
    "jobs": ["integration/test_services.py"],
    "files": ["integration/test_services.py"],
    "events": ["integration/test_services.py"],
    "notifications": ["integration/test_services.py"],
    "glossary": ["integration/test_services.py"],
    "home": ["integration/test_services.py"],
    "version": ["integration/test_services.py"],
}

CONTRACT_SWEEP_TEST_ID = (
    "integration/test_production_api_contract_sweep.py::"
    "test_authenticated_personas_exercise_every_protected_operation"
)
ANONYMOUS_SWEEP_TEST_ID = (
    "integration/test_production_api_contract_sweep.py::"
    "test_every_production_operation_has_a_resolvable_contract_and_fails_closed"
)


def _action(method: str, path: str) -> str:
    if method == "get":
        return "read"
    if method == "post" and any(
        segment in path for segment in ("/publish", "/run", "/cancel", "/restore", "/download")
    ):
        return "action"
    return {"post": "create", "put": "update", "patch": "update", "delete": "delete"}[method]


def _scope(tag: str, path: str) -> str:
    if path in PUBLIC_PATHS:
        return "public"
    if tag in {"platform-admin", "platform-catalogs", "operations"} or path.startswith(
        "/api/v1/platform"
    ):
        return "platform"
    if "workspace" in path or tag not in {"authentication", "version"}:
        return "workspace"
    return "authenticated"


def _bounded_query_dimensions(operation: dict[str, Any]) -> set[str]:
    dimensions: set[str] = set()
    for parameter in operation.get("parameters", []):
        if parameter.get("in") != "query":
            continue
        schema = parameter.get("schema", {})
        if not isinstance(schema, dict):
            continue
        name = str(parameter.get("name", ""))
        parameter_dimensions: set[str] = set()
        if any(key in schema for key in ("minimum", "exclusiveMinimum", "minLength")):
            parameter_dimensions.add("payload_lower_bound")
        if any(key in schema for key in ("maximum", "exclusiveMaximum", "maxLength")):
            parameter_dimensions.add("payload_upper_bound")
        dimensions |= parameter_dimensions
        if parameter_dimensions and name in {
            "page",
            "page_size",
            "limit",
            "offset",
            "per_page",
        }:
            dimensions.add("pagination_boundary")
        if "maxLength" in schema and name in {"q", "query", "search", "filter", "status"}:
            dimensions.add("filtering_validation")
    return dimensions


def _acl_dimensions(operation_id: str) -> set[str]:
    if operation_id.endswith("resources__resource_type___resource_id__access_post"):
        return {
            "direct_acl_allow",
            "direct_acl_deny",
            "group_acl_allow",
            "group_acl_deny",
            "explicit_deny",
        }
    if operation_id.startswith(("list_access_", "effective_access_", "simulate_access_")):
        return {
            "direct_acl_allow",
            "direct_acl_deny",
            "group_acl_allow",
            "group_acl_deny",
            "explicit_deny",
        }
    if operation_id.startswith("revoke_access_"):
        return {"direct_acl_allow"}
    return set()


def _has_uuid_path_parameter(path: str, operation: dict[str, Any]) -> bool:
    names = {part[1:-1] for part in path.split("/") if part.startswith("{")}
    for parameter in operation.get("parameters", []):
        name = str(parameter.get("name", ""))
        schema = parameter.get("schema", {})
        if (
            parameter.get("in") == "path"
            and name in names
            and isinstance(schema, dict)
            and (schema.get("format") == "uuid" or name.endswith("_id"))
        ):
            return True
    return any(name.endswith("_id") for name in names)


def _probes(method: str, path: str, scope: str, operation: dict[str, Any]) -> list[str]:
    """Apply explicit, reviewable rules for operation-level evidence dimensions."""
    probes = ["openapi_contract"]
    if scope == "public":
        probes.append("public_probe")
    else:
        probes.extend(["unauthenticated_probe", "authenticated_probe"])
        if path not in SUSPENDED_EXEMPT_PATHS:
            probes.extend(["suspended_user_probe", "suspended_user_rejected"])
    if _has_uuid_path_parameter(path, operation):
        probes.append("invalid_uuid_probe")
    if scope == "workspace":
        probes.extend(
            ["restricted_role_probe", "cross_tenant_header_probe", "cross_tenant_isolated"]
        )
    if "{" not in path:
        probes.extend(sorted(_bounded_query_dimensions(operation)))
    probes.extend(sorted(_acl_dimensions(str(operation["operationId"]))))
    if method == "get" and set(part for part in path.split("/") if part.startswith("{")) == {
        "{dashboard_id}"
    }:
        probes.extend(["cross_tenant_resource_probe", "cross_tenant_isolated"])
    return list(dict.fromkeys(probes))


def _validate_evidence_test_id(test_id: str) -> None:
    relative, separator, function_name = test_id.partition("::")
    if not separator or not function_name:
        raise ValueError(f"Executable evidence must use file::test_function: {test_id}")
    tests_root = Path(__file__).resolve().parents[3] / "tests"
    source = tests_root.joinpath(relative)
    if not source.is_file():
        raise ValueError(f"Executable evidence file does not exist: {test_id}")
    marker = f"def {function_name}("
    async_marker = f"async def {function_name}("
    text = source.read_text(encoding="utf-8")
    if marker not in text and async_marker not in text:
        raise ValueError(f"Executable evidence test does not exist: {test_id}")


def build_coverage(
    document: dict[str, Any], execution: dict[str, dict[str, object]] | None = None
) -> dict[str, object]:
    _validate_evidence_test_id(CONTRACT_SWEEP_TEST_ID)
    _validate_evidence_test_id(ANONYMOUS_SWEEP_TEST_ID)
    operations: list[dict[str, object]] = []
    for path, path_item in sorted(document["paths"].items()):
        for method in sorted(HTTP_METHODS & path_item.keys()):
            operation = path_item[method]
            tag = str(operation["tags"][0])
            scope = _scope(tag, path)
            probes = _probes(method, path, scope, operation)
            result = execution.get(operation["operationId"]) if execution is not None else None
            raw_dimensions = result.get("executed_dimensions", []) if result is not None else []
            if not isinstance(raw_dimensions, list) or not all(
                isinstance(item, str) for item in raw_dimensions
            ):
                raise ValueError(
                    f"Execution evidence for {operation['operationId']} has invalid dimensions"
                )
            executed_dimensions = raw_dimensions
            applicable_dimensions = list(dict.fromkeys([*probes, *executed_dimensions]))
            unsupported = sorted(set(executed_dimensions) - SUPPORTED_DIMENSIONS)
            if unsupported:
                raise ValueError(
                    "Execution evidence for "
                    f"{operation['operationId']} has unsupported dimensions: "
                    f"{unsupported}"
                )
            if result is not None and not set(probes) <= set(executed_dimensions):
                missing = sorted(set(probes) - set(executed_dimensions))
                raise ValueError(
                    f"Execution evidence for {operation['operationId']} "
                    f"is missing probes: {missing}"
                )
            raw_evidence = result.get("dimension_evidence", {}) if result is not None else {}
            if not isinstance(raw_evidence, dict):
                raise ValueError(
                    f"Execution evidence for {operation['operationId']} has invalid evidence"
                )
            if result is not None and set(raw_evidence) != set(executed_dimensions):
                missing_evidence = sorted(set(executed_dimensions) - set(raw_evidence))
                extra_evidence = sorted(set(raw_evidence) - set(executed_dimensions))
                raise ValueError(
                    f"Execution evidence for {operation['operationId']} does not match claims; "
                    f"missing={missing_evidence}, extra={extra_evidence}"
                )
            for dimension, item in raw_evidence.items():
                if not isinstance(item, dict):
                    raise ValueError(
                        f"Evidence for {operation['operationId']}:{dimension} must be an object"
                    )
                test_id = item.get("test_id")
                if not isinstance(test_id, str):
                    raise ValueError(
                        f"Evidence for {operation['operationId']}:{dimension} lacks a test ID"
                    )
                _validate_evidence_test_id(test_id)
                if item.get("result") != "pass" or "observed_http_status" not in item:
                    raise ValueError(
                        f"Evidence for {operation['operationId']}:{dimension} is not passing "
                        "observed evidence"
                    )
            personas = {
                "public": ["anonymous"],
                "authenticated": ["active_user", "suspended_user"],
                "platform": ["platform_admin", "normal_user", "suspended_user"],
                "workspace": [
                    "workspace_admin",
                    "workspace_viewer",
                    "explicit_deny_user",
                    "cross_tenant_user",
                    "suspended_user",
                ],
            }[scope]
            operations.append(
                {
                    "operation_id": operation["operationId"],
                    "method": method.upper(),
                    "path": path,
                    "tag": tag,
                    "authentication_level": scope,
                    "action": _action(method, path),
                    "resource_bound": "{" in path,
                    "personas": personas,
                    "required_dimensions": probes,
                    "applicable_dimensions": applicable_dimensions,
                    "claimed_dimensions": executed_dimensions if result is not None else probes,
                    "executed_dimensions": executed_dimensions,
                    "dimension_status": {
                        dimension: (
                            "passed"
                            if dimension in executed_dimensions
                            else "applicable_not_executed"
                            if dimension in applicable_dimensions
                            else "not_applicable"
                        )
                        for dimension in sorted(SUPPORTED_DIMENSIONS)
                    },
                    "test_evidence": raw_evidence,
                    "dimension_evidence": raw_evidence,
                    "mapped_test_ids": [ANONYMOUS_SWEEP_TEST_ID, CONTRACT_SWEEP_TEST_ID],
                    "related_domain_tests": sorted(set(TAG_TESTS[tag])),
                    "classification_status": "classified",
                    "test_mapping_status": "mapped",
                    "execution_status": "executed" if result is not None else "not_run",
                    "result": str(result.get("result")) if result is not None else "not_run",
                    "observations": result.get("observations", {}) if result is not None else {},
                }
            )
    executed_count = sum(item["execution_status"] == "executed" for item in operations)
    passed_count = sum(item["result"] == "pass" for item in operations)
    if execution is not None and executed_count != len(operations):
        mapped_ids = {str(item["operation_id"]) for item in operations}
        missing = sorted(mapped_ids - set(execution))
        raise ValueError(
            "Execution evidence is incomplete; missing operation IDs: " + ", ".join(missing)
        )
    dimension_counts = {
        dimension: sum(
            dimension in cast(list[str], item["executed_dimensions"]) for item in operations
        )
        for dimension in sorted(SUPPORTED_DIMENSIONS)
    }
    applicable_counts = {
        dimension: sum(
            dimension in cast(list[str], item["applicable_dimensions"]) for item in operations
        )
        for dimension in sorted(SUPPORTED_DIMENSIONS)
    }
    return {
        "schema_version": 2,
        "path_count": len(document["paths"]),
        "operation_count": len(operations),
        "classified_count": len(operations),
        "test_mapped_count": len(operations),
        "executed_count": executed_count,
        "passed_count": passed_count,
        "dimension_counts": dimension_counts,
        "applicable_dimension_counts": applicable_counts,
        "unsupported_claim_count": 0,
        "claimed_dimensions_without_evidence": 0 if execution is not None else None,
        "operations": operations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--execution-report", type=Path)
    args = parser.parse_args()
    from vip_api.main import app

    execution: dict[str, dict[str, object]] | None = None
    if args.execution_report is not None:
        payload = json.loads(args.execution_report.read_text(encoding="utf-8"))
        execution = {str(item["operation_id"]): item for item in payload.get("operations", [])}
    result = build_coverage(app.openapi(), execution)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"classified={result['classified_count']}/{result['operation_count']} "
        f"mapped={result['test_mapped_count']} executed={result['executed_count']} "
        f"passed={result['passed_count']}"
    )
    if result["passed_count"] != result["operation_count"]:
        raise SystemExit("Operation execution evidence contains failed operations")


if __name__ == "__main__":
    main()
