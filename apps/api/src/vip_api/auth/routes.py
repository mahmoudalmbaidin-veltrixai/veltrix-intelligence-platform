"""Cookie-based authentication endpoints."""

from __future__ import annotations

import logging
from datetime import timedelta
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from vip_api.auth.authentication import authenticate_login
from vip_api.auth.avatar import delete_avatar, read_avatar, store_avatar
from vip_api.auth.cookies import clear_auth_cookies, set_auth_cookies
from vip_api.auth.csrf import validate_csrf
from vip_api.auth.dependencies import AuthenticatedContext, get_current_session, require_csrf
from vip_api.auth.email import send_password_reset_email
from vip_api.auth.models import AuthSession, User, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.password_reset import (
    change_password as change_password_service,
)
from vip_api.auth.password_reset import (
    consume_password_reset,
    request_password_reset,
)
from vip_api.auth.rate_limit import login_rate_limited, password_reset_rate_limited
from vip_api.auth.sessions import (
    authentication_error,
    create_session,
    ensure_active_user,
    find_access_session,
    find_refresh_session,
    load_user,
    revoke_session,
    revoke_session_chain,
    session_idle,
)
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.governance.audit import record_audit
from vip_api.redis.client import RedisClient
from vip_api.schemas.auth import (
    AuthenticatedUser,
    AuthenticationResponse,
    ChangePasswordRequest,
    GenericAcceptedResponse,
    LoginRequest,
    LogoutResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdateRequest,
    RevokeSessionsResponse,
    SessionInfo,
    SessionListResponse,
    SessionSummary,
)
from vip_api.schemas.error import ErrorResponse

logger = logging.getLogger("vip_api.security")
router = APIRouter(prefix="/auth", tags=["authentication"])


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_password_service(request: Request) -> PasswordService:
    service: PasswordService = request.app.state.password_service
    return service


def get_redis(request: Request) -> RedisClient:
    redis_client: RedisClient = request.app.state.redis
    return redis_client


def auth_response(user: User, session: AuthSession, settings: Settings) -> AuthenticationResponse:
    idle_ttl = settings.AUTH_SESSION_IDLE_TTL_MINUTES
    return AuthenticationResponse(
        user=AuthenticatedUser.from_user(user),
        session=SessionInfo(
            expires_at=session.access_expires_at,
            idle_expires_at=session.last_seen_at + timedelta(minutes=idle_ttl),
            idle_timeout_minutes=idle_ttl,
            warning_minutes=settings.AUTH_SESSION_IDLE_WARNING_MINUTES,
        ),
    )


@router.post(
    "/login",
    response_model=AuthenticationResponse,
    summary="Create an authenticated session",
    description=(
        "Validates email/password credentials and sets opaque access and refresh HttpOnly cookies "
        "plus a readable CSRF cookie. Raw session values are never returned in JSON."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials or inactive account"},
        422: {"model": ErrorResponse, "description": "Invalid request"},
        429: {"model": ErrorResponse, "description": "Login rate limit exceeded"},
    },
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
    redis_client: Annotated[RedisClient, Depends(get_redis)],
) -> AuthenticationResponse:
    client_identifier = request.client.host if request.client else "unknown"
    if await login_rate_limited(redis_client, client_identifier, settings):
        raise ApplicationError(
            code="TOO_MANY_LOGIN_ATTEMPTS",
            message="Too many login attempts. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    user, auth_session, tokens = await authenticate_login(
        db,
        payload.identifier,
        payload.password,
        settings,
        password_service,
        user_agent=request.headers.get("user-agent"),
    )
    set_auth_cookies(response, tokens, settings)
    return auth_response(user, auth_session, settings)


