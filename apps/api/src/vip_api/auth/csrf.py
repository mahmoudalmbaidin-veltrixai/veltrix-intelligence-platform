"""Session-bound double-submit CSRF validation."""

from hmac import compare_digest

from fastapi import Request

from vip_api.auth.models import AuthSession
from vip_api.auth.tokens import hash_token
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError


def csrf_error() -> ApplicationError:
    return ApplicationError(
        code="CSRF_VALIDATION_FAILED",
        message="The CSRF validation failed.",
        status_code=403,
    )


def validate_csrf(request: Request, session: AuthSession, settings: Settings) -> None:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin and origin not in settings.CSRF_TRUSTED_ORIGINS:
        raise csrf_error()
    if (
        not origin
        and referer
        and not any(referer.startswith(f"{trusted}/") for trusted in settings.CSRF_TRUSTED_ORIGINS)
    ):
        raise csrf_error()

    cookie_token = request.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    header_token = request.headers.get(settings.AUTH_CSRF_HEADER_NAME)
    if not cookie_token or not header_token or not compare_digest(cookie_token, header_token):
        raise csrf_error()
    if not compare_digest(hash_token(cookie_token, "csrf"), session.csrf_token_hash):
        raise csrf_error()
