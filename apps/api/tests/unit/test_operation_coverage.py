"""Honesty invariants for generated operation-level certification evidence."""

from __future__ import annotations

from typing import cast

import pytest

from vip_api.api.operation_coverage import build_coverage


def _document() -> dict[str, object]:
    return {
        "paths": {
            "/api/v1/dashboards/{dashboard_id}": {
                "get": {
                    "operationId": "read_dashboard",
                    "tags": ["dashboards"],
                }
            }
        }
    }


def _complete_dimensions() -> list[str]:
    return [
        "openapi_contract",
        "unauthenticated_probe",
        "authenticated_probe",
        "invalid_uuid_probe",
        "restricted_role_probe",
        "cross_tenant_header_probe",
        "cross_tenant_isolated",
        "cross_tenant_resource_probe",
        "suspended_user_probe",
        "suspended_user_rejected",
    ]


def _evidence(dimensions: list[str]) -> dict[str, dict[str, object]]:
    return {
        dimension: {
            "test_id": (
                "unit/test_operation_coverage.py::"
                "test_complete_executable_evidence_is_reported_separately"
            ),
            "persona": "unit-test",
            "resource": "dashboard",
            "observed_http_status": 200,
            "result": "pass",
        }
        for dimension in dimensions
    }


def test_classification_does_not_claim_execution() -> None:
    coverage = build_coverage(_document())
    assert coverage["classified_count"] == 1
    assert coverage["test_mapped_count"] == 1
    assert coverage["executed_count"] == 0
    operation = cast(list[dict[str, object]], coverage["operations"])[0]
    assert operation["execution_status"] == "not_run"
    assert operation["executed_dimensions"] == []


def test_execution_evidence_must_cover_every_claimed_probe() -> None:
    with pytest.raises(ValueError, match="missing probes"):
        build_coverage(
            _document(),
            {
                "read_dashboard": {
                    "operation_id": "read_dashboard",
                    "executed_dimensions": ["openapi_contract"],
                    "dimension_evidence": _evidence(["openapi_contract"]),
                    "result": "pass",
                }
            },
        )


def test_execution_evidence_rejects_unproven_dimensions() -> None:
    with pytest.raises(ValueError, match="unsupported dimensions"):
        build_coverage(
            _document(),
            {
                "read_dashboard": {
                    "operation_id": "read_dashboard",
                    "executed_dimensions": [
                        *_complete_dimensions(),
                        "payload_bounds_verified",
                    ],
                    "dimension_evidence": _evidence(
                        [*_complete_dimensions(), "payload_bounds_verified"]
                    ),
                    "result": "pass",
                }
            },
        )


def test_complete_executable_evidence_is_reported_separately() -> None:
    coverage = build_coverage(
        _document(),
        {
            "read_dashboard": {
                "operation_id": "read_dashboard",
                "executed_dimensions": _complete_dimensions(),
                "dimension_evidence": _evidence(_complete_dimensions()),
                "observations": {
                    "authenticated": 404,
                    "restricted": 403,
                    "cross_tenant": 404,
                },
                "result": "pass",
            }
        },
    )
    assert coverage["classified_count"] == 1
    assert coverage["test_mapped_count"] == 1
    assert coverage["executed_count"] == 1
    assert coverage["passed_count"] == 1
