"""VIP-BUG-005: verify the effective security-header contract on real responses.

Asserts behavior (actual response headers), not just that config strings exist.
HSTS must be absent in local environments (never asserted over local HTTP).
"""

from __future__ import annotations

from starlette.testclient import TestClient

from vip_api.core.config import Settings
from vip_api.main import create_application


def _client(settings: Settings) -> TestClient:
    return TestClient(create_application(settings))


def test_security_headers_present_on_api_response(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp


def test_hsts_absent_outside_production(settings: Settings) -> None:
    # settings fixture is APP_ENV=test/development -> HSTS must NOT be emitted.
    with _client(settings) as client:
        response = client.get("/health")
    assert "strict-transport-security" not in {k.lower() for k in response.headers}


def test_hsts_present_in_demo() -> None:
    settings = Settings(
        APP_ENV="demo",
        DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
        REDIS_URL="redis://cache/0",
        CORS_ALLOWED_ORIGINS="https://veltrix-one-demo.onrender.com",
        TRUSTED_HOSTS="testserver",
        CSRF_TRUSTED_ORIGINS="https://veltrix-one-demo.onrender.com",
        AUTH_COOKIE_SECURE=True,
        METRICS_ENABLED=False,
        CONNECTION_ENCRYPTION_KEY="connection-key",
        DASHBOARD_DOWNLOAD_SIGNING_KEY="dashboard-key",
        PIPELINE_DOWNLOAD_SIGNING_KEY="pipeline-key",
        FILE_DOWNLOAD_SIGNING_KEY="file-key",
    )
    with _client(settings) as client:
        response = client.get("/health")
    assert response.headers["strict-transport-security"] == (
        "max-age=63072000; includeSubDomains; preload"
    )


def test_docs_paths_exempt_from_strict_csp(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.get("/openapi.json")
    # Docs/OpenAPI keep the static hardening headers but not the strict API CSP.
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in {k.lower() for k in response.headers}
