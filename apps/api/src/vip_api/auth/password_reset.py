"""One-time password-reset token and password-change foundation."""

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.authentication import normalize_email
from vip_api.auth.models import PasswordResetToken, User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.sessions import revoke_all_user_sessions
from vip_api.auth.tokens import generate_token, hash_token
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError


async def request_password_reset(
    db: AsyncSession,
    email: str,
    settings: Settings,
    requested_ip_hash: str | None = None,
) -> str | None:
    user = await db.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    if user is None or user.status not in {UserStatus.ACTIVE, UserStatus.LOCKED}:
        return None
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=utc_now())
    )
    token = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token, "password-reset"),
            expires_at=utc_now() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES),
            requested_ip_hash=requested_ip_hash,
        )
    )
    await db.commit()
    return token


async def consume_password_reset(
    db: AsyncSession,
    token: str,
    new_password: str,
    password_service: PasswordService,
) -> User:
    password_service.validate_password(new_password)
    reset = await db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(token, "password-reset"))
        .with_for_update()
    )
    if reset is None or reset.used_at is not None:
        raise ApplicationError(
            code="PASSWORD_RESET_TOKEN_INVALID",
            message="The reset token is invalid.",
            status_code=400,
        )
    if reset.expires_at <= utc_now():
        raise ApplicationError(
            code="PASSWORD_RESET_TOKEN_EXPIRED",
            message="The reset token has expired.",
            status_code=400,
        )
    user = await db.get(User, reset.user_id, with_for_update=True)
    if user is None or user.status not in {UserStatus.ACTIVE, UserStatus.LOCKED}:
        raise ApplicationError(
            code="PASSWORD_RESET_TOKEN_INVALID",
            message="The reset token is invalid.",
            status_code=400,
        )
    now = utc_now()
    user.password_hash = password_service.hash_password(new_password)
    user.password_changed_at = now
    user.failed_login_count = 0
    user.locked_until = None
    user.status = UserStatus.ACTIVE
    reset.used_at = now
    await revoke_all_user_sessions(db, user.id, "password_changed")
    await db.commit()
    return user
