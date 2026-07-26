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
