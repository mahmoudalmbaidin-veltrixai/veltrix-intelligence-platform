"""FastAPI application factory and ASGI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from vip_api.api.router import register_routers
from vip_api.auth.password import PasswordService
from vip_api.core.config import Settings, get_settings
from vip_api.core.errors import register_exception_handlers
from vip_api.core.logging import configure_logging
from vip_api.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from vip_api.database.session import Database
from vip_api.redis.client import RedisClient


def create_application(settings: Settings | None = None) -> FastAPI:
    """Build a fully configured application without connecting to external services."""
    app_settings = settings or get_settings()
    configure_logging(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = Database(app_settings)
        app.state.redis = RedisClient(app_settings)
        app.state.password_service = PasswordService(app_settings)
        try:
            yield
        finally:
            await app.state.redis.close()
            await app.state.database.dispose()

    docs_url = "/docs" if app_settings.docs_enabled else None
    openapi_url = "/openapi.json" if app_settings.docs_enabled else None
    app = FastAPI(
        title=app_settings.APP_NAME,
        version=app_settings.APP_VERSION,
        debug=app_settings.DEBUG,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.settings = app_settings

    # Application-factory callers (tests, workers, alternate deployments) must
    # use the settings supplied to this app instance, not a process-global
    # Settings cache constructed from unrelated environment state.
    def configured_settings() -> Settings:
        return app_settings

    app.dependency_overrides[get_settings] = configured_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=app_settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "Last-Event-ID",
            "X-Correlation-ID",
            "X-File-Name",
            app_settings.AUTH_CSRF_HEADER_NAME,
            "X-Locale",
            app_settings.TENANCY_ORGANIZATION_HEADER,
            "X-Timezone",
            app_settings.TENANCY_WORKSPACE_HEADER,
        ],
    )
    if app_settings.TRUSTED_HOSTS != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=app_settings.TRUSTED_HOSTS)
    app.add_middleware(
        RequestContextMiddleware,
        organization_header=app_settings.TENANCY_ORGANIZATION_HEADER,
        workspace_header=app_settings.TENANCY_WORKSPACE_HEADER,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        is_production=app_settings.is_public_environment,
    )

    register_exception_handlers(app)
    register_routers(app, app_settings)
    return app


app = create_application()
