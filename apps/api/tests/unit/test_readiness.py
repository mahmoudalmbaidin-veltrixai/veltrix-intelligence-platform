"""Readiness aggregation unit tests using dependency check fakes."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient


def _patch_checks(monkeypatch: pytest.MonkeyPatch, *, database: bool, redis: bool) -> None:
    async def database_check(*_args: object, **_kwargs: object) -> bool:
        return database

    async def redis_check(*_args: object, **_kwargs: object) -> bool:
        return redis

    monkeypatch.setattr("vip_api.api.routes.operational.check_database", database_check)
    monkeypatch.setattr("vip_api.api.routes.operational.check_redis", redis_check)


def test_ready_when_all_dependencies_are_healthy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, database=True, redis=True)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": {"status": "healthy"}, "redis": {"status": "healthy"}},
    }


def test_not_ready_when_database_is_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, database=False, redis=True)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"]["status"] == "unhealthy"


def test_not_ready_when_redis_is_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, database=True, redis=False)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"]["status"] == "unhealthy"


def test_readiness_failure_does_not_expose_secrets(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, database=False, redis=False)
    response = client.get("/ready")
    body = response.text
    assert "vip_test" not in body
    assert "postgresql" not in body
    assert "redis://" not in body
