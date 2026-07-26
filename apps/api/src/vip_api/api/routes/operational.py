"""Unversioned liveness and readiness endpoints."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from vip_api.core.config import Settings
from vip_api.database.health import check_database
from vip_api.database.session import Database, get_database
from vip_api.redis.client import RedisClient
from vip_api.redis.health import check_redis
from vip_api.schemas.health import (
    DependencyCheck,
    HealthResponse,
    ReadinessChecks,
    ReadinessResponse,
)

router = APIRouter(tags=["operations"])


def get_redis_client(request: Request) -> RedisClient:
    redis_client: RedisClient = request.app.state.redis
    return redis_client


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_app_settings)]) -> HealthResponse:
    """Report process liveness without touching external dependencies."""
    return HealthResponse(
        status="healthy",
        service=settings.SERVICE_NAME,
        version=settings.APP_VERSION,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(
    response: Response,
    settings: Annotated[Settings, Depends(get_app_settings)],
    database: Annotated[Database, Depends(get_database)],
    redis_client: Annotated[RedisClient, Depends(get_redis_client)],
) -> ReadinessResponse:
    """Check required dependencies concurrently with bounded timeouts."""
    database_healthy, redis_healthy = await asyncio.gather(
        check_database(database, settings.DATABASE_CONNECT_TIMEOUT),
        check_redis(redis_client, settings.REDIS_SOCKET_TIMEOUT),
    )
    ready = database_healthy and redis_healthy
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=ReadinessChecks(
            database=DependencyCheck(status="healthy" if database_healthy else "unhealthy"),
            redis=DependencyCheck(status="healthy" if redis_healthy else "unhealthy"),
        ),
    )
