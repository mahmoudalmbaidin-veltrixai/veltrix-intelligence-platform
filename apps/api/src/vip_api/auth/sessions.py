"""Revocable opaque-session lifecycle and refresh rotation."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import AuthSession, User, UserStatus, utc_now
from vip_api.auth.tokens import SessionTokens, generate_session_tokens, hash_token
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError


def authentication_error(code: str = "AUTHENTICATION_REQUIRED") -> ApplicationError:
    return ApplicationError(code=code, message="Authentication is required.", status_code=401)


def ensure_active_user(user: User) -> None:
    if user.status is not UserStatus.ACTIVE or user.deleted_at is not None:
        raise authentication_error("ACCOUNT_INACTIVE")


def session_idle(session: AuthSession, settings: Settings) -> bool:
    return (
        session.last_seen_at + timedelta(minutes=settings.AUTH_SESSION_IDLE_TTL_MINUTES)
        <= utc_now()
    )


async def create_session(
    db: AsyncSession,
    user: User,
    settings: Settings,
    *,
    rotated_from: UUID | None = None,
    user_agent: str | None = None,
) -> tuple[AuthSession, SessionTokens]:
    now = utc_now()
    tokens = generate_session_tokens()
    auth_session = AuthSession(
        user_id=user.id,
        access_token_hash=hash_token(tokens.access, "access"),
        refresh_token_hash=hash_token(tokens.refresh, "refresh"),
        csrf_token_hash=hash_token(tokens.csrf, "csrf"),
        access_expires_at=now + timedelta(minutes=settings.AUTH_ACCESS_SESSION_TTL_MINUTES),
        refresh_expires_at=now + timedelta(days=settings.AUTH_REFRESH_SESSION_TTL_DAYS),
        last_seen_at=now,
        user_agent=(user_agent or None) and user_agent[:512],
        rotated_from_session_id=rotated_from,
    )
    db.add(auth_session)
    await db.flush()

    active = (
        await db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.refresh_expires_at > now,
            )
            .order_by(AuthSession.created_at.desc())
        )
    ).all()
    for stale in active[settings.AUTH_MAX_ACTIVE_SESSIONS_PER_USER :]:
        stale.revoked_at = now
        stale.revocation_reason = "maximum_sessions_exceeded"
    return auth_session, tokens


async def find_access_session(db: AsyncSession, token: str) -> AuthSession | None:
    return cast(
        AuthSession | None,
        await db.scalar(
            select(AuthSession).where(AuthSession.access_token_hash == hash_token(token, "access"))
        ),
    )


async def find_refresh_session(
    db: AsyncSession, token: str, *, for_update: bool = False
) -> AuthSession | None:
    statement = select(AuthSession).where(
        AuthSession.refresh_token_hash == hash_token(token, "refresh")
    )
    if for_update:
        statement = statement.with_for_update()
    return cast(AuthSession | None, await db.scalar(statement))


async def load_user(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def revoke_session(session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = utc_now()
        session.revocation_reason = reason


async def revoke_session_by_id(db: AsyncSession, session_id: UUID, reason: str) -> bool:
    session = await db.get(AuthSession, session_id)
    if session is None:
        return False
    await revoke_session(session, reason)
    return True


async def revoke_all_user_sessions(db: AsyncSession, user_id: UUID, reason: str) -> int:
    result = cast(
        CursorResult[Any],
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utc_now(), revocation_reason=reason)
        ),
    )
    return int(result.rowcount or 0)


async def revoke_session_chain(db: AsyncSession, session: AuthSession) -> None:
    pending = [session.id]
    seen: set[UUID] = set()
    now = utc_now()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        child_ids = list(
            await db.scalars(
                select(AuthSession.id).where(AuthSession.rotated_from_session_id == current)
            )
        )
        pending.extend(child_ids)
    await db.execute(
        update(AuthSession)
        .where(AuthSession.id.in_(seen))
        .values(revoked_at=now, revocation_reason="refresh_token_reuse")
    )


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    result = cast(
        CursorResult[Any],
        await db.execute(delete(AuthSession).where(AuthSession.refresh_expires_at <= utc_now())),
    )
    return int(result.rowcount or 0)


async def active_session_count(db: AsyncSession, user_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.refresh_expires_at > utc_now(),
            )
        )
        or 0
    )
