"""Consistent authentication cookie creation and removal."""

from fastapi import Response

from vip_api.auth.tokens import SessionTokens
from vip_api.core.config import Settings


def set_auth_cookies(response: Response, tokens: SessionTokens, settings: Settings) -> None:
    response.set_cookie(
        settings.AUTH_ACCESS_COOKIE_NAME,
        tokens.access,
        httponly=True,
        path="/",
        max_age=settings.AUTH_ACCESS_SESSION_TTL_MINUTES * 60,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        tokens.refresh,
        httponly=True,
        path="/auth",
        max_age=settings.AUTH_REFRESH_SESSION_TTL_DAYS * 86_400,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.set_cookie(
        settings.AUTH_CSRF_COOKIE_NAME,
        tokens.csrf,
        httponly=False,
        path="/",
        max_age=settings.AUTH_REFRESH_SESSION_TTL_DAYS * 86_400,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.AUTH_ACCESS_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path="/auth",
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.delete_cookie(
        settings.AUTH_CSRF_COOKIE_NAME,
        path="/",
        httponly=False,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
