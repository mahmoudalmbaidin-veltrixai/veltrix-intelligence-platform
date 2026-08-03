"""End-to-end API authentication tests against PostgreSQL and Redis."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import cast
from uuid import UUID

import pytest
from httpx import Response
from sqlalchemy import delete, select, update
from starlette.testclient import TestClient

from vip_api.auth.models import AuthSession, PasswordResetToken, User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.password_reset import consume_password_reset, request_password_reset
from vip_api.auth.sessions import (
    cleanup_expired_sessions,
    create_session,
    revoke_all_user_sessions,
    revoke_session_by_id,
)
from vip_api.auth.tokens import hash_token
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.main import create_application
from vip_api.tenancy.models import Organization

EMAIL = "admin@veltrix.local"
PASSWORD = "Development passphrase 2026"


async def reset_auth_data(settings: Settings) -> None:
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


async def add_user(
    settings: Settings,
    *,
    email: str = EMAIL,
    password: str = PASSWORD,
    status: UserStatus = UserStatus.ACTIVE,
) -> UUID:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            user = User(
                username="admin",
                normalized_username="admin",
                email=email,
                normalized_email=email.casefold(),
                password_hash=PasswordService(settings).hash_password(password),
                display_name="VIP Administrator",
                status=status,
            )
            db.add(user)
            await db.commit()
            return user.id
    finally:
        await database.dispose()


def login(client: TestClient, password: str = PASSWORD) -> Response:
    return cast(Response, client.post("/auth/login", json={"email": EMAIL, "password": password}))


def required_cookie(client: TestClient, name: str) -> str:
    value = client.cookies.get(name)
    assert isinstance(value, str)
    return value


@pytest.fixture
def auth_client(settings: Settings) -> Iterator[TestClient]:
    asyncio.run(reset_auth_data(settings))
    asyncio.run(add_user(settings))
    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        yield client


@pytest.mark.integration
def test_login_me_refresh_logout_flow(auth_client: TestClient) -> None:
    login_response = login(auth_client)
    assert login_response.status_code == 200
    body = login_response.json()
    assert body["user"]["email"] == EMAIL
    # The submitted password and any raw session token must never be echoed. (The
    # safe `must_change_password` boolean is a legitimate field, so assert on the
    # actual secret value rather than the substring "password".)
    assert PASSWORD not in login_response.text
    assert "token" not in login_response.text
    cookies = login_response.headers.get_list("set-cookie")
    assert any("vip_access_session=" in value and "HttpOnly" in value for value in cookies)
    assert any("vip_refresh_session=" in value and "HttpOnly" in value for value in cookies)
    assert any("vip_csrf_token=" in value and "HttpOnly" not in value for value in cookies)
    assert all("SameSite=lax" in value for value in cookies)

    assert auth_client.get("/auth/me").status_code == 200
    old_refresh = required_cookie(auth_client, "vip_refresh_session")
    old_csrf = required_cookie(auth_client, "vip_csrf_token")
    refresh_response = auth_client.post("/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert refresh_response.status_code == 200
    assert auth_client.cookies.get("vip_refresh_session") != old_refresh
    assert auth_client.cookies.get("vip_csrf_token") != old_csrf

    csrf = required_cookie(auth_client, "vip_csrf_token")
    logout_response = auth_client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_response.status_code == 200
    assert logout_response.json() == {"success": True}
    assert auth_client.get("/auth/me").status_code == 401
    assert auth_client.post("/auth/logout").status_code == 200
    assert auth_client.post("/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code == 401


@pytest.mark.integration
def test_invalid_credentials_are_generic_and_lockout_expires(settings: Settings) -> None:
    asyncio.run(reset_auth_data(settings))
    user_id = asyncio.run(add_user(settings))
    lock_settings = settings.model_copy(update={"AUTH_MAX_FAILED_LOGIN_ATTEMPTS": 3})
    with TestClient(create_application(lock_settings), raise_server_exceptions=False) as client:
        wrong = login(client, "wrong password")
        unknown = client.post(
            "/auth/login", json={"email": "unknown@veltrix.local", "password": "wrong password"}
        )
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
        assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"]
        assert wrong.json()["error"]["correlation_id"]
        assert "Traceback" not in wrong.text
        login(client, "wrong password")
        login(client, "wrong password")
        assert login(client).status_code == 401

    async def expire_lock() -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                await db.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(locked_until=utc_now() - timedelta(seconds=1))
                )
                await db.commit()
        finally:
            await database.dispose()

    asyncio.run(expire_lock())
    with TestClient(create_application(lock_settings), raise_server_exceptions=False) as client:
        assert login(client).status_code == 200


@pytest.mark.integration
def test_login_counters_and_inactive_account(settings: Settings) -> None:
    asyncio.run(reset_auth_data(settings))
    user_id = asyncio.run(add_user(settings))
    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        assert login(client, "wrong password").status_code == 401

        async def read_failed_count() -> int:
            database = Database(settings)
            try:
                async with database.session_factory() as db:
                    user = await db.get(User, user_id)
                    assert user is not None
                    return user.failed_login_count
            finally:
                await database.dispose()

        assert asyncio.run(read_failed_count()) == 1
        assert login(client).status_code == 200
        assert asyncio.run(read_failed_count()) == 0

    asyncio.run(reset_auth_data(settings))
    asyncio.run(add_user(settings, status=UserStatus.SUSPENDED))
    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        inactive = login(client)
        unknown = client.post(
            "/auth/login", json={"email": "unknown@veltrix.local", "password": PASSWORD}
        )
        assert inactive.status_code == unknown.status_code == 401
        assert inactive.json()["error"]["code"] == unknown.json()["error"]["code"]


@pytest.mark.integration
def test_missing_expired_revoked_and_disabled_sessions(settings: Settings) -> None:
    asyncio.run(reset_auth_data(settings))
    user_id = asyncio.run(add_user(settings))
    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        assert client.get("/auth/me").status_code == 401
        assert login(client).status_code == 200
        access = required_cookie(client, "vip_access_session")

        async def expire_access() -> None:
            database = Database(settings)
            try:
                async with database.session_factory() as db:
                    await db.execute(
                        update(AuthSession)
                        .where(AuthSession.access_token_hash == hash_token(access, "access"))
                        .values(access_expires_at=utc_now() - timedelta(seconds=1))
                    )
                    await db.commit()
            finally:
                await database.dispose()

        asyncio.run(expire_access())
        refresh_before = client.cookies.get("vip_refresh_session")
        assert client.get("/auth/me").status_code == 401
        assert client.cookies.get("vip_refresh_session") == refresh_before

    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        assert login(client).status_code == 200

        async def disable_user() -> None:
            database = Database(settings)
            try:
                async with database.session_factory() as db:
                    await db.execute(
                        update(User).where(User.id == user_id).values(status=UserStatus.DISABLED)
                    )
                    await db.commit()
            finally:
                await database.dispose()

        asyncio.run(disable_user())
        assert client.get("/auth/me").status_code == 401

    asyncio.run(reset_auth_data(settings))
    asyncio.run(add_user(settings))
    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        assert login(client).status_code == 200
        access = required_cookie(client, "vip_access_session")

        async def revoke_access() -> None:
            database = Database(settings)
            try:
                async with database.session_factory() as db:
                    session = await db.scalar(
                        select(AuthSession).where(
                            AuthSession.access_token_hash == hash_token(access, "access")
                        )
                    )
                    assert session is not None
                    session.revoked_at = utc_now()
                    await db.commit()
            finally:
                await database.dispose()

        asyncio.run(revoke_access())
        assert client.get("/auth/me").status_code == 401


@pytest.mark.integration
def test_csrf_and_refresh_replay(auth_client: TestClient, settings: Settings) -> None:
    assert login(auth_client).status_code == 200
    old_refresh = required_cookie(auth_client, "vip_refresh_session")
    old_csrf = required_cookie(auth_client, "vip_csrf_token")
    assert auth_client.post("/auth/refresh").status_code == 403
    assert auth_client.post("/auth/refresh", headers={"X-CSRF-Token": "invalid"}).status_code == 403
    assert (
        auth_client.post(
            "/auth/refresh",
            headers={"X-CSRF-Token": old_csrf, "Origin": "https://attacker.invalid"},
        ).status_code
        == 403
    )
    assert auth_client.post("/auth/refresh", headers={"X-CSRF-Token": old_csrf}).status_code == 200
    current_csrf = required_cookie(auth_client, "vip_csrf_token")
    assert (
        auth_client.post("/auth/refresh", headers={"X-CSRF-Token": current_csrf}).status_code == 200
    )

    replay = TestClient(create_application(settings), raise_server_exceptions=False)
    replay.cookies.set("vip_refresh_session", old_refresh, path="/auth")
    replay.cookies.set("vip_csrf_token", old_csrf, path="/")
    with replay:
        response = replay.post("/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert response.status_code == 401
    assert "vip_local_dev_only" not in response.text


@pytest.mark.integration
def test_expired_and_revoked_refresh_and_logout_csrf(settings: Settings) -> None:
    async def invalidate_refresh(raw_token: str, *, revoke: bool) -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                session = await db.scalar(
                    select(AuthSession).where(
                        AuthSession.refresh_token_hash == hash_token(raw_token, "refresh")
                    )
                )
                assert session is not None
                if revoke:
                    session.revoked_at = utc_now()
                else:
                    session.refresh_expires_at = utc_now() - timedelta(seconds=1)
                await db.commit()
        finally:
            await database.dispose()

    for revoke in (False, True):
        asyncio.run(reset_auth_data(settings))
        asyncio.run(add_user(settings))
        with TestClient(create_application(settings), raise_server_exceptions=False) as client:
            assert login(client).status_code == 200
            refresh_token = required_cookie(client, "vip_refresh_session")
            csrf = required_cookie(client, "vip_csrf_token")
            asyncio.run(invalidate_refresh(refresh_token, revoke=revoke))
            assert client.post("/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code == 401

    asyncio.run(reset_auth_data(settings))
    asyncio.run(add_user(settings))
    with TestClient(create_application(settings), raise_server_exceptions=False) as client:
        assert login(client).status_code == 200
        assert client.post("/auth/logout").status_code == 403
        assert client.get("/auth/me").status_code == 200


@pytest.mark.integration
def test_concurrent_refresh_is_serialized(settings: Settings) -> None:
    asyncio.run(reset_auth_data(settings))
    asyncio.run(add_user(settings))
    app = create_application(settings)
    with TestClient(app, raise_server_exceptions=False) as login_client:
        assert login(login_client).status_code == 200
        refresh_token = required_cookie(login_client, "vip_refresh_session")
        csrf = required_cookie(login_client, "vip_csrf_token")

    def refresh_once() -> int:
        with TestClient(create_application(settings), raise_server_exceptions=False) as client:
            client.cookies.set("vip_refresh_session", refresh_token, path="/auth")
            client.cookies.set("vip_csrf_token", csrf, path="/")
            response = cast(
                Response,
                client.post("/auth/refresh", headers={"X-CSRF-Token": csrf}),
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _: refresh_once(), range(2)))
    assert statuses == [200, 401]


@pytest.mark.integration
def test_session_revocation_cleanup_and_password_reset(settings: Settings) -> None:
    asyncio.run(reset_auth_data(settings))
    user_id = asyncio.run(add_user(settings))

    async def exercise() -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                user = await db.get(User, user_id)
                assert user is not None
                first, _ = await create_session(db, user, settings)
                second, _ = await create_session(db, user, settings)
                await db.commit()
                assert await revoke_session_by_id(db, first.id, "test")
                await db.commit()
                active_session = await db.get(AuthSession, second.id)
                assert active_session is not None and active_session.revoked_at is None
                assert await revoke_all_user_sessions(db, user_id, "all") == 1
                await db.commit()

                expired, _ = await create_session(db, user, settings)
                expired.refresh_expires_at = utc_now() - timedelta(seconds=1)
                await db.commit()
                assert await cleanup_expired_sessions(db) == 1
                await db.commit()

                reset_session, _ = await create_session(db, user, settings)
                await db.commit()
                raw_result = await request_password_reset(db, EMAIL, settings)
                assert raw_result is not None
                raw_token = raw_result[0]
                stored = await db.scalar(
                    select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
                )
                assert stored is not None and stored.token_hash != raw_token
                await consume_password_reset(
                    db, raw_token, "Replacement passphrase 2026", PasswordService(settings)
                )
                reset_session_after = await db.get(AuthSession, reset_session.id)
                assert (
                    reset_session_after is not None and reset_session_after.revoked_at is not None
                )
                with pytest.raises(ApplicationError):
                    await consume_password_reset(
                        db, raw_token, "Another replacement 2026", PasswordService(settings)
                    )
                assert await request_password_reset(db, "missing@veltrix.local", settings) is None

                expiring_result = await request_password_reset(db, EMAIL, settings)
                assert expiring_result is not None
                expiring_token = expiring_result[0]
                expiring = await db.scalar(
                    select(PasswordResetToken).where(
                        PasswordResetToken.token_hash
                        == hash_token(expiring_token, "password-reset")
                    )
                )
                assert expiring is not None
                expiring.expires_at = utc_now() - timedelta(seconds=1)
                await db.commit()
                with pytest.raises(ApplicationError) as reset_error:
                    await consume_password_reset(
                        db, expiring_token, "Another replacement 2026", PasswordService(settings)
                    )
                assert reset_error.value.code == "PASSWORD_RESET_TOKEN_EXPIRED"
        finally:
            await database.dispose()

    asyncio.run(exercise())
