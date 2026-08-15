"""End-to-end tests for the self-service Settings account endpoints.

Covers profile update + preferences merge, timezone/immutability validation,
CSRF enforcement, session listing/revocation with cross-user isolation, and
avatar upload/serve/remove with content validation.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Iterator
from typing import cast
from uuid import UUID

import pytest
from httpx import Response
from PIL import Image
from sqlalchemy import delete
from starlette.testclient import TestClient

from vip_api.auth.models import AuthSession, PasswordResetToken, User, UserStatus
from vip_api.auth.password import PasswordService
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.main import create_application
from vip_api.tenancy.models import Organization

EMAIL = "settings-user@veltrix.local"
PASSWORD = "Development passphrase 2026"


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
    settings: Settings, *, username: str = "settings-user", email: str = EMAIL
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
                display_name="Settings User",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.commit()
            return user.id
    finally:
        await database.dispose()


def _login(client: TestClient, email: str = EMAIL) -> Response:
    return cast(Response, client.post("/auth/login", json={"email": email, "password": PASSWORD}))


def _csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("vip_csrf_token")
    assert isinstance(token, str)
    return {"X-CSRF-Token": token}


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (10, 80, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def settings_client(settings: Settings, tmp_path: object) -> Iterator[tuple[TestClient, Settings]]:
    scoped = settings.model_copy(update={"FILE_STORAGE_ROOT": str(tmp_path)})
    asyncio.run(_reset(scoped))
    asyncio.run(_add_user(scoped))
    with TestClient(create_application(scoped), raise_server_exceptions=False) as client:
        yield client, scoped


@pytest.mark.integration
def test_profile_update_and_preferences_merge(settings_client: tuple[TestClient, Settings]) -> None:
    client, _ = settings_client
    _login(client)

    resp = client.patch(
        "/auth/me",
        headers=_csrf(client),
        json={
            "display_name": "Mahmoud Almbaidin",
            "job_title": "CEO",
            "department": "Executive",
            "phone": "+966500000000",
            "locale": "en-US",
            "timezone": "Asia/Riyadh",
            "preferences": {"theme": "dark", "density": "compact"},
        },
    )
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["display_name"] == "Mahmoud Almbaidin"
    assert user["job_title"] == "CEO"
    assert user["timezone"] == "Asia/Riyadh"
    assert user["preferences"] == {"theme": "dark", "density": "compact"}

    # A partial preferences update MERGES rather than replaces.
    resp2 = client.patch(
        "/auth/me", headers=_csrf(client), json={"preferences": {"density": "comfortable"}}
    )
    assert resp2.status_code == 200
    prefs = resp2.json()["user"]["preferences"]
    assert prefs == {"theme": "dark", "density": "comfortable"}

    # Persistence survives a fresh read.
    me = client.get("/auth/me")
    assert me.json()["user"]["job_title"] == "CEO"
    assert me.json()["user"]["preferences"]["theme"] == "dark"


@pytest.mark.integration
def test_nested_group_preferences_persist_and_merge(
    settings_client: tuple[TestClient, Settings],
) -> None:
    """Notification-style grouped preferences (a flat object) persist and merge
    without clobbering unrelated top-level preferences (BUG-NOTIF-002)."""
    client, _ = settings_client
    _login(client)
    # Save appearance + a grouped notifications object.
    first = client.patch(
        "/auth/me",
        headers=_csrf(client),
        json={
            "preferences": {"theme": "dark", "notifications": {"Pipelines": False, "System": True}}
        },
    )
    assert first.status_code == 200, first.text
    prefs = first.json()["user"]["preferences"]
    assert prefs["notifications"] == {"Pipelines": False, "System": True}

    # A later notifications-only save replaces that group but keeps theme intact.
    second = client.patch(
        "/auth/me",
        headers=_csrf(client),
        json={"preferences": {"notifications": {"Pipelines": True, "Marketplace": True}}},
    )
    assert second.status_code == 200
    prefs2 = second.json()["user"]["preferences"]
    assert prefs2["theme"] == "dark"  # untouched
    assert prefs2["notifications"] == {"Pipelines": True, "Marketplace": True}

    # Survives a fresh read (i.e. refresh / re-login).
    reread = client.get("/auth/me").json()["user"]["preferences"]
    assert reread["notifications"]["Pipelines"] is True

    # Deep nesting is still rejected.
    assert (
        client.patch(
            "/auth/me", headers=_csrf(client), json={"preferences": {"x": {"y": {"z": 1}}}}
        ).status_code
        == 422
    )


@pytest.mark.integration
def test_new_user_preferences_default_to_empty_bag(
    settings_client: tuple[TestClient, Settings],
) -> None:
    """A user who has never saved preferences reads back an empty bag (the
    documented server-authoritative default), never another user's values."""
    client, _ = settings_client
    _login(client)
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["preferences"] == {}


