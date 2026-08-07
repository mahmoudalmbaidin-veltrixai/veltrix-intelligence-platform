"""Unit coverage for the post-Core beta connectors' testers (Part A).

Verifies: (1) all five connectors are registered in the tester registry;
(2) each real-driver tester degrades to a safe CONNECTION_DRIVER_UNAVAILABLE
result when its optional driver is absent (never crashes); (3) the S3 tester's
success and auth-failure mapping via an injected fake boto3 (no AWS needed).
"""

from __future__ import annotations

import importlib.util
import sys
import types

import pytest

from vip_api.connections.testers import ConnectionTesterRegistry, S3Tester
from vip_api.core.config import Settings


def _driver_present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def test_all_new_connectors_registered(settings: Settings) -> None:
    registry = ConnectionTesterRegistry(settings)
    for key in ("mssql", "snowflake", "bigquery", "s3", "rest_api"):
        assert registry.get(key) is not None


@pytest.mark.parametrize(
    ("key", "module", "config", "creds"),
    [
        (
            "mssql",
            "pytds",
            {"host": "h", "port": 1433, "database": "d", "username": "u"},
            {"password": "p"},
        ),
        (
            "snowflake",
            "snowflake.connector",
            {
                "account": "acme",
                "username": "u",
                "warehouse": "w",
                "database": "d",
                "schema_name": "PUBLIC",
            },
            {"password": "p"},
        ),
        (
            "bigquery",
            "google.cloud.bigquery",
            {"project_id": "proj", "location": "US"},
            {"service_account_json": '{"type":"service_account"}'},
        ),
        (
            "s3",
            "boto3",
            {"bucket": "buck-et", "region": "us-east-1"},
            {"access_key_id": "AKIA", "secret_access_key": "sk"},
        ),
    ],
)
@pytest.mark.asyncio
async def test_tester_degrades_when_driver_missing(
    settings: Settings, key: str, module: str, config: dict, creds: dict
) -> None:
    if _driver_present(module):
        pytest.skip(f"{module} installed; degradation path not exercised in this env")
    result = await ConnectionTesterRegistry(settings).get(key).test(config, creds)
    assert result.success is False
    assert result.error_code == "CONNECTION_DRIVER_UNAVAILABLE"


class _FakeClientError(Exception):
    def __init__(self, status: int) -> None:
        self.response = {"ResponseMetadata": {"HTTPStatusCode": status}}


def _install_fake_boto3(
    monkeypatch: pytest.MonkeyPatch, *, head_ok: bool, status: int = 403
) -> None:
    boto3 = types.ModuleType("boto3")
    botocore = types.ModuleType("botocore")
    config_mod = types.ModuleType("botocore.config")
    exc_mod = types.ModuleType("botocore.exceptions")

    class _Config:
        def __init__(self, **_: object) -> None: ...

    config_mod.Config = _Config  # type: ignore[attr-defined]
    exc_mod.ClientError = _FakeClientError  # type: ignore[attr-defined]

    class _S3:
        def head_bucket(self, **_: object) -> None:
            if not head_ok:
                raise _FakeClientError(status)

    boto3.client = lambda *a, **k: _S3()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", config_mod)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", exc_mod)


@pytest.mark.asyncio
async def test_s3_tester_success(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_boto3(monkeypatch, head_ok=True)
    result = await S3Tester(settings).test(
        {"bucket": "buck-et", "region": "us-east-1", "endpoint_url": None},
        {"access_key_id": "AKIA", "secret_access_key": "sk"},
    )
    assert result.success is True and result.health_status == "healthy"


@pytest.mark.asyncio
async def test_s3_tester_maps_forbidden_to_auth_failure(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_boto3(monkeypatch, head_ok=False, status=403)
    result = await S3Tester(settings).test(
        {"bucket": "buck-et", "region": "us-east-1", "endpoint_url": None},
        {"access_key_id": "AKIA", "secret_access_key": "bad"},
    )
    assert result.success is False
    assert result.error_code == "CONNECTION_AUTHENTICATION_FAILED"
