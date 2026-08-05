"""Build the deterministic production API operation certification map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PUBLIC_PATHS = {
    "/health",
    "/api/v1/version",
    "/auth/login",
    "/auth/password-reset/request",
    "/auth/password-reset/confirm",
}
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


def _probes(method: str, path: str, scope: str) -> list[str]:
    """Return only probes the operation-wide integration sweep actually executes."""
    probes = ["openapi_contract"]
    if scope == "public":
        probes.append("public_probe")
    else:
        probes.extend(["unauthenticated_probe", "authenticated_probe"])
    if "{" in path:
        probes.append("invalid_uuid_probe")
    if method in {"post", "put", "patch"}:
        probes.append("empty_payload_probe")
    if scope == "workspace":
        probes.extend(["restricted_role_probe", "cross_tenant_header_probe"])
    return probes


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
            probes = _probes(method, path, scope)
            result = execution.get(operation["operationId"]) if execution is not None else None
            raw_dimensions = result.get("executed_dimensions", []) if result is not None else []
            if not isinstance(raw_dimensions, list) or not all(
                isinstance(item, str) for item in raw_dimensions
            ):
                raise ValueError(
                    f"Execution evidence for {operation['operationId']} has invalid dimensions"
                )
            executed_dimensions = raw_dimensions
            unsupported = sorted(
                set(executed_dimensions)
                - set(probes)
                - {
                    "authenticated_success",
                    "response_schema_validated",
                    "forbidden_observed",
                    "cross_tenant_isolated",
                    "safe_error_envelope",
                    "secret_non_disclosure_observed",
                }
            )
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
                    "claimed_dimensions": probes,
                    "executed_dimensions": executed_dimensions,
                    "test_evidence": [
                        {
                            "test_id": ANONYMOUS_SWEEP_TEST_ID,
                            "dimensions": [
                                item
                                for item in probes
                                if item
                                in {
                                    "openapi_contract",
                                    "public_probe",
                                    "unauthenticated_probe",
                                    "invalid_uuid_probe",
                                    "empty_payload_probe",
                                }
                            ],
                        },
                        {
                            "test_id": CONTRACT_SWEEP_TEST_ID,
                            "dimensions": [
                                item
                                for item in (executed_dimensions if result is not None else probes)
                                if item
                                not in {
                                    "openapi_contract",
                                    "public_probe",
                                    "unauthenticated_probe",
                                    "invalid_uuid_probe",
                                    "empty_payload_probe",
                                }
                            ],
                        },
                    ],
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
    return {
        "schema_version": 1,
        "path_count": len(document["paths"]),
        "operation_count": len(operations),
        "classified_count": len(operations),
        "test_mapped_count": len(operations),
        "executed_count": executed_count,
        "passed_count": passed_count,
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