@pytest.mark.integration
def test_notification_preferences_are_user_scoped(
    settings_client: tuple[TestClient, Settings],
) -> None:
    """Personal notification preferences are scoped to the authenticated user:
    one user saving must never read or mutate another user's preferences (the
    endpoint derives identity from the session, never a client-supplied id)."""
    client, scoped = settings_client
    # User A saves a notification preference set.
    _login(client)
    saved_a = client.patch(
        "/auth/me",
        headers=_csrf(client),
        json={"preferences": {"notifications": {"Pipelines": False, "System": True}}},
    )
    assert saved_a.status_code == 200, saved_a.text

    # A genuinely different user B.
    other_email = "second-user@veltrix.local"
    asyncio.run(_add_user(scoped, username="second-user", email=other_email))
    with TestClient(create_application(scoped), raise_server_exceptions=False) as other:
        _login(other, email=other_email)
        # B does NOT inherit A's preferences.
        assert other.get("/auth/me").json()["user"]["preferences"] == {}
        # B saves its own, different preferences.
        saved_b = other.patch(
            "/auth/me",
            headers=_csrf(other),
            json={"preferences": {"notifications": {"Pipelines": True, "Marketplace": True}}},
        )
        assert saved_b.status_code == 200
        assert saved_b.json()["user"]["preferences"]["notifications"] == {
            "Pipelines": True,
            "Marketplace": True,
        }

    # A's preferences are completely unaffected by B's write.
    reread_a = client.get("/auth/me").json()["user"]["preferences"]
    assert reread_a["notifications"] == {"Pipelines": False, "System": True}


@pytest.mark.integration
def test_preferences_require_authentication(
    settings_client: tuple[TestClient, Settings],
) -> None:
    """Unauthenticated callers can neither read nor modify preferences: with no
    session cookie, both the bootstrap read and the profile write are rejected."""
    client, _ = settings_client
    # No login → no session (and no CSRF) cookie has been issued.
    assert client.get("/auth/me").status_code == 401
    blocked = client.patch("/auth/me", json={"preferences": {"notifications": {"Pipelines": True}}})
    assert blocked.status_code in (401, 403)


@pytest.mark.integration
def test_profile_rejects_unknown_timezone_and_extra_fields(
    settings_client: tuple[TestClient, Settings],
) -> None:
    client, _ = settings_client
    _login(client)
    assert (
        client.patch(
            "/auth/me", headers=_csrf(client), json={"timezone": "Middle/Nowhere"}
        ).status_code
        == 422
    )
    # username/email/status are system-managed: extra="forbid" rejects them.
    assert (
        client.patch(
            "/auth/me", headers=_csrf(client), json={"email": "attacker@evil.test"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/auth/me", headers=_csrf(client), json={"username": "someoneelse"}
        ).status_code
        == 422
    )


@pytest.mark.integration
def test_profile_update_requires_csrf(settings_client: tuple[TestClient, Settings]) -> None:
    client, _ = settings_client
    _login(client)
    assert client.patch("/auth/me", json={"job_title": "x"}).status_code == 403


@pytest.mark.integration
def test_session_list_marks_current_and_revokes_others(
    settings_client: tuple[TestClient, Settings],
) -> None:
    client, scoped = settings_client
    _login(client)
    listing = client.get("/auth/sessions")
    assert listing.status_code == 200
    body = listing.json()
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["current"] is True

    # A second, independent client establishes a second session for the user.
    with TestClient(create_application(scoped), raise_server_exceptions=False) as other:
        _login(other)
        assert other.get("/auth/me").status_code == 200
        assert len(client.get("/auth/sessions").json()["sessions"]) == 2

        revoked = client.post("/auth/sessions/revoke-others", headers=_csrf(client))
        assert revoked.status_code == 200
        assert revoked.json()["revoked"] == 1
        # The other session is now dead; the current one still works.
        assert other.get("/auth/me").status_code == 401
        assert client.get("/auth/me").status_code == 200
        assert len(client.get("/auth/sessions").json()["sessions"]) == 1


@pytest.mark.integration
def test_cannot_revoke_foreign_session(settings_client: tuple[TestClient, Settings]) -> None:
    client, scoped = settings_client
    _login(client)
    # A genuinely DIFFERENT user owns the foreign session.
    other_email = "second-user@veltrix.local"
    asyncio.run(_add_user(scoped, username="second-user", email=other_email))
    with TestClient(create_application(scoped), raise_server_exceptions=False) as other:
        _login(other, email=other_email)
        foreign_id = other.get("/auth/sessions").json()["current_session_id"]
        # The first user must not be able to revoke another user's session (IDOR).
        resp = client.delete(f"/auth/sessions/{foreign_id}", headers=_csrf(client))
        assert resp.status_code == 404
        assert other.get("/auth/me").status_code == 200  # untouched


@pytest.mark.integration
def test_avatar_upload_serve_and_remove(settings_client: tuple[TestClient, Settings]) -> None:
    client, _ = settings_client
    _login(client)

    upload = client.post(
        "/auth/me/avatar",
        headers={**_csrf(client), "X-File-Name": "avatar.png", "Content-Type": "image/png"},
        content=_png_bytes(),
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["user"]["avatar_url"] == "/api/v1/auth/me/avatar"

    served = client.get("/auth/me/avatar")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content[:8] == b"\x89PNG\r\n\x1a\n"

    removed = client.delete("/auth/me/avatar", headers=_csrf(client))
    assert removed.status_code == 200
    assert removed.json()["user"]["avatar_url"] is None
    assert client.get("/auth/me/avatar").status_code == 404


@pytest.mark.integration
def test_avatar_rejects_disguised_non_image(
    settings_client: tuple[TestClient, Settings],
) -> None:
    client, _ = settings_client
    _login(client)
    # A text payload masquerading as a PNG fails the magic-byte signature check.
    resp = client.post(
        "/auth/me/avatar",
        headers={**_csrf(client), "X-File-Name": "evil.png", "Content-Type": "image/png"},
        content=b"#!/bin/sh\nrm -rf /\n",
    )
    assert resp.status_code in (400, 415, 422)
    assert client.get("/auth/me/avatar").status_code == 404
