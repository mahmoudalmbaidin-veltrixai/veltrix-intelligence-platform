"""Versioned API metadata endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from vip_api.api.routes.operational import get_app_settings
from vip_api.core.config import Settings
from vip_api.schemas.version import VersionResponse

router = APIRouter()


@router.get("/version", response_model=VersionResponse)
async def version(settings: Annotated[Settings, Depends(get_app_settings)]) -> VersionResponse:
    return VersionResponse(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV.value,
        commit_sha=settings.BUILD_COMMIT_SHA,
        build_timestamp=settings.BUILD_TIMESTAMP,
    )
