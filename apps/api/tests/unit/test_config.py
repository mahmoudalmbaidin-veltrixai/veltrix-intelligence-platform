"""Security-sensitive settings validation tests."""

import pytest
from pydantic import ValidationError

from vip_api.core.config import Settings


def test_production_rejects_wildcard_hosts_and_origins() -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
            REDIS_URL="redis://cache/0",
            CORS_ALLOWED_ORIGINS="*",
            TRUSTED_HOSTS="*",
        )


def test_demo_requires_public_environment_security_controls() -> None:
    with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE"):
        Settings(
            APP_ENV="demo",
            DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
            REDIS_URL="redis://cache/0",
            CORS_ALLOWED_ORIGINS="https://veltrix-one-demo.onrender.com",
            TRUSTED_HOSTS="veltrix-one-api.up.railway.app",
            METRICS_ENABLED=False,
            CONNECTION_ENCRYPTION_KEY="connection-key",
            DASHBOARD_DOWNLOAD_SIGNING_KEY="dashboard-key",
            PIPELINE_DOWNLOAD_SIGNING_KEY="pipeline-key",
            FILE_DOWNLOAD_SIGNING_KEY="file-key",
        )


def test_demo_allows_documented_noop_scanner_and_disabled_email() -> None:
    settings = Settings(
        APP_ENV="demo",
        DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
        REDIS_URL="redis://cache/0",
        CORS_ALLOWED_ORIGINS="https://veltrix-one-demo.onrender.com",
        TRUSTED_HOSTS="veltrix-one-api.up.railway.app",
        CSRF_TRUSTED_ORIGINS="https://veltrix-one-demo.onrender.com",
        AUTH_COOKIE_SECURE=True,
        METRICS_ENABLED=False,
        CONNECTION_ENCRYPTION_KEY="connection-key",
        DASHBOARD_DOWNLOAD_SIGNING_KEY="dashboard-key",
        PIPELINE_DOWNLOAD_SIGNING_KEY="pipeline-key",
        FILE_DOWNLOAD_SIGNING_KEY="file-key",
        FILE_MALWARE_SCANNER="noop",
        DASHBOARD_EMAIL_PROVIDER="disabled",
    )
    assert settings.is_public_environment is True
    assert settings.docs_enabled is False


def test_csv_settings_are_parsed() -> None:
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
        REDIS_URL="redis://cache/0",
        CORS_ALLOWED_ORIGINS="http://localhost:3000, http://localhost:3009",
    )
    assert settings.CORS_ALLOWED_ORIGINS == ["http://localhost:3000", "http://localhost:3009"]


def test_smtp_configuration_is_fail_closed() -> None:
    with pytest.raises(ValidationError, match="DASHBOARD_SMTP_HOST"):
        Settings(
            APP_ENV="test",
            DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
            REDIS_URL="redis://cache/0",
            DASHBOARD_EMAIL_PROVIDER="smtp",
        )
    with pytest.raises(ValidationError, match="cannot both be enabled"):
        Settings(
            APP_ENV="test",
            DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
            REDIS_URL="redis://cache/0",
            DASHBOARD_EMAIL_PROVIDER="smtp",
            DASHBOARD_SMTP_HOST="smtp.example.com",
            DASHBOARD_SMTP_STARTTLS=True,
            DASHBOARD_SMTP_USE_TLS=True,
        )
