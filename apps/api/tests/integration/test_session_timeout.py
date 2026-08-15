"""Idle session-timeout and session-lifecycle security tests.

Idle is simulated deterministically by ageing ``last_seen_at`` in the database
(no 30-minute waits). Covers the sliding window boundary, that background reads
do NOT extend it, activity renewal, refresh-idle enforcement, revocation,
suspended users, admin termination, and CSRF.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import timedelta
from typing import cast
from uuid import UUID

import pytest
from httpx import Response
from sqlalchemy import delete, select, update
from starlette.testclient import TestClient

from vip_api.auth.models import AuthSession, PasswordResetToken, User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.governance.models import AuditEvent
from vip_api.main import create_application
from vip_api.tenancy.models import Organization

PASSWORD = "Development passphrase 2026"


async def _reset(settings: Settings) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await db.execute(delete(Organization))
            await db.execute(delete(AuditEvent))
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
    email: str,
    platform_admin: bool = False,
) -> UUID:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            user = User(
                username=username,
                normalized_username=username,
                email=email,
                normalized_email=email.casefold(),
                password_hash=PasswordService(settings).hash_password(PASSWORD),
                display_name=username.title(),
                status=UserStatus.ACTIVE,
                is_platform_admin=platform_admin,
            )
            db.add(user)
            await db.commit()
            return user.id
    finally:
        await database.dispose()


async def _age_last_seen(settings: Settings, user_id: UUID, minutes: int) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
                .values(last_seen_at=utc_now() - timedelta(minutes=minutes))
            )
            await db.commit()
    finally:
        await database.dispose()


async def _session_row(settings: Settings, user_id: UUID) -> AuthSession | None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            # scalars(...).first() is typed ScalarResult[AuthSession].first() ->
            # AuthSession | None, unlike scalar() which erases to Any.
            result = await db.scalars(
                select(AuthSession)
                .where(AuthSession.user_id == user_id)
                .order_by(AuthSession.created_at.desc())
            )
            return result.first()
    finally:
        await database.dispose()


async def _count_audit(settings: Settings, event_type: str) -> int:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            rows = (
                await db.scalars(select(AuditEvent).where(AuditEvent.event_type == event_type))
            ).all()
            return len(list(rows))
    finally:
        await database.dispose()


def _login(client: TestClient, username: str) -> Response:
    return cast(
        Response,
        client.post("/auth/login", json={"username": username, "password": PASSWORD}),
    )


def _csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("vip_csrf_token")
    assert isinstance(token, str)
    return {"X-CSRF-Token": token}


@pytest.fixture
def env(settings: Settings) -> Iterator[tuple[TestClient, Settings, UUID]]:
    asyncio.run(_reset(settings))
    uid = asyncio.run(_add_user(settings, username="idle-user", email="idle@vip.test"))
    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        yield client, settings, uid


@pytest.mark.integration
def test_idle_default_is_thirty_minutes(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, _ = env
    assert settings.AUTH_SESSION_IDLE_TTL_MINUTES == 30
    assert settings.AUTH_SESSION_IDLE_WARNING_MINUTES == 5
    body = _login(client, "idle-user").json()
    assert body["session"]["idle_timeout_minutes"] == 30
    assert body["session"]["warning_minutes"] == 5
    assert body["session"]["idle_expires_at"] is not None


@pytest.mark.integration
def test_active_and_boundary_sessions(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    assert client.get("/auth/me").status_code == 200  # fresh
    asyncio.run(_age_last_seen(settings, uid, 29))
    assert client.get("/auth/me").status_code == 200  # 29 min: still valid
    asyncio.run(_age_last_seen(settings, uid, 31))
    assert client.get("/auth/me").status_code == 401  # 31 min: rejected


@pytest.mark.integration
def test_idle_expiry_revokes_and_audits(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    asyncio.run(_age_last_seen(settings, uid, 31))
    assert client.get("/auth/me").status_code == 401
    row = asyncio.run(_session_row(settings, uid))
    assert row is not None and row.revoked_at is not None
    assert row.revocation_reason == "idle_timeout"
    assert asyncio.run(_count_audit(settings, "session.expired_idle")) == 1


@pytest.mark.integration
def test_background_read_does_not_extend_idle(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    asyncio.run(_age_last_seen(settings, uid, 20))
    before = asyncio.run(_session_row(settings, uid))
    assert before is not None
    # A plain authenticated GET (background/poll style) must NOT bump last_seen.
    assert client.get("/auth/me").status_code == 200
    after = asyncio.run(_session_row(settings, uid))
    assert after is not None
    assert after.last_seen_at == before.last_seen_at


@pytest.mark.integration
def test_activity_endpoint_renews_idle_window(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    asyncio.run(_age_last_seen(settings, uid, 20))
    resp = client.post("/auth/session/activity", headers=_csrf(client))
    assert resp.status_code == 200
    row = asyncio.run(_session_row(settings, uid))
    assert row is not None
    # Renewed to ~now, so the session survives well past the previous deadline.
    assert utc_now() - row.last_seen_at < timedelta(minutes=1)
    asyncio.run(_age_last_seen(settings, uid, 29))
    assert client.get("/auth/me").status_code == 200


@pytest.mark.integration
def test_activity_requires_csrf(env: tuple[TestClient, Settings, UUID]) -> None:
    client, _, _ = env
    _login(client, "idle-user")
    assert client.post("/auth/session/activity").status_code == 403


@pytest.mark.integration
def test_expired_session_cannot_be_renewed(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    headers = _csrf(client)
    asyncio.run(_age_last_seen(settings, uid, 31))
    assert client.post("/auth/session/activity", headers=headers).status_code == 401


@pytest.mark.integration
def test_refresh_cannot_bypass_idle_timeout(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    headers = _csrf(client)
    asyncio.run(_age_last_seen(settings, uid, 31))
    # A refresh with a valid refresh cookie must still be rejected once idle.
    assert client.post("/auth/refresh", headers=headers).status_code == 401


@pytest.mark.integration
def test_revoked_session_rejected_immediately(env: tuple[TestClient, Settings, UUID]) -> None:
    client, _, _ = env
    _login(client, "idle-user")
    sid = client.get("/auth/sessions").json()["current_session_id"]
    assert client.delete(f"/auth/sessions/{sid}", headers=_csrf(client)).status_code == 200
    assert client.get("/auth/me").status_code == 401


@pytest.mark.integration
def test_suspended_user_session_rejected(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    assert client.get("/auth/me").status_code == 200

    async def _suspend() -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                await db.execute(
                    update(User).where(User.id == uid).values(status=UserStatus.SUSPENDED)
                )
                await db.commit()
        finally:
            await database.dispose()

    asyncio.run(_suspend())
    assert client.get("/auth/me").status_code == 401


@pytest.mark.integration
def test_admin_can_terminate_user_sessions(env: tuple[TestClient, Settings, UUID]) -> None:
    client, settings, uid = env
    _login(client, "idle-user")
    assert client.get("/auth/me").status_code == 200
    asyncio.run(
        _add_user(settings, username="ops-admin", email="ops@vip.test", platform_admin=True)
    )
    with TestClient(create_application(settings), raise_server_exceptions=False) as admin:
        _login(admin, "ops-admin")
        resp = admin.post(f"/api/v1/platform/users/{uid}/sessions/revoke", headers=_csrf(admin))
        assert resp.status_code == 200
        assert resp.json()["revoked"] >= 1
    # The target user's session is now dead.
    assert client.get("/auth/me").status_code == 401
    assert asyncio.run(_count_audit(settings, "session.revoked_by_admin")) == 1


@pytest.mark.integration
def test_non_admin_cannot_terminate_sessions(env: tuple[TestClient, Settings, UUID]) -> None:
    client, _, uid = env
    _login(client, "idle-user")
    # A regular user calling the admin endpoint is denied. The platform-admin
    # guard hides the surface (404) rather than disclosing it exists (403); both
    # are valid denials — the point is the action does not succeed.
    resp = client.post(f"/api/v1/platform/users/{uid}/sessions/revoke", headers=_csrf(client))
    assert resp.status_code in (401, 403, 404)
