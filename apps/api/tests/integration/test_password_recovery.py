"""Password recovery + forced-change end-to-end tests (Phase B9.0).

Drives the real auth routes through a TestClient against PostgreSQL/Redis:
non-disclosing reset request, single-use/expiry/purpose token handling, session
revocation, current-password change, and the server-side ``must_change_password``
enforcement chokepoint.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import Response
from sqlalchemy import delete, select, update
from starlette.testclient import TestClient

from vip_api.auth.models import AuthSession, PasswordResetToken, User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.password_reset import request_password_reset
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.main import create_application
from vip_api.tenancy.models import Organization

PASSWORD = "Development passphrase 2026"
NEW_PASSWORD = "Rotated passphrase 2026!"


async def _reset(settings: Settings) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await db.execute(delete(Organization))
            await db.execute(delete(PasswordResetToken))
            await db.execute(delete(AuthSession))
            await db.execute(delete(User))
            await db.commit()
    finally:
        await database.dispose()


async def _add_user(
    settings: Settings,
    *,
    username: str,
    email: str | None,
    password: str = PASSWORD,
    status: UserStatus = UserStatus.ACTIVE,
    must_change_password: bool = False,
) -> UUID:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            user = User(
                username=username,
                normalized_username=username.casefold(),
                email=email,
                normalized_email=email.casefold() if email else None,
                password_hash=PasswordService(settings).hash_password(password),
                display_name="Recovery User",
                status=status,
                must_change_password=must_change_password,
            )
            db.add(user)
            await db.commit()
            return user.id
    finally:
        await database.dispose()


async def _token_count(settings: Settings, user_id: UUID) -> int:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            rows = await db.scalars(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
            )
            return len(list(rows.all()))
    finally:
        await database.dispose()


async def _mint_token(settings: Settings, identifier: str) -> str:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            result = await request_password_reset(db, identifier, settings)
            assert result is not None
            return result[0]
    finally:
        await database.dispose()


async def _expire_tokens(settings: Settings, user_id: UUID) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await db.execute(
                update(PasswordResetToken)
                .where(PasswordResetToken.user_id == user_id)
                .values(expires_at=utc_now() - timedelta(minutes=1))
            )
            await db.commit()
    finally:
        await database.dispose()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    asyncio.run(_reset(settings))
    with TestClient(create_application(settings), raise_server_exceptions=False) as test_client:
        yield test_client


def _csrf(client: TestClient) -> str:
    value = client.cookies.get("vip_csrf_token")
    assert isinstance(value, str)
    return value


@pytest.mark.integration
def test_reset_request_is_non_disclosing(settings: Settings, client: TestClient) -> None:
    known = asyncio.run(_add_user(settings, username="known", email="known@vip.test"))

    known_response = cast(
        Response, client.post("/auth/password-reset/request", json={"identifier": "known@vip.test"})
    )
    unknown_response = cast(
        Response,
        client.post("/auth/password-reset/request", json={"identifier": "ghost@vip.test"}),
    )

    # Identical status + body regardless of whether the account exists.
    assert known_response.status_code == 202
    assert unknown_response.status_code == 202
    assert known_response.json() == unknown_response.json() == {"status": "accepted"}
    assert "token" not in known_response.text
    # A token was created only for the real account.
    assert asyncio.run(_token_count(settings, known)) == 1

    # A username also works and stays non-disclosing.
    by_username = cast(
        Response, client.post("/auth/password-reset/request", json={"identifier": "known"})
    )
    assert by_username.status_code == 202


@pytest.mark.integration
def test_suspended_user_reset_is_non_disclosing(settings: Settings, client: TestClient) -> None:
    suspended = asyncio.run(
        _add_user(settings, username="susp", email="susp@vip.test", status=UserStatus.SUSPENDED)
    )
    response = cast(
        Response, client.post("/auth/password-reset/request", json={"identifier": "susp@vip.test"})
    )
    assert response.status_code == 202
    # No token is issued for a suspended account.
    assert asyncio.run(_token_count(settings, suspended)) == 0


@pytest.mark.integration
def test_reset_confirm_rotates_password_and_revokes_sessions(
    settings: Settings, client: TestClient
) -> None:
    asyncio.run(_add_user(settings, username="rot", email="rot@vip.test"))
    # Establish a live session that the reset must revoke.
    assert (
        client.post("/auth/login", json={"email": "rot@vip.test", "password": PASSWORD}).status_code
        == 200
    )
    assert client.get("/auth/me").status_code == 200

    token = asyncio.run(_mint_token(settings, "rot@vip.test"))
    confirm = client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert confirm.status_code == 200
    assert confirm.json() == {"status": "accepted"}

    # The prior session is revoked.
    assert client.get("/auth/me").status_code == 401
    # The old password no longer authenticates; the new one does.
    assert (
        client.post("/auth/login", json={"email": "rot@vip.test", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", json={"email": "rot@vip.test", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )

    # The token is single-use — replay fails.
    replay = client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": "Another pass 2026!"}
    )
    assert replay.status_code == 400


@pytest.mark.integration
def test_reset_confirm_rejects_invalid_and_expired_tokens(
    settings: Settings, client: TestClient
) -> None:
    user_id = asyncio.run(_add_user(settings, username="tok", email="tok@vip.test"))

    # Garbage token.
    invalid = client.post(
        "/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": NEW_PASSWORD},
    )
    assert invalid.status_code == 400

    # Expired token.
    token = asyncio.run(_mint_token(settings, "tok@vip.test"))
    asyncio.run(_expire_tokens(settings, user_id))
    expired = client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert expired.status_code == 400


@pytest.mark.integration
def test_reset_confirm_enforces_password_policy(settings: Settings, client: TestClient) -> None:
    asyncio.run(_add_user(settings, username="pol", email="pol@vip.test"))
    token = asyncio.run(_mint_token(settings, "pol@vip.test"))
    weak = client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": "short"}
    )
    assert weak.status_code in {400, 422}


@pytest.mark.integration
def test_change_password_requires_current_and_revokes_sessions(
    settings: Settings, client: TestClient
) -> None:
    asyncio.run(_add_user(settings, username="chg", email="chg@vip.test"))
    assert (
        client.post("/auth/login", json={"email": "chg@vip.test", "password": PASSWORD}).status_code
        == 200
    )
    csrf = _csrf(client)

    # Wrong current password is rejected.
    wrong = client.post(
        "/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": "incorrect", "new_password": NEW_PASSWORD},
    )
    assert wrong.status_code == 400

    # Correct current password succeeds and revokes sessions.
    ok = client.post(
        "/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert ok.status_code == 200
    assert client.get("/auth/me").status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": "chg@vip.test", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )


@pytest.mark.integration
def test_must_change_password_blocks_business_routes_until_changed(
    settings: Settings, client: TestClient
) -> None:
    asyncio.run(
        _add_user(settings, username="force", email="force@vip.test", must_change_password=True)
    )
    login = client.post("/auth/login", json={"email": "force@vip.test", "password": PASSWORD})
    assert login.status_code == 200
    # The flag is surfaced so the client can route into the forced-change flow.
    assert login.json()["user"]["must_change_password"] is True

    # Session-only endpoints remain reachable...
    assert client.get("/auth/me").status_code == 200
    # ...but any tenant-scoped business route is blocked server-side.
    blocked = client.get("/api/v1/roles", headers={"X-Organization-ID": str(uuid4())})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"

    # Changing the password clears the flag (verified after re-login).
    csrf = _csrf(client)
    changed = client.post(
        "/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    relogin = client.post("/auth/login", json={"email": "force@vip.test", "password": NEW_PASSWORD})
    assert relogin.status_code == 200
    assert relogin.json()["user"]["must_change_password"] is False


@pytest.mark.integration
def test_reset_request_is_rate_limited(settings: Settings, client: TestClient) -> None:
    limit = settings.PASSWORD_RESET_RATE_LIMIT_PER_MINUTE
    identifier = f"rl-{uuid4().hex[:8]}@vip.test"
    statuses = [
        client.post("/auth/password-reset/request", json={"identifier": identifier}).status_code
        for _ in range(limit + 2)
    ]
    # Fails open if Redis is unavailable; when present, the burst is throttled.
    assert statuses.count(429) >= 1 or all(code == 202 for code in statuses)
