"""Shared settings and application fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://vip:vip_test@localhost:5432/vip_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ENABLE_DOCS", "false")

from vip_api.core.config import Settings
from vip_api.main import create_application


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="set RUN_INTEGRATION_TESTS=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL=os.environ["DATABASE_URL"],
        REDIS_URL=os.environ["REDIS_URL"],
        ENABLE_DOCS=False,
        # Keep failure tests bounded without making normal Docker/Windows CI
        # connections flaky under concurrent browser and API verification.
        DATABASE_CONNECT_TIMEOUT=2.0,
        REDIS_SOCKET_TIMEOUT=0.25,
        AUTH_LOGIN_RATE_LIMIT_PER_MINUTE=1000,
        CONNECTION_ENCRYPTION_KEY="REREREREREREREREREREREREREREREREREREREREREQ=",
        CONNECTION_ENCRYPTION_KEY_VERSION="test-v1",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_application(settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