@router.get(
    "/me",
    response_model=AuthenticationResponse,
    summary="Bootstrap the current session",
    description=(
        "Reads the access-session HttpOnly cookie and returns the safe user and access expiry. "
        "This endpoint never refreshes a session automatically."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Session missing, expired, or revoked"}
    },
)
async def me(
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationResponse:
    return auth_response(context.user, context.session, settings)


@router.post(
    "/session/activity",
    response_model=AuthenticationResponse,
    dependencies=[Depends(require_csrf)],
    summary="Record genuine user activity and renew the idle window",
    description=(
        "Called by the client on real user interaction (throttled) and by the "
        "'Stay signed in' action. Refreshes the sliding idle deadline ONLY if the "
        "session is still valid; an already idle/revoked session is rejected so the "
        "user is routed to sign-in. This is the single endpoint that extends idle "
        "time — background traffic never does."
    ),
    responses={403: {"model": ErrorResponse, "description": "CSRF validation failed"}},
)
async def session_activity(
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationResponse:
    context.session.last_seen_at = utc_now()
    await db.commit()
    return auth_response(context.user, context.session, settings)


@router.patch(
    "/me",
    response_model=AuthenticationResponse,
    dependencies=[Depends(require_csrf)],
    summary="Update the signed-in user's own profile and preferences",
    description=(
        "Self-service update of personal profile fields (display name, job title, department, "
        "phone, locale, time zone) and the UI preferences bag. Username, email and status are "
        "administrator/system managed and cannot be changed here."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "CSRF validation failed"},
        422: {"model": ErrorResponse, "description": "Invalid profile fields"},
    },
)
async def update_me(
    payload: ProfileUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationResponse:
    user = context.user
    fields = payload.model_dump(exclude_unset=True)
    # Empty strings clear an optional field; preferences are shallow-merged so a
    # partial update never drops unrelated preference keys.
    changed: list[str] = []
    for name in ("display_name", "job_title", "department", "phone", "locale", "timezone"):
        if name not in fields:
            continue
        value = fields[name]
        if name == "display_name":
            if not value or not str(value).strip():
                continue  # display name cannot be blanked
            value = str(value).strip()
        elif isinstance(value, str) and value.strip() == "":
            value = None
        setattr(user, name, value)
        changed.append(name)
    if "preferences" in fields and fields["preferences"] is not None:
        merged = dict(user.preferences or {})
        merged.update(fields["preferences"])
        user.preferences = merged
        changed.append("preferences")
    if changed:
        user.updated_by = user.id
        await record_audit(
            db,
            "auth.profile_updated",
            actor_user_id=user.id,
            organization_id=None,
            resource_type="user",
            resource_id=user.id,
            metadata={"fields": sorted(changed)},
            commit=False,
        )
        await db.commit()
        await db.refresh(user)
    return auth_response(user, context.session, settings)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List the signed-in user's active sessions",
    description=(
        "Returns the caller's own non-revoked, non-expired sessions with timestamps and a "
        "current-session marker. Sessions store no device or location metadata, so only "
        "timing information is available."
    ),
)
async def list_sessions(
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SessionListResponse:
    now = utc_now()
    rows = (
        await db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == context.user.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.refresh_expires_at > now,
            )
            .order_by(AuthSession.last_seen_at.desc())
        )
    ).all()
    summaries = [
        SessionSummary(
            id=item.id,
            created_at=item.created_at,
            last_seen_at=item.last_seen_at,
            access_expires_at=item.access_expires_at,
            refresh_expires_at=item.refresh_expires_at,
            current=item.id == context.session.id,
            user_agent=item.user_agent,
        )
        for item in rows
    ]
    return SessionListResponse(sessions=summaries, current_session_id=context.session.id)


@router.delete(
    "/sessions/{session_id}",
    response_model=RevokeSessionsResponse,
    dependencies=[Depends(require_csrf)],
    summary="Revoke one of the signed-in user's sessions",
    description=(
        "Revokes a single session owned by the caller. A session belonging to another user is "
        "never revealed or affected (returns not-found)."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "CSRF validation failed"},
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
)
async def revoke_session_route(
    session_id: UUID,
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RevokeSessionsResponse:
    target = await db.get(AuthSession, session_id)
    # Ownership check prevents cross-user session tampering / IDOR. A missing or
    # foreign session is reported identically so existence is not disclosed.
    if target is None or target.user_id != context.user.id or target.revoked_at is not None:
        raise ApplicationError(
            code="NOT_FOUND", message="The session was not found.", status_code=404
        )
    await revoke_session(target, "user_revoked")
    await record_audit(
        db,
        "auth.session_revoked",
        actor_user_id=context.user.id,
        organization_id=None,
        resource_type="auth_session",
        resource_id=target.id,
        commit=False,
    )
    await db.commit()
    return RevokeSessionsResponse(revoked=1)


@router.post(
    "/sessions/revoke-others",
    response_model=RevokeSessionsResponse,
    dependencies=[Depends(require_csrf)],
    summary="Sign out all other sessions",
    description="Revokes every active session for the caller except the current one.",
    responses={403: {"model": ErrorResponse, "description": "CSRF validation failed"}},
)
async def revoke_other_sessions_route(
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RevokeSessionsResponse:
    now = utc_now()
    others = (
        await db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == context.user.id,
                AuthSession.id != context.session.id,
                AuthSession.revoked_at.is_(None),
            )
        )
    ).all()
    for item in others:
        await revoke_session(item, "user_revoked_others")
    if others:
        await record_audit(
            db,
            "auth.session_revoked",
            actor_user_id=context.user.id,
            organization_id=None,
            resource_type="user",
            resource_id=context.user.id,
            metadata={"scope": "others", "count": len(others), "at": now.isoformat()},
            commit=False,
        )
    await db.commit()
    return RevokeSessionsResponse(revoked=len(others))


