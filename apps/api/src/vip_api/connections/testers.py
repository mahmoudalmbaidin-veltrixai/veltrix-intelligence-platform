"""Restricted, injectable connection-test implementations."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.parse import urljoin

import asyncpg  # type: ignore[import-untyped]
import httpx

from vip_api.connections.network import UnsafeDestinationError, validate_host, validate_url
from vip_api.core.config import Settings


@dataclass(frozen=True, slots=True)
class TesterResult:
    __test__ = False

    success: bool
    health_status: str
    latency_ms: int
    error_code: str | None = None


class ConnectionTester(Protocol):
    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult: ...


class PostgreSQLTester:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        host = str(configuration["host"])
        port = cast(int, configuration["port"])
        await validate_host(host, port, self.settings)
        started = time.perf_counter()
        connection: asyncpg.Connection[asyncpg.Record] | None = None
        try:
            connection = await asyncio.wait_for(
                asyncpg.connect(
                    host=host,
                    port=port,
                    database=str(configuration["database"]),
                    user=str(configuration["username"]),
                    password=credentials["password"],
                    ssl=str(configuration["ssl_mode"]),
                    command_timeout=self.settings.CONNECTION_TEST_TIMEOUT_SECONDS,
                    server_settings={"application_name": "vip-connection-test"},
                ),
                timeout=self.settings.CONNECTION_TEST_TIMEOUT_SECONDS,
            )
            assert connection is not None
            await connection.fetchval("SELECT 1")
            return TesterResult(True, "healthy", _latency(started))
        except TimeoutError:
            return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TIMEOUT")
        except asyncpg.InvalidPasswordError:
            return TesterResult(
                False, "unhealthy", _latency(started), "CONNECTION_AUTHENTICATION_FAILED"
            )
        except (OSError, asyncpg.PostgresError):
            return TesterResult(
                False, "unhealthy", _latency(started), "CONNECTION_HOST_UNREACHABLE"
            )
        finally:
            if connection is not None:
                await connection.close(timeout=2)


class RestApiTester:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        base_url = str(configuration["base_url"])
        url = urljoin(base_url.rstrip("/") + "/", str(configuration["health_path"]).lstrip("/"))
        headers: dict[str, str] = {"User-Agent": "VIP-Connection-Test/1.0"}
        auth_type = str(configuration["auth_type"])
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {credentials['token']}"
        elif auth_type == "api_key":
            headers[str(configuration["api_key_header"])] = credentials["api_key"]
        started = time.perf_counter()
        timeout = min(
            cast(int, configuration["timeout_seconds"]),
            self.settings.CONNECTION_TEST_TIMEOUT_SECONDS,
        )
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                verify=True,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                for redirect_count in range(self.settings.CONNECTION_TEST_MAX_REDIRECTS + 1):
                    await validate_url(url, self.settings)
                    response = await client.head(url, headers=headers)
                    if response.is_redirect:
                        if redirect_count >= self.settings.CONNECTION_TEST_MAX_REDIRECTS:
                            return TesterResult(
                                False, "unhealthy", _latency(started), "CONNECTION_REDIRECT_BLOCKED"
                            )
                        location = response.headers.get("location")
                        if not location:
                            return TesterResult(
                                False, "unhealthy", _latency(started), "CONNECTION_TEST_FAILED"
                            )
                        url = urljoin(url, location)
                        continue
                    if response.status_code in {401, 403}:
                        return TesterResult(
                            False,
                            "unhealthy",
                            _latency(started),
                            "CONNECTION_AUTHENTICATION_FAILED",
                        )
                    if response.status_code >= 500:
                        return TesterResult(
                            False, "degraded", _latency(started), "CONNECTION_REMOTE_UNAVAILABLE"
                        )
                    return TesterResult(True, "healthy", _latency(started))
        except UnsafeDestinationError:
            raise
        except httpx.TimeoutException:
            return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TIMEOUT")
        except httpx.TransportError:
            return TesterResult(
                False, "unhealthy", _latency(started), "CONNECTION_HOST_UNREACHABLE"
            )
        return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TEST_FAILED")


class ConnectionTesterRegistry:
    def __init__(self, settings: Settings) -> None:
        self._testers: dict[str, ConnectionTester] = {
            "postgresql": PostgreSQLTester(settings),
            "rest_api": RestApiTester(settings),
        }

    def get(self, type_key: str) -> ConnectionTester:
        tester = self._testers.get(type_key)
        if tester is None:
            raise LookupError("Connection tester is unavailable")
        return tester

    def replace(self, type_key: str, tester: ConnectionTester) -> None:
        self._testers[type_key] = tester


def _latency(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
