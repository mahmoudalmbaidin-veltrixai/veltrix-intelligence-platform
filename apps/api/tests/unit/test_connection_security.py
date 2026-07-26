"""Cryptography, validation, serialization, and SSRF security boundaries."""

import json
import logging
from uuid import uuid4

import pytest
from pydantic import ValidationError

from vip_api.connections.catalog import validate_configuration, validate_credentials
from vip_api.connections.crypto import (
    SecretDecryptionError,
    TestEncryptionKeyProvider,
    associated_data,
    decrypt_json,
    encrypt_json,
)
from vip_api.connections.network import UnsafeDestinationError, validate_host, validate_url
from vip_api.core.config import Settings
from vip_api.core.logging import JsonFormatter


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_authenticated_encryption_random_nonce_tamper_and_wrong_key() -> None:
    provider = TestEncryptionKeyProvider()
    aad = associated_data(uuid4(), uuid4(), uuid4(), "database_encrypted", 1)
    first, first_nonce, version = await encrypt_json({"password": "unique-secret"}, aad, provider)
    second, second_nonce, _ = await encrypt_json({"password": "unique-secret"}, aad, provider)
    assert first_nonce != second_nonce
    assert first != second
    assert await decrypt_json(first, first_nonce, aad, version, provider) == {
        "password": "unique-secret"
    }
    tampered = bytes([first[0] ^ 1]) + first[1:]
    with pytest.raises(SecretDecryptionError):
        await decrypt_json(tampered, first_nonce, aad, version, provider)
    with pytest.raises(SecretDecryptionError):
        await decrypt_json(
            first,
            first_nonce,
            aad,
            version,
            TestEncryptionKeyProvider(b"W" * 32),
        )


@pytest.mark.unit
@pytest.mark.security
def test_connection_type_validation_separates_secrets_and_rejects_unknown_keys() -> None:
    configuration = validate_configuration(
        "postgresql",
        {"host": "db.example.com", "database": "analytics", "username": "reader"},
    )
    assert configuration["port"] == 5432
    assert "password" not in configuration
    assert validate_credentials("postgresql", {"password": "submitted-once"}) == {
        "password": "submitted-once"
    }
    with pytest.raises(ValueError):
        validate_configuration("unknown", {})
    with pytest.raises(ValidationError):
        validate_configuration(
            "postgresql",
            {
                "host": "db.example.com",
                "database": "analytics",
                "username": "reader",
                "password": "must-not-be-here",
            },
        )


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_ssrf_policy_blocks_loopback_metadata_private_and_unsafe_schemes(
    settings: Settings,
) -> None:
    hardened_settings = settings.model_copy(update={"CONNECTION_ALLOW_PRIVATE_NETWORKS": False})
    for host in ("127.0.0.1", "169.254.169.254", "10.0.0.1", "::1"):
        with pytest.raises(UnsafeDestinationError):
            await validate_host(host, 443, hardened_settings)
    for url in ("file:///etc/passwd", "ftp://example.com/file", "http://127.0.0.1"):
        with pytest.raises(UnsafeDestinationError):
            await validate_url(url, hardened_settings)


@pytest.mark.unit
def test_production_requires_connection_encryption_key() -> None:
    with pytest.raises(ValueError, match="CONNECTION_ENCRYPTION_KEY"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://vip:vip@postgres/vip",
            REDIS_URL="redis://redis/0",
            TRUSTED_HOSTS=["api.example.com"],
            CORS_ALLOWED_ORIGINS=["https://app.example.com"],
            CSRF_TRUSTED_ORIGINS=["https://app.example.com"],
            AUTH_COOKIE_SECURE=True,
            CONNECTION_ENCRYPTION_KEY=None,
        )


@pytest.mark.unit
@pytest.mark.security
def test_structured_logging_recursively_redacts_secret_shaped_fields() -> None:
    marker = "unique-log-secret-marker"
    record = logging.makeLogRecord(
        {
            "name": "vip_api.connections",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Safe connection event",
            "credentials": {"password": marker, "nested": {"api_key": marker}},
            "authorization": marker,
            "provider": "database_encrypted",
        }
    )
    output = JsonFormatter(environment="test", service_name="vip-api").format(record)
    payload = json.loads(output)
    assert marker not in output
    assert payload["credentials"]["password"] == "[REDACTED]"
    assert payload["credentials"]["nested"]["api_key"] == "[REDACTED]"
    assert payload["authorization"] == "[REDACTED]"