@router.post(
    "/me/avatar",
    response_model=AuthenticationResponse,
    dependencies=[Depends(require_csrf)],
    summary="Upload the signed-in user's avatar",
    description=(
        "Accepts a PNG or JPEG image, validated by extension, declared MIME type, and magic-byte "
        "signature, and stored under a per-user key. Only the formats the platform can verify are "
        "accepted."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "CSRF validation failed"},
        413: {"model": ErrorResponse, "description": "Image too large"},
        415: {"model": ErrorResponse, "description": "Unsupported image type"},
    },
)
async def upload_avatar(
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    filename: Annotated[str, Header(alias="X-File-Name", min_length=1, max_length=255)],
    content_type: Annotated[str, Header(alias="Content-Type")],
) -> AuthenticationResponse:
    await store_avatar(request.stream(), filename, content_type, context.user, settings)
    await record_audit(
        db,
        "auth.avatar_updated",
        actor_user_id=context.user.id,
        organization_id=None,
        resource_type="user",
        resource_id=context.user.id,
        commit=False,
    )
    await db.commit()
    await db.refresh(context.user)
    return auth_response(context.user, context.session, settings)


@router.get(
    "/me/avatar",
    summary="Stream the signed-in user's avatar",
    description="Streams the caller's stored avatar image, or 404 when none is set.",
    responses={404: {"model": ErrorResponse, "description": "No avatar set"}},
)
async def get_avatar(
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    result = await read_avatar(context.user, settings)
    if result is None:
        raise ApplicationError(code="NOT_FOUND", message="No avatar is set.", status_code=404)
    stream, content_type = result
    return StreamingResponse(
        stream,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=0, must-revalidate"},
    )


@router.delete(
    "/me/avatar",
    response_model=AuthenticationResponse,
    dependencies=[Depends(require_csrf)],
    summary="Remove the signed-in user's avatar",
    responses={403: {"model": ErrorResponse, "description": "CSRF validation failed"}},
)
async def remove_avatar(
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationResponse:
    removed = await delete_avatar(context.user, settings)
    if removed:
        await record_audit(
            db,
            "auth.avatar_removed",
            actor_user_id=context.user.id,
            organization_id=None,
            resource_type="user",
            resource_id=context.user.id,
            commit=False,
        )
    await db.commit()
    await db.refresh(context.user)
    return auth_response(context.user, context.session, settings)


@router.post(
    "/refresh",
    response_model=AuthenticationResponse,
    summary="Rotate the current session",
    description=(
        "Requires the refresh HttpOnly cookie and matching CSRF cookie/header proof. Rotates all "
        "session and CSRF values and invalidates the previous refresh value."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Refresh session invalid or expired"},
        403: {"model": ErrorResponse, "description": "CSRF validation failed"},
    },
)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationResponse:
    refresh_token = request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise authentication_error("INVALID_REFRESH_SESSION")
    old_session = await find_refresh_session(db, refresh_token, for_update=True)
    if old_session is None:
        raise authentication_error("INVALID_REFRESH_SESSION")
    validate_csrf(request, old_session, settings)
    if old_session.revoked_at is not None:
        await revoke_session_chain(db, old_session)
        await db.commit()
        logger.warning(
            "Refresh token reuse detected",
            extra={
                "security_event": "refresh_reuse",
                "outcome": "revoked",
                "session_id": str(old_session.id),
            },
        )
        raise authentication_error("INVALID_REFRESH_SESSION")
    if old_session.refresh_expires_at <= utc_now() or session_idle(old_session, settings):
        await revoke_session(old_session, "expired")
        await db.commit()
        raise authentication_error("INVALID_REFRESH_SESSION")
    user = await load_user(db, old_session.user_id)
    if user is None:
        raise authentication_error("INVALID_REFRESH_SESSION")
    ensure_active_user(user)
    await revoke_session(old_session, "rotated")
    new_session, tokens = await create_session(
        db,
        user,
        settings,
        rotated_from=old_session.id,
        user_agent=request.headers.get("user-agent") or old_session.user_agent,
    )
    await db.commit()
    set_auth_cookies(response, tokens, settings)
    logger.info(
        "Session refreshed",
        extra={
            "security_event": "refresh_success",
            "outcome": "success",
            "user_id": str(user.id),
            "session_id": str(new_session.id),
        },
    )
    return auth_response(user, new_session, settings)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke the current session",
    description=(
        "Revokes an identifiable session and clears all authentication cookies. CSRF proof is "
        "required when a session is present; an already-absent session remains idempotent."
    ),
    responses={403: {"model": ErrorResponse, "description": "CSRF validation failed"}},
)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LogoutResponse:
    access_token = request.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    refresh_token = request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    auth_session: AuthSession | None = None
    if access_token:
        auth_session = await find_access_session(db, access_token)
    if auth_session is None and refresh_token:
        auth_session = await find_refresh_session(db, refresh_token)
    if auth_session is not None:
        validate_csrf(request, auth_session, settings)
        await revoke_session(auth_session, "logout")
        await db.commit()
        logger.info(
            "Session logged out",
            extra={
                "security_event": "logout",
                "outcome": "success",
                "session_id": str(auth_session.id),
            },
        )
    clear_auth_cookies(response, settings)
    return LogoutResponse()


@router.post(
    "/password-reset/request",
    response_model=GenericAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password-reset link",
    description=(
        "Accepts a username or email and always returns the same accepted response so account "
        "existence is never disclosed. When a match exists an email with a single-use, "
        "time-limited reset link is delivered via the configured provider."
    ),
)
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[RedisClient, Depends(get_redis)],
) -> GenericAcceptedResponse:
    client_ip = request.client.host if request.client else "unknown"
    scope = f"{client_ip}:{payload.identifier.strip().lower()}"
    if await password_reset_rate_limited(redis_client, scope, settings):
        raise ApplicationError(
            code="TOO_MANY_REQUESTS",
            message="Too many requests. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    ip_hash = sha256(client_ip.encode()).hexdigest()
    result = await request_password_reset(
        db, payload.identifier, settings, requested_ip_hash=ip_hash
    )
    if result is not None:
        token, user = result
        await record_audit(
            db,
            "auth.password_reset.requested",
            actor_user_id=user.id,
            organization_id=None,
            resource_type="user",
            resource_id=user.id,
            commit=True,
        )
        if user.email:
            reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
            await send_password_reset_email(settings, user.email, reset_url)
    return GenericAcceptedResponse()


@router.post(
    "/password-reset/confirm",
    response_model=GenericAcceptedResponse,
    summary="Complete a password reset",
    description=(
        "Consumes a single-use reset token and sets a new password. The token is validated by "
        "hash, purpose, and expiry; all of the account's sessions are revoked on success."
    ),
    responses={400: {"model": ErrorResponse, "description": "Invalid or expired reset token"}},
)
async def password_reset_confirm(
    payload: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> GenericAcceptedResponse:
    user = await consume_password_reset(db, payload.token, payload.new_password, password_service)
    await record_audit(
        db,
        "auth.password_reset.completed",
        actor_user_id=user.id,
        organization_id=None,
        resource_type="user",
        resource_id=user.id,
        commit=True,
    )
    logger.info(
        "Password reset completed",
        extra={"security_event": "password_reset_completed", "outcome": "success"},
    )
    return GenericAcceptedResponse()


@router.post(
    "/change-password",
    response_model=GenericAcceptedResponse,
    dependencies=[Depends(require_csrf)],
    summary="Change the signed-in user's password",
    description=(
        "Verifies the current password, applies the new one, clears any forced-change flag, and "
        "revokes every session so the new credential must be used to sign back in."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Current password incorrect or policy failed"},
        403: {"model": ErrorResponse, "description": "CSRF validation failed"},
    },
)
async def change_password_route(
    payload: ChangePasswordRequest,
    context: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> GenericAcceptedResponse:
    user = await change_password_service(
        db,
        context.user.id,
        payload.current_password,
        payload.new_password,
        password_service,
    )
    await record_audit(
        db,
        "auth.password_changed",
        actor_user_id=user.id,
        organization_id=None,
        resource_type="user",
        resource_id=user.id,
        commit=True,
    )
    logger.info(
        "Password changed",
        extra={"security_event": "password_changed", "outcome": "success"},
    )
    return GenericAcceptedResponse()
