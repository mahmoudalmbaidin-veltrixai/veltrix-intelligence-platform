"""Application factory and public endpoint unit tests."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Query
from pydantic import SecretStr
from starlette.testclient import TestClient

from vip_api.core.config import Settings
from vip_api.main import create_application


def test_application_factory_creates_app(settings: Settings) -> None:
    app = create_application(settings)
    assert app.title == "VIP API"
    assert app.version == "0.1.0"


def test_health_is_live_without_starting_external_resources(settings: Settings) -> None:
    # Omitting the context manager deliberately avoids lifespan resource initialization.
    local_client = TestClient(create_application(settings), raise_server_exceptions=False)
    response = local_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "vip-api", "version": "0.1.0"}


def test_metrics_are_prometheus_compatible_and_can_require_bearer_auth(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def platform_metrics(*_args: object) -> str:
        return "vip_workers_active 1\n"

    async def healthy(*_args: object) -> bool:
        return True

    monkeypatch.setattr(
        "vip_api.api.routes.operational._platform_metrics",
        platform_metrics,
    )
    monkeypatch.setattr("vip_api.api.routes.operational.check_database", healthy)
    monkeypatch.setattr("vip_api.api.routes.operational.check_redis", healthy)
    secured = settings.model_copy(update={"METRICS_BEARER_TOKEN": SecretStr("metrics-test-token")})
    with TestClient(create_application(secured), raise_server_exceptions=False) as local_client:
        denied = local_client.get("/metrics")
        response = local_client.get(
            "/metrics", headers={"Authorization": "Bearer metrics-test-token"}
        )

    assert denied.status_code == 401
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "vip_http_requests_total" in response.text
    assert "vip_http_active_requests" in response.text
    assert "vip_authentication_failures_total" in response.text
    assert "vip_database_healthy" in response.text
    assert "vip_sse_active_connections" in response.text
    assert "vip_workers_active 1" in response.text


def test_version_schema(client: TestClient) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json() == {
        "name": "VIP API",
        "version": "0.1.0",
        "environment": "test",
        "commit_sha": None,
        "build_timestamp": None,
    }


def test_correlation_id_is_generated(client: TestClient) -> None:
    response = client.get("/health")
    assert UUID(response.headers["X-Correlation-ID"])
    assert UUID(response.headers["X-Request-ID"])


def test_valid_correlation_id_is_echoed(client: TestClient) -> None:
    correlation_id = "frontend-request_2026.07.21:abc"
    response = client.get("/health", headers={"X-Correlation-ID": correlation_id})
    assert response.headers["X-Correlation-ID"] == correlation_id


def test_invalid_correlation_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "invalid id\nsecret"})
    assert UUID(response.headers["X-Correlation-ID"])


def test_invalid_and_duplicate_tenant_headers_use_standard_error(client: TestClient) -> None:
    invalid = client.get("/health", headers={"X-Organization-ID": "not-a-uuid"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_TENANT_CONTEXT"
    assert invalid.json()["error"]["correlation_id"] == invalid.headers["X-Correlation-ID"]

    duplicate = client.get(
        "/health",
        headers=[("X-Workspace-ID", str(UUID(int=1))), ("X-Workspace-ID", str(UUID(int=2)))],
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "INVALID_TENANT_CONTEXT"


def test_cors_preflight_allows_frontend_context_and_csrf_headers(settings: Settings) -> None:
    cors_settings = settings.model_copy(update={"CORS_ALLOW_CREDENTIALS": True})
    with TestClient(create_application(cors_settings), raise_server_exceptions=False) as client:
        response = client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost:3009",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "content-type,x-correlation-id,x-csrf-token,x-locale,x-timezone,"
                    "x-organization-id,x-workspace-id"
                ),
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3009"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unknown_route_uses_standard_error(client: TestClient) -> None:
    response = client.get("/does-not-exist", headers={"X-Correlation-ID": "known-id"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "The requested resource was not found.",
            "correlation_id": "known-id",
        }
    }


def test_validation_error_uses_standard_error(settings: Settings) -> None:
    app = create_application(settings)

    @app.get("/test-validation")
    async def validation(value: Annotated[int, Query(gt=0)]) -> dict[str, int]:
        return {"value": value}

    with TestClient(app, raise_server_exceptions=False) as local_client:
        response = local_client.get("/test-validation?value=invalid")

    assert response.status_code == 422
    payload = response.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["details"][0]["field"] == "query.value"
    assert payload["correlation_id"] == response.headers["X-Correlation-ID"]


def test_unexpected_exception_is_safe(settings: Settings) -> None:
    app = create_application(settings)

    @app.get("/test-exception")
    async def broken() -> None:
        raise RuntimeError("sensitive stack marker")

    with TestClient(app, raise_server_exceptions=False) as local_client:
        response = local_client.get("/test-exception")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "sensitive stack marker" not in response.text
    assert "traceback" not in response.text.lower()
