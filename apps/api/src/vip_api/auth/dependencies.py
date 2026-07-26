"""Reusable typed dependencies for authenticated users and sessions."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.csrf import validate_csrf
from vip_api.auth.models import AuthSession, User, utc_now
from vip_api.auth.sessions import (
    authentication_error,
    ensure_active_user,
    find_access_session,
    load_user,
    session_idle,
)
from vip_api.core.config import Settings
from vip_api.database.session import get_db_session


@dataclass(frozen=True, slots=True)
class AuthenticatedContext:
    user: User
    session: AuthSession


async def get_current_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthenticatedContext:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    if not token:
        raise authentication_error()
    auth_session = await find_access_session(db, token)
    now = utc_now()
    if auth_session is None or auth_session.revoked_at is not None:
        raise authentication_error("SESSION_REVOKED")
    if auth_session.access_expires_at <= now or session_idle(auth_session, settings):
        raise authentication_error("SESSION_EXPIRED")
    user = await load_user(db, auth_session.user_id)
    if user is None:
        raise authentication_error()
    ensure_active_user(user)
    if auth_session.last_seen_at + timedelta(minutes=5) <= now:
        auth_session.last_seen_at = now
        await db.commit()
    return AuthenticatedContext(user=user, session=auth_session)


async def get_current_user(
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
) -> User:
    return context.user


require_authenticated_user = get_current_user


async def require_csrf(
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
) -> None:
    settings: Settings = request.app.state.settings
    validate_csrf(request, context.session, settings)
