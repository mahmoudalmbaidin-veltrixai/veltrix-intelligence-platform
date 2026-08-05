"""Build the deterministic production API operation certification map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PUBLIC_PATHS = {
    "/health",
    "/readiness",
    "/version",
    "/auth/login",
    "/auth/password/forgot",
    "/auth/password/reset/validate",
    "/auth/password/reset",
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


def _dimensions(method: str, path: str, scope: str) -> list[str]:
    dimensions = ["declared_response_schema", "error_envelope", "status_code"]
    if "{" in path:
        dimensions.extend(["invalid_uuid", "missing_resource"])
    if method in {"post", "put", "patch"}:
        dimensions.extend(
            [
                "invalid_payload",
                "extra_field",
                "wrong_field_type",
                "empty_payload",
                "payload_boundary",
            ]
        )
    if method == "get" and "{" not in path:
        dimensions.extend(["pagination", "filtering", "sorting"])
    if scope != "public":
        dimensions.extend(["unauthenticated", "suspended_user"])
    if scope == "platform":
        dimensions.extend(["forbidden", "role_ceiling"])
    if scope == "workspace":
        dimensions.extend(
            [
                "forbidden",
                "cross_tenant",
                "tenant_header_manipulation",
                "resource_uuid_enumeration",
                "role_ceiling",
                "acl_denial",
                "explicit_deny",
                "expired_access",
            ]
        )
    if "export" in path or "download" in path:
        dimensions.extend(["secret_non_disclosure", "signed_url", "export_authorization"])
    return list(dict.fromkeys(dimensions))


def build_coverage(document: dict[str, Any]) -> dict[str, object]:
    operations: list[dict[str, object]] = []
    for path, path_item in sorted(document["paths"].items()):
        for method in sorted(HTTP_METHODS & path_item.keys()):
            operation = path_item[method]
            tag = str(operation["tags"][0])
            scope = _scope(tag, path)
            tests = ["integration/test_production_api_contract_sweep.py"]
            tests.extend(TAG_TESTS[tag])
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
                    "security_dimensions": _dimensions(method, path, scope),
                    "test_ids": sorted(set(tests)),
                    "status": "classified",
                }
            )
    return {
        "schema_version": 1,
        "path_count": len(document["paths"]),
        "operation_count": len(operations),
        "classified_count": len(operations),
        "operations": operations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    from vip_api.main import app

    result = build_coverage(app.openapi())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"classified={result['classified_count']}/{result['operation_count']}")


if __name__ == "__main__":
    main()
