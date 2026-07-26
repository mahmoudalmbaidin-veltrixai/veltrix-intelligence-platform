"""Password, token, and authentication configuration unit tests."""

import pytest
from pydantic import ValidationError

from vip_api.auth.password import PasswordService
from vip_api.auth.tokens import generate_session_tokens, hash_token
from vip_api.core.config import Settings


def test_argon2id_hash_and_verification(settings: Settings) -> None:
    service = PasswordService(settings)
    password = "correct horse battery staple"
    password_hash = service.hash_password(password)
    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert service.verify_password(password, password_hash)
    assert not service.verify_password("incorrect password", password_hash)
    assert not service.needs_rehash(password_hash)


def test_password_length_policy(settings: Settings) -> None:
    service = PasswordService(settings)
    with pytest.raises(ValueError):
        service.hash_password("too-short")
    with pytest.raises(ValueError):
        service.hash_password("x" * (settings.PASSWORD_MAX_LENGTH + 1))


def test_tokens_have_entropy_and_domain_separated_hashes() -> None:
    first = generate_session_tokens()
    second = generate_session_tokens()
    assert len(first.access) >= 43
    assert len({first.access, first.refresh, first.csrf, second.access}) == 4
    assert hash_token(first.access, "access") != hash_token(first.access, "refresh")
    assert first.access not in hash_token(first.access, "access")


def test_production_requires_secure_auth_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@db/vip",
            REDIS_URL="redis://cache/0",
            CORS_ALLOWED_ORIGINS="https://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            CSRF_TRUSTED_ORIGINS="https://app.example.com",
            AUTH_COOKIE_SECURE=False,
        )
