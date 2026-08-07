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


class MySQLTester:
    """Real MySQL/MariaDB reachability + authentication test.

    The async driver is imported lazily so a missing optional driver degrades to a
    safe, actionable error instead of crashing API startup.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        try:
            import aiomysql  # type: ignore
        except ImportError:
            return TesterResult(False, "unhealthy", 0, "CONNECTION_DRIVER_UNAVAILABLE")
        host = str(configuration["host"])
        port = cast(int, configuration["port"])
        await validate_host(host, port, self.settings)
        ssl_mode = str(configuration.get("ssl_mode", "require"))
        started = time.perf_counter()
        pool = None
        try:
            pool = await asyncio.wait_for(
                aiomysql.create_pool(
                    host=host,
                    port=port,
                    db=str(configuration["database"]),
                    user=str(configuration["username"]),
                    password=credentials["password"],
                    ssl=ssl_mode != "disable",
                    connect_timeout=self.settings.CONNECTION_TEST_TIMEOUT_SECONDS,
                    minsize=1,
                    maxsize=1,
                    program_name="vip-connection-test",
                ),
                timeout=self.settings.CONNECTION_TEST_TIMEOUT_SECONDS,
            )
            async with pool.acquire() as connection, connection.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()
            return TesterResult(True, "healthy", _latency(started))
        except TimeoutError:
            return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TIMEOUT")
        except Exception as error:
            # Raw driver details are never surfaced; only safe, actionable codes.
            args = getattr(error, "args", ()) or (None,)
            number = args[0]
            if number in {1045, 1044, 1698}:  # access denied / auth failures
                code = "CONNECTION_AUTHENTICATION_FAILED"
            elif number == 1049:  # unknown database
                code = "CONNECTION_METADATA_UNAVAILABLE"
            else:
                code = "CONNECTION_HOST_UNREACHABLE"
            return TesterResult(False, "unhealthy", _latency(started), code)
        finally:
            if pool is not None:
                pool.close()
                await pool.wait_closed()


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


class MSSQLTester:
    """Real Microsoft SQL Server reachability + auth test via the pure-python
    ``pytds`` TDS driver (lazily imported so a missing driver degrades safely)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        try:
            import pytds  # type: ignore
        except ImportError:
            return TesterResult(False, "unhealthy", 0, "CONNECTION_DRIVER_UNAVAILABLE")
        host = str(configuration["host"])
        port = cast(int, configuration["port"])
        await validate_host(host, port, self.settings)
        timeout = self.settings.CONNECTION_TEST_TIMEOUT_SECONDS
        started = time.perf_counter()

        def _ping() -> None:
            conn = pytds.connect(
                server=host,
                port=port,
                database=str(configuration["database"]),
                user=str(configuration["username"]),
                password=credentials["password"],
                login_timeout=timeout,
                timeout=timeout,
                cafile=None,
                validate_host=False,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            finally:
                conn.close()

        try:
            await asyncio.wait_for(asyncio.to_thread(_ping), timeout=timeout + 2)
            return TesterResult(True, "healthy", _latency(started))
        except TimeoutError:
            return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TIMEOUT")
        except pytds.LoginError:
            return TesterResult(
                False, "unhealthy", _latency(started), "CONNECTION_AUTHENTICATION_FAILED"
            )
        except Exception:
            return TesterResult(
                False, "unhealthy", _latency(started), "CONNECTION_HOST_UNREACHABLE"
            )


class SnowflakeTester:
    """Snowflake reachability + auth via the official connector (lazy import)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        try:
            import snowflake.connector  # type: ignore
            from snowflake.connector.errors import DatabaseError, ProgrammingError  # type: ignore
        except ImportError:
            return TesterResult(False, "unhealthy", 0, "CONNECTION_DRIVER_UNAVAILABLE")
        account = str(configuration["account"])
        # Snowflake reaches <account>.snowflakecomputing.com over HTTPS; SSRF-guard it.
        await validate_host(f"{account}.snowflakecomputing.com", 443, self.settings)
        timeout = self.settings.CONNECTION_TEST_TIMEOUT_SECONDS
        started = time.perf_counter()

        def _ping() -> None:
            conn = snowflake.connector.connect(
                account=account,
                user=str(configuration["username"]),
                password=credentials["password"],
                warehouse=str(configuration["warehouse"]),
                database=str(configuration["database"]),
                schema=str(configuration.get("schema_name", "PUBLIC")),
                role=configuration.get("role") or None,
                login_timeout=timeout,
                network_timeout=timeout,
                client_session_keep_alive=False,
            )
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            finally:
                conn.close()

        try:
            await asyncio.wait_for(asyncio.to_thread(_ping), timeout=timeout + 2)
            return TesterResult(True, "healthy", _latency(started))
        except TimeoutError:
            return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TIMEOUT")
        except (DatabaseError, ProgrammingError) as error:
            code = getattr(error, "errno", None)
            auth = code in {250001, 390100, 390101} or "authentication" in str(error).lower()
            return TesterResult(
                False,
                "unhealthy",
                _latency(started),
                "CONNECTION_AUTHENTICATION_FAILED" if auth else "CONNECTION_HOST_UNREACHABLE",
            )
        except Exception:
            return TesterResult(
                False, "unhealthy", _latency(started), "CONNECTION_HOST_UNREACHABLE"
            )


class BigQueryTester:
    """Google BigQuery reachability + auth via a service-account key (lazy import)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        try:
            import json as _json

            from google.cloud import bigquery  # type: ignore
            from google.oauth2 import service_account  # type: ignore
        except ImportError:
            return TesterResult(False, "unhealthy", 0, "CONNECTION_DRIVER_UNAVAILABLE")
        try:
            info = _json.loads(credentials["service_account_json"])
        except (ValueError, KeyError):
            return TesterResult(False, "unhealthy", 0, "CONNECTION_CONFIGURATION_INVALID")
        timeout = self.settings.CONNECTION_TEST_TIMEOUT_SECONDS
        started = time.perf_counter()

        def _ping() -> None:
            creds = service_account.Credentials.from_service_account_info(info)
            client = bigquery.Client(
                project=str(configuration["project_id"]),
                credentials=creds,
                location=str(configuration["location"]),
            )
            try:
                job = client.query("SELECT 1", timeout=timeout)
                list(job.result(timeout=timeout))
            finally:
                client.close()

        try:
            await asyncio.wait_for(asyncio.to_thread(_ping), timeout=timeout + 3)
            return TesterResult(True, "healthy", _latency(started))
        except TimeoutError:
            return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TIMEOUT")
        except Exception as error:  # google exceptions vary; map by message safely
            text = str(error).lower()
            if any(k in text for k in ("permission", "forbidden", "credential", "unauthorized")):
                code = "CONNECTION_AUTHENTICATION_FAILED"
            elif "not found" in text:
                code = "CONNECTION_METADATA_UNAVAILABLE"
            else:
                code = "CONNECTION_HOST_UNREACHABLE"
            return TesterResult(False, "unhealthy", _latency(started), code)


class S3Tester:
    """Amazon S3 (and S3-compatible) reachability + auth via boto3 (lazy import)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        try:
            import boto3  # type: ignore
            from botocore.config import Config  # type: ignore
            from botocore.exceptions import ClientError  # type: ignore
        except ImportError:
            return TesterResult(False, "unhealthy", 0, "CONNECTION_DRIVER_UNAVAILABLE")
        endpoint = configuration.get("endpoint_url")
        if endpoint:
            # A custom (S3-compatible) endpoint is user-supplied → SSRF-guard it.
            await validate_url(str(endpoint), self.settings)
        timeout = self.settings.CONNECTION_TEST_TIMEOUT_SECONDS
        started = time.perf_counter()

        def _ping() -> None:
            client = boto3.client(
                "s3",
                region_name=str(configuration["region"]),
                aws_access_key_id=credentials["access_key_id"],
                aws_secret_access_key=credentials["secret_access_key"],
                aws_session_token=credentials.get("session_token") or None,
                endpoint_url=str(endpoint) if endpoint else None,
                config=Config(
                    connect_timeout=timeout,
                    read_timeout=timeout,
                    retries={"max_attempts": 1},
                    signature_version="s3v4",
                ),
            )
            client.head_bucket(Bucket=str(configuration["bucket"]))

        try:
            await asyncio.wait_for(asyncio.to_thread(_ping), timeout=timeout + 2)
            return TesterResult(True, "healthy", _latency(started))
        except TimeoutError:
            return TesterResult(False, "unhealthy", _latency(started), "CONNECTION_TIMEOUT")
        except ClientError as error:
            status = int(error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) or 0)
            if status in {401, 403}:
                code = "CONNECTION_AUTHENTICATION_FAILED"
            elif status == 404:
                code = "CONNECTION_METADATA_UNAVAILABLE"
            else:
                code = "CONNECTION_HOST_UNREACHABLE"
            return TesterResult(False, "unhealthy", _latency(started), code)
        except Exception:
            return TesterResult(
                False, "unhealthy", _latency(started), "CONNECTION_HOST_UNREACHABLE"
            )


class ConnectionTesterRegistry:
    def __init__(self, settings: Settings) -> None:
        self._testers: dict[str, ConnectionTester] = {
            "postgresql": PostgreSQLTester(settings),
            "mysql": MySQLTester(settings),
            "rest_api": RestApiTester(settings),
            "mssql": MSSQLTester(settings),
            "snowflake": SnowflakeTester(settings),
            "bigquery": BigQueryTester(settings),
            "s3": S3Tester(settings),
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
