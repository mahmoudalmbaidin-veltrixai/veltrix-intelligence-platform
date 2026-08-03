"""One-time password-reset token and password-change foundation."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.authentication import normalize_email
from vip_api.auth.models import PasswordResetToken, User, UserStatus, normalize_username, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.sessions import revoke_all_user_sessions
from vip_api.auth.tokens import generate_token, hash_token
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError


def _validate_new_password(password_service: PasswordService, new_password: str) -> None:
    """Translate the password-policy check into a client-facing 422 (never a 500)."""
    try:
        password_service.validate_password(new_password)
    except ValueError as exc:
        raise ApplicationError(code="PASSWORD_POLICY", message=str(exc), status_code=422) from exc


async def request_password_reset(
    db: AsyncSession,
    identifier: str,
    settings: Settings,
    requested_ip_hash: str | None = None,
) -> tuple[str, User] | None:
    """Issue a single-use reset token for the user matching ``identifier``.

    ``identifier`` may be a username or an email. Returns ``(token, user)`` on
    success or ``None`` when no eligible account matches — the caller must return
    an identical response in both cases so account existence is never disclosed.
    """
    identifier = identifier.strip()
    user = await db.scalar(
        select(User).where(
            or_(
                User.normalized_username == normalize_username(identifier),
                User.normalized_email == normalize_email(identifier),
            )
        )
    )
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
    return token, user


async def consume_password_reset(
    db: AsyncSession,
    token: str,
    new_password: str,
    password_service: PasswordService,
) -> User:
    _validate_new_password(password_service, new_password)
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
    # A completed reset also satisfies any forced-change requirement.
    user.must_change_password = False
    reset.used_at = now
    await revoke_all_user_sessions(db, user.id, "password_changed")
    await db.commit()
    return user


async def change_password(
    db: AsyncSession,
    user_id: UUID,
    current_password: str,
    new_password: str,
    password_service: PasswordService,
) -> User:
    """Change a signed-in user's password after verifying the current one.

    Clears ``must_change_password`` and revokes every session (the caller included)
    so the new credential must be used to sign back in. Suspended users are refused.
    """
    _validate_new_password(password_service, new_password)
    user = await db.get(User, user_id, with_for_update=True)
    if user is None or user.status not in {UserStatus.ACTIVE, UserStatus.LOCKED}:
        raise ApplicationError(
            code="INVALID_CREDENTIALS",
            message="The current password is incorrect.",
            status_code=400,
        )
    if not password_service.verify_password(current_password, user.password_hash):
        raise ApplicationError(
            code="INVALID_CREDENTIALS",
            message="The current password is incorrect.",
            status_code=400,
        )
    now = utc_now()
    user.password_hash = password_service.hash_password(new_password)
    user.password_changed_at = now
    user.failed_login_count = 0
    user.locked_until = None
    user.status = UserStatus.ACTIVE
    user.must_change_password = False
    await revoke_all_user_sessions(db, user.id, "password_changed")
    await db.commit()
    return user
