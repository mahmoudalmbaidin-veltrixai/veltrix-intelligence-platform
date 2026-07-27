"""Transactional login and session authentication operations."""

import logging
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import AuthSession, User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.sessions import create_session, revoke_all_user_sessions
from vip_api.auth.tokens import SessionTokens
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError

logger = logging.getLogger("vip_api.security")


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def invalid_credentials() -> ApplicationError:
    return ApplicationError(
        code="INVALID_CREDENTIALS", message="Invalid username or password.", status_code=401
    )


async def authenticate_login(
    db: AsyncSession,
    identifier: str,
    password: str,
    settings: Settings,
    password_service: PasswordService,
) -> tuple[User, AuthSession, SessionTokens]:
    now = utc_now()
    # Accept the username (primary) or the email (legacy) as the login identifier.
    normalized = identifier.strip().casefold()
    user = await db.scalar(
        select(User)
        .where(
            or_(
                User.normalized_username == normalized,
                User.normalized_email == normalized,
            )
        )
        .with_for_update()
    )
    if user is None:
        password_service.verify_unknown_user(password)
        logger.info("Login failed", extra={"security_event": "login_failure", "outcome": "denied"})
        raise invalid_credentials()

    if user.status is UserStatus.LOCKED and user.locked_until and user.locked_until <= now:
        user.status = UserStatus.ACTIVE
        user.locked_until = None
        user.failed_login_count = 0

    if user.status is UserStatus.LOCKED:
        await db.commit()
        logger.info(
            "Login denied for locked account",
            extra={
                "security_event": "login_failure",
                "outcome": "locked",
                "user_id": str(user.id),
            },
        )
        raise invalid_credentials()
    if user.status is not UserStatus.ACTIVE or user.deleted_at is not None:
        await db.commit()
        logger.info(
            "Login denied for inactive account",
            extra={
                "security_event": "login_failure",
                "outcome": "inactive",
                "user_id": str(user.id),
            },
        )
        raise invalid_credentials()

    if not password_service.verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.AUTH_MAX_FAILED_LOGIN_ATTEMPTS:
            user.status = UserStatus.LOCKED
            user.locked_until = now + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
            await revoke_all_user_sessions(db, user.id, "account_locked")
            logger.warning(
                "Account temporarily locked",
                extra={
                    "security_event": "account_lockout",
                    "outcome": "locked",
                    "user_id": str(user.id),
                },
            )
        await db.commit()
        raise invalid_credentials()

    if password_service.needs_rehash(user.password_hash):
        user.password_hash = password_service.hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    auth_session, tokens = await create_session(db, user, settings)
    await db.commit()
    logger.info(
        "Login succeeded",
        extra={
            "security_event": "login_success",
            "outcome": "success",
            "user_id": str(user.id),
            "session_id": str(auth_session.id),
        },
    )
    return user, auth_session, tokens
