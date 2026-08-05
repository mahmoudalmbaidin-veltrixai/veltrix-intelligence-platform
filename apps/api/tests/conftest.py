"""Shared settings and application fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv(
        "TEST_DATABASE_URL",
        # The local Docker test service does not offer TLS. asyncpg defaults to
        # ssl=prefer, which first attempts TLS and then reconnects in plaintext;
        # under Windows/Docker checkpoint load that double handshake can consume
        # the entire strict two-second connect budget. Pin loopback IPv4 and the
        # known local transport explicitly. Production URLs keep their own TLS
        # policy and are never rewritten here.
        "postgresql+asyncpg://vip:vip_local_dev_only@127.0.0.1:5432/vip_test?ssl=disable",
    ),
)
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
        # Hermetic host allow-list. Without this, running the suite inside the
        # live API container (which exports TRUSTED_HOSTS for the running server)
        # would enable TrustedHostMiddleware and reject the TestClient "testserver"
        # host with a 400, masking the real 422/readiness assertions. Matches the
        # certified CI default (TRUSTED_HOSTS unset -> ["*"], middleware disabled).
        TRUSTED_HOSTS=["*"],
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
