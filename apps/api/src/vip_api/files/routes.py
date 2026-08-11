"""Governed streaming file APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import require_csrf
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.files.capabilities import capability_contract
from vip_api.files.schemas import DownloadLink, FileList, FileResponse, FileVersionResponse
from vip_api.files.services import (
    consume_download,
    create_download,
    delete_file,
    get_file,
    list_files,
    provider_for,
    replace_file,
    response,
    restore_version,
    upload_file,
    versions,
)
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_permission
from vip_api.redis.client import RedisClient

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/capabilities")
async def file_format_capabilities(
    context: Annotated[AuthorizationContext, Depends(require_permission("file.download"))],
) -> dict[str, object]:
    """Server-authoritative upload and tabular-ingest format contract."""
    _ = context
    return capability_contract()


async def _enforce_rate_limit(
    request: Request,
    context: AuthorizationContext,
    operation: str,
    limit: int,
) -> None:
    redis: RedisClient = request.app.state.redis
    key = (
        f"{request.app.state.settings.JOB_QUEUE_PREFIX}:rate:file:{operation}:"
        f"{context.organization_id}:{context.workspace_id}:{context.user_id}"
    )
    count = int(await redis.client.incr(key))
    if count == 1:
        await redis.client.expire(key, 60)
    if count > limit:
        raise ApplicationError(
            code="FILE_RATE_LIMIT_EXCEEDED",
            message="Too many file requests. Please try again later.",
            status_code=429,
        )


@router.post("", response_model=FileResponse, status_code=201, dependencies=[Depends(require_csrf)])
async def upload(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.upload"))],
    filename: Annotated[str, Header(alias="X-File-Name", min_length=1, max_length=255)],
    content_type: Annotated[str, Header(alias="Content-Type")],
) -> FileResponse:
    settings: Settings = request.app.state.settings
    await _enforce_rate_limit(
        request, context, "upload", settings.FILE_UPLOAD_RATE_LIMIT_PER_MINUTE
    )
    return await upload_file(db, context, request, filename, content_type, settings)


@router.get("", response_model=FileList)
async def index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.download"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: datetime | None = None,
) -> FileList:
    return await list_files(db, context, limit, before)


@router.get("/{file_id}", response_model=FileResponse)
async def show(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.download"))],
) -> FileResponse:
    return response(await get_file(db, context, file_id))


@router.get("/{file_id}/versions", response_model=list[FileVersionResponse])
async def file_versions(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.download"))],
) -> list[FileVersionResponse]:
    return await versions(db, context, file_id)


@router.put(
    "/{file_id}/content",
    response_model=FileResponse,
    dependencies=[Depends(require_csrf)],
)
async def replace(
    file_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.manage"))],
    filename: Annotated[str, Header(alias="X-File-Name", min_length=1, max_length=255)],
    content_type: Annotated[str, Header(alias="Content-Type")],
) -> FileResponse:
    settings: Settings = request.app.state.settings
    await _enforce_rate_limit(
        request, context, "upload", settings.FILE_UPLOAD_RATE_LIMIT_PER_MINUTE
    )
    return await replace_file(
        db,
        context,
        file_id,
        request,
        filename,
        content_type,
        settings,
    )


@router.post(
    "/{file_id}/versions/{version_number}/restore",
    response_model=FileResponse,
    dependencies=[Depends(require_csrf)],
)
async def restore(
    file_id: UUID,
    version_number: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.manage"))],
) -> FileResponse:
    return await restore_version(db, context, file_id, version_number)


@router.post(
    "/{file_id}/download",
    response_model=DownloadLink,
    dependencies=[Depends(require_csrf)],
)
async def download_link(
    file_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.download"))],
) -> DownloadLink:
    settings: Settings = request.app.state.settings
    await _enforce_rate_limit(
        request, context, "download", settings.FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE
    )
    return await create_download(db, context, file_id, settings)


@router.get("/download/{token}", response_class=StreamingResponse)
async def download(
    token: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.download"))],
) -> StreamingResponse:
    settings: Settings = request.app.state.settings
    await _enforce_rate_limit(
        request, context, "download", settings.FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE
    )
    item = await consume_download(db, context, token, settings)
    if item.storage_key is None:
        raise ApplicationError(
            code="FILE_NOT_READY", message="The file is not ready for download.", status_code=409
        )
    provider = provider_for(item, settings)
    safe_name = item.filename.replace('"', "_")
    return StreamingResponse(
        provider.stream(item.storage_key, settings.FILE_STREAM_CHUNK_BYTES),
        media_type=item.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(item.size_bytes),
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{file_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def remove(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(require_permission("file.delete"))],
) -> Response:
    await delete_file(db, context, file_id)
    return Response(status_code=204)
