"""Tenant-safe upload, metadata, version, token and lifecycle services."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.files.models import (
    FileDownloadToken,
    FileScan,
    FileUpload,
    FileVersion,
    PlatformFile,
)
from vip_api.files.scanning import malware_scanner
from vip_api.files.schemas import DownloadLink, FileList, FileResponse, FileVersionResponse
from vip_api.files.storage import StorageProvider, storage_provider
from vip_api.files.validation import inspect_signature, sanitize_filename, validate_file_type
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext


def _workspace(context: AuthorizationContext) -> UUID:
    if context.workspace_id is None:
        raise ApplicationError(
            code="TENANT_CONTEXT_REQUIRED",
            message="Workspace context is required.",
            status_code=400,
        )
    return context.workspace_id


def response(item: PlatformFile) -> FileResponse:
    return FileResponse(
        id=item.id,
        filename=item.filename,
        original_filename=item.original_filename,
        mime_type=item.mime_type,
        extension=item.extension,
        size_bytes=item.size_bytes,
        sha256=item.sha256,
        kind=item.file_kind,
        status=item.status,
        tags=item.tags,
        current_version=item.current_version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def upload_file(
    db: AsyncSession,
    context: AuthorizationContext,
    request: Request,
    filename_value: str,
    mime_type: str,
    settings: Settings,
) -> FileResponse:
    workspace_id = _workspace(context)
    filename = sanitize_filename(filename_value)
    extension = validate_file_type(
        filename,
        mime_type,
        settings.FILE_ALLOWED_EXTENSIONS,
        settings.FILE_ALLOWED_MIME_TYPES,
    )
    upload = FileUpload(
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        user_id=context.user_id,
    )
    db.add(upload)
    await db.commit()
    upload_id = upload.id
    file_descriptor, temp_name = tempfile.mkstemp(prefix="vip-upload-")
    os.close(file_descriptor)
    temp_path = Path(temp_name)
    size = 0
    digest = hashlib.sha256()
    scan_provider = settings.FILE_MALWARE_SCANNER
    scan_status: str | None = None
    scan_signature: str | None = None
    try:
        handle = await asyncio.to_thread(temp_path.open, "wb")
        try:
            async for chunk in request.stream():
                size += len(chunk)
                if size > settings.FILE_MAX_UPLOAD_BYTES:
                    raise ApplicationError(
                        code="FILE_TOO_LARGE",
                        message="The upload exceeds the configured size limit.",
                        status_code=413,
                    )
                digest.update(chunk)
                await asyncio.to_thread(handle.write, chunk)
        finally:
            await asyncio.to_thread(handle.close)
        if size == 0:
            raise ApplicationError(
                code="EMPTY_FILE", message="The uploaded file is empty.", status_code=422
            )
        await asyncio.to_thread(inspect_signature, temp_path, mime_type)
        upload.stage = "virus_scan"
        scan = await malware_scanner(settings).scan(temp_path)
        scan_status = scan.status
        scan_signature = scan.signature
        upload.scan_provider = scan_provider
        upload.scan_status = scan_status
        upload.scan_signature = scan_signature
        if scan.status != "clean":
            raise ApplicationError(
                code="FILE_INFECTED" if scan.status == "infected" else "FILE_SCANNER_UNAVAILABLE",
                message="The file did not pass security scanning.",
                status_code=422 if scan.status == "infected" else 503,
            )
        content_hash = digest.hexdigest()
        duplicate = await db.scalar(
            select(PlatformFile.id).where(
                PlatformFile.organization_id == context.organization_id,
                PlatformFile.workspace_id == workspace_id,
                PlatformFile.sha256 == content_hash,
                PlatformFile.status == "ready",
                PlatformFile.is_deleted.is_(False),
            )
        )
        item = PlatformFile(
            organization_id=context.organization_id,
            workspace_id=workspace_id,
            created_by_user_id=context.user_id,
            file_kind="user",
            status="processing",
            filename=filename,
            original_filename=filename_value[:255],
            mime_type=mime_type,
            extension=extension,
            size_bytes=size,
            sha256=content_hash,
            checksum=f"sha256:{content_hash}",
            metadata_json={"duplicate_of": str(duplicate)} if duplicate else {},
            storage_provider=settings.FILE_STORAGE_PROVIDER,
            retention_until=datetime.now(UTC) + timedelta(days=settings.FILE_RETENTION_DAYS),
        )
        db.add(item)
        await db.flush()
        storage_key = (
            f"{context.organization_id}/{workspace_id}/{item.id}/"
            f"{item.current_version}/{uuid4().hex}{extension}"
        )
        provider = storage_provider(settings.FILE_STORAGE_PROVIDER, settings.FILE_STORAGE_ROOT)
        await provider.put(temp_path, storage_key)
        item.storage_key = storage_key
        item.status = "ready"
        upload.file_id = item.id
        upload.stage = "ready"
        upload.status = "completed"
        upload.bytes_received = size
        upload.completed_at = datetime.now(UTC)
        db.add(
            FileVersion(
                file_id=item.id,
                version_number=1,
                created_by_user_id=context.user_id,
                storage_provider=item.storage_provider,
                storage_key=storage_key,
                size_bytes=size,
                sha256=content_hash,
                mime_type=mime_type,
                scan_status=scan.status,
            )
        )
        db.add(
            FileScan(
                file_id=item.id,
                provider=settings.FILE_MALWARE_SCANNER,
                status=scan.status,
                signature=scan.signature,
            )
        )
        await record_audit(
            db,
            "file.upload",
            actor_user_id=context.user_id,
            organization_id=context.organization_id,
            workspace_id=workspace_id,
            resource_type="file",
            resource_id=item.id,
            metadata={"scan_provider": scan_provider, "scan_status": scan_status},
        )
        await db.commit()
        await db.refresh(item)
        return response(item)
    except Exception as exc:
        await db.rollback()
        persisted = await db.get(FileUpload, upload_id)
        if persisted is not None:
            persisted.status = "failed"
            persisted.safe_error_code = (
                exc.code if isinstance(exc, ApplicationError) else "FILE_UPLOAD_FAILED"
            )
            persisted.safe_error_message = "The upload could not be completed."
            persisted.scan_provider = scan_provider
            persisted.scan_status = scan_status
            persisted.scan_signature = scan_signature
            persisted.completed_at = datetime.now(UTC)
            await record_audit(
                db,
                "file.upload.failed",
                actor_user_id=context.user_id,
                organization_id=context.organization_id,
                workspace_id=workspace_id,
                outcome="failure",
                reason_code=persisted.safe_error_code,
                resource_type="file_upload",
                resource_id=upload_id,
                metadata={
                    "scan_provider": scan_provider,
                    "scan_status": scan_status or "not_run",
                    "scan_signature": scan_signature,
                },
            )
            await db.commit()
        raise
    finally:
        if await asyncio.to_thread(temp_path.exists):
            await asyncio.to_thread(temp_path.unlink)


async def get_file(db: AsyncSession, context: AuthorizationContext, file_id: UUID) -> PlatformFile:
    item = await db.scalar(
        select(PlatformFile).where(
            PlatformFile.id == file_id,
            PlatformFile.organization_id == context.organization_id,
            PlatformFile.workspace_id == _workspace(context),
            PlatformFile.is_deleted.is_(False),
        )
    )
    if item is None:
        raise ApplicationError(
            code="FILE_NOT_FOUND", message="The file was not found.", status_code=404
        )
    return item


async def list_files(
    db: AsyncSession,
    context: AuthorizationContext,
    limit: int,
    before: datetime | None = None,
) -> FileList:
    statement = select(PlatformFile).where(
        PlatformFile.organization_id == context.organization_id,
        PlatformFile.workspace_id == _workspace(context),
        PlatformFile.is_deleted.is_(False),
    )
    if before is not None:
        statement = statement.where(PlatformFile.created_at < before)
    items = (
        await db.scalars(statement.order_by(PlatformFile.created_at.desc()).limit(limit + 1))
    ).all()
    next_cursor = items[limit - 1].created_at if len(items) > limit else None
    return FileList(items=[response(item) for item in items[:limit]], next_cursor=next_cursor)


async def delete_file(db: AsyncSession, context: AuthorizationContext, file_id: UUID) -> None:
    item = await get_file(db, context, file_id)
    item.is_deleted = True
    item.status = "deleted"
    item.deleted_at = datetime.now(UTC)
    item.row_version += 1
    await record_audit(
        db,
        "file.delete",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="file",
        resource_id=item.id,
    )
    await db.commit()


async def create_download(
    db: AsyncSession,
    context: AuthorizationContext,
    file_id: UUID,
    settings: Settings,
) -> DownloadLink:
    item = await get_file(db, context, file_id)
    if item.status != "ready":
        raise ApplicationError(
            code="FILE_NOT_READY", message="The file is not ready for download.", status_code=409
        )
    nonce = secrets.token_urlsafe(48)
    signature = hmac.new(
        settings.file_download_signing_key.encode(), nonce.encode(), hashlib.sha256
    ).hexdigest()
    raw_token = f"{nonce}.{signature}"
    expires = datetime.now(UTC) + timedelta(seconds=settings.FILE_DOWNLOAD_TOKEN_TTL_SECONDS)
    db.add(
        FileDownloadToken(
            file_id=item.id,
            organization_id=context.organization_id,
            workspace_id=_workspace(context),
            user_id=context.user_id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=expires,
        )
    )
    await record_audit(
        db,
        "file.download_token.created",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="file",
        resource_id=item.id,
    )
    await db.commit()
    return DownloadLink(url=f"/api/v1/files/download/{raw_token}", expires_at=expires)


async def consume_download(
    db: AsyncSession,
    context: AuthorizationContext,
    raw_token: str,
    settings: Settings,
) -> PlatformFile:
    try:
        nonce, signature = raw_token.split(".", 1)
    except ValueError as exc:
        raise ApplicationError(
            code="DOWNLOAD_TOKEN_INVALID",
            message="The download link is invalid or expired.",
            status_code=404,
        ) from exc
    expected = hmac.new(
        settings.file_download_signing_key.encode(), nonce.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ApplicationError(
            code="DOWNLOAD_TOKEN_INVALID",
            message="The download link is invalid or expired.",
            status_code=404,
        )
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token = await db.scalar(
        select(FileDownloadToken)
        .where(FileDownloadToken.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        token is None
        or token.expires_at <= now
        or token.used_at is not None
        or token.user_id != context.user_id
        or token.organization_id != context.organization_id
        or token.workspace_id != _workspace(context)
    ):
        raise ApplicationError(
            code="DOWNLOAD_TOKEN_INVALID",
            message="The download link is invalid or expired.",
            status_code=404,
        )
    item = await get_file(db, context, token.file_id)
    token.used_at = now
    await record_audit(
        db,
        "file.download",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="file",
        resource_id=item.id,
    )
    await db.commit()
    return item


async def versions(
    db: AsyncSession, context: AuthorizationContext, file_id: UUID
) -> list[FileVersionResponse]:
    item = await get_file(db, context, file_id)
    rows = (
        await db.scalars(
            select(FileVersion)
            .where(FileVersion.file_id == item.id)
            .order_by(FileVersion.version_number.desc())
        )
    ).all()
    return [
        FileVersionResponse(
            version=row.version_number,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            mime_type=row.mime_type,
            scan_status=row.scan_status,
            created_at=row.created_at,
        )
        for row in rows
    ]


async def replace_file(
    db: AsyncSession,
    context: AuthorizationContext,
    file_id: UUID,
    request: Request,
    filename: str,
    mime_type: str,
    settings: Settings,
) -> FileResponse:
    item = await get_file(db, context, file_id)
    staged = await upload_file(db, context, request, filename, mime_type, settings)
    staged_item = await get_file(db, context, staged.id)
    staged_version = await db.scalar(
        select(FileVersion).where(
            FileVersion.file_id == staged_item.id,
            FileVersion.version_number == staged_item.current_version,
        )
    )
    if staged_version is None or staged_item.storage_key is None or staged_item.sha256 is None:
        raise ApplicationError(
            code="FILE_REPLACEMENT_FAILED",
            message="The replacement could not be completed.",
            status_code=500,
        )
    next_version = item.current_version + 1
    db.add(
        FileVersion(
            file_id=item.id,
            version_number=next_version,
            created_by_user_id=context.user_id,
            storage_provider=staged_item.storage_provider,
            storage_key=staged_item.storage_key,
            size_bytes=staged_item.size_bytes,
            sha256=staged_item.sha256,
            mime_type=staged_item.mime_type,
            scan_status=staged_version.scan_status,
        )
    )
    item.filename = staged_item.filename
    item.original_filename = staged_item.original_filename
    item.mime_type = staged_item.mime_type
    item.extension = staged_item.extension
    item.size_bytes = staged_item.size_bytes
    item.sha256 = staged_item.sha256
    item.checksum = staged_item.checksum
    item.storage_provider = staged_item.storage_provider
    item.storage_key = staged_item.storage_key
    item.current_version = next_version
    item.row_version += 1
    await db.delete(staged_item)
    await record_audit(
        db,
        "file.replace",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="file",
        resource_id=item.id,
    )
    await db.commit()
    await db.refresh(item)
    return response(item)


async def restore_version(
    db: AsyncSession,
    context: AuthorizationContext,
    file_id: UUID,
    version_number: int,
) -> FileResponse:
    item = await get_file(db, context, file_id)
    source = await db.scalar(
        select(FileVersion).where(
            FileVersion.file_id == item.id,
            FileVersion.version_number == version_number,
        )
    )
    if source is None:
        raise ApplicationError(
            code="FILE_VERSION_NOT_FOUND",
            message="The file version was not found.",
            status_code=404,
        )
    next_version = item.current_version + 1
    db.add(
        FileVersion(
            file_id=item.id,
            version_number=next_version,
            created_by_user_id=context.user_id,
            storage_provider=source.storage_provider,
            storage_key=source.storage_key,
            size_bytes=source.size_bytes,
            sha256=source.sha256,
            mime_type=source.mime_type,
            scan_status=source.scan_status,
        )
    )
    item.storage_provider = source.storage_provider
    item.storage_key = source.storage_key
    item.size_bytes = source.size_bytes
    item.sha256 = source.sha256
    item.checksum = f"sha256:{source.sha256}"
    item.mime_type = source.mime_type
    item.current_version = next_version
    item.row_version += 1
    await record_audit(
        db,
        "file.restore",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="file",
        resource_id=item.id,
    )
    await db.commit()
    await db.refresh(item)
    return response(item)


def provider_for(item: PlatformFile, settings: Settings) -> StorageProvider:
    return storage_provider(item.storage_provider, settings.FILE_STORAGE_ROOT)
