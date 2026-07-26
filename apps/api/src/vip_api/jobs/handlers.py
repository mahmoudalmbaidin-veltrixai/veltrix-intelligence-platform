"""Built-in generic handlers; feature adapters register here without worker coupling."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.crypto import EnvironmentEncryptionKeyProvider
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings, get_settings
from vip_api.dashboard_delivery.models import DashboardExport
from vip_api.dashboard_delivery.rendering import RendererRegistry
from vip_api.dashboard_delivery.storage import FileArtifactStorage
from vip_api.dashboard_delivery.worker import process
from vip_api.database.session import Database
from vip_api.files.lifecycle import cleanup_expired_files
from vip_api.files.models import FileScan, FileVersion, PlatformFile
from vip_api.files.storage import storage_provider
from vip_api.jobs.registry import JobContextProtocol, registry
from vip_api.jobs.retry import PermanentJobError, RetryableJobError


async def platform_noop(
    context: JobContextProtocol, payload: dict[str, object]
) -> dict[str, object]:
    await context.progress(50, stage="processing", message="Processing platform job")
    if await context.cancellation_requested():
        return {"cancelled": True}
    await context.progress(100, stage="complete", message="Platform job completed")
    return {"accepted": True, "payload_keys": sorted(payload)}


registry.register("platform.noop", platform_noop)


async def dataset_quality(
    context: JobContextProtocol, payload: dict[str, object]
) -> dict[str, object]:
    raw_id = payload.get("quality_evaluation_id")
    if not isinstance(raw_id, str):
        raise PermanentJobError(
            "INVALID_QUALITY_PAYLOAD", "The quality evaluation payload is invalid."
        )
    try:
        evaluation_id = UUID(raw_id)
    except ValueError as exc:
        raise PermanentJobError(
            "INVALID_QUALITY_PAYLOAD", "The quality evaluation payload is invalid."
        ) from exc
    from vip_api.datasets.quality import evaluate

    settings = get_settings()
    database = Database(settings)
    provider = DatabaseEncryptedSecretProvider(EnvironmentEncryptionKeyProvider(settings))
    try:
        await context.progress(5, stage="quality", message="Preparing dataset quality evaluation")
        async with database.session_factory() as db:
            result = await evaluate(db, evaluation_id, settings, provider)
        await context.progress(100, stage="complete", message="Quality evaluation completed")
        return result
    finally:
        await database.dispose()


registry.register("dataset.quality", dataset_quality)


async def dashboard_export(
    context: JobContextProtocol, payload: dict[str, object]
) -> dict[str, object]:
    raw_id = payload.get("dashboard_export_id")
    if not isinstance(raw_id, str):
        raise PermanentJobError("INVALID_EXPORT_PAYLOAD", "The export payload is invalid.")
    try:
        export_id = UUID(raw_id)
    except ValueError as exc:
        raise PermanentJobError("INVALID_EXPORT_PAYLOAD", "The export payload is invalid.") from exc
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            export = await db.scalar(select(DashboardExport).where(DashboardExport.id == export_id))
            if export is None:
                raise PermanentJobError(
                    "DASHBOARD_EXPORT_NOT_FOUND", "The dashboard export was not found."
                )
            export.status = "rendering"
            export.attempts += 1
            await db.commit()
        await context.progress(5, stage="rendering", message="Preparing dashboard export")
        async with database.session_factory() as db:
            await process(
                db,
                export_id,
                settings,
                FileArtifactStorage(settings),
                RendererRegistry(),
            )
        async with database.session_factory() as db:
            export = await db.get(DashboardExport, export_id)
            if export is None:
                raise PermanentJobError(
                    "DASHBOARD_EXPORT_NOT_FOUND", "The dashboard export was not found."
                )
            if export.status == "cancelled":
                return {"dashboard_export_id": raw_id, "cancelled": True}
            if export.status != "completed":
                export.status = "queued"
                export.progress = 0
                await db.commit()
                raise RetryableJobError(
                    export.safe_error_code or "DASHBOARD_EXPORT_FAILED",
                    "The dashboard export could not be completed.",
                )
            result = {
                "dashboard_export_id": raw_id,
                "format": export.format,
                "size_bytes": export.artifact_size_bytes or 0,
                "sha256": export.artifact_sha256 or "",
            }
            file_id = await _register_export_file(
                db, context, export, settings, FileArtifactStorage(settings)
            )
            result["file_id"] = str(file_id)
        await context.progress(100, stage="complete", message="Dashboard export completed")
        return result
    finally:
        await database.dispose()


registry.register("dashboard.export", dashboard_export)


async def _register_export_file(
    db: AsyncSession,
    context: JobContextProtocol,
    export: DashboardExport,
    settings: Settings,
    artifact_storage: FileArtifactStorage,
) -> UUID:
    existing = await db.scalar(
        select(PlatformFile).where(
            PlatformFile.organization_id == export.organization_id,
            PlatformFile.workspace_id == export.workspace_id,
            PlatformFile.metadata_json["source_job_id"].as_string() == str(context.job_id),
            PlatformFile.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing.id
    if (
        export.artifact_key is None
        or export.artifact_content_type is None
        or export.artifact_sha256 is None
    ):
        raise PermanentJobError(
            "DASHBOARD_ARTIFACT_NOT_FOUND", "The dashboard artifact is unavailable."
        )
    content = await artifact_storage.read(export.artifact_key)
    extension = f".{export.format}"
    item = PlatformFile(
        organization_id=export.organization_id,
        workspace_id=export.workspace_id,
        created_by_user_id=export.requested_by_user_id,
        file_kind="generated",
        status="processing",
        filename=f"dashboard-export-{export.id}{extension}",
        original_filename=f"dashboard-export-{export.id}{extension}",
        mime_type=export.artifact_content_type,
        extension=extension,
        size_bytes=len(content),
        sha256=export.artifact_sha256,
        checksum=f"sha256:{export.artifact_sha256}",
        metadata_json={
            "source": "dashboard_export",
            "source_job_id": str(context.job_id),
            "dashboard_id": str(export.dashboard_id),
            "dashboard_version_id": str(export.dashboard_version_id),
            "generated_at": export.completed_at.isoformat() if export.completed_at else None,
        },
        storage_provider=settings.FILE_STORAGE_PROVIDER,
        retention_policy="generated",
        retention_until=export.expires_at,
    )
    db.add(item)
    await db.flush()
    key = f"{export.organization_id}/{export.workspace_id}/{item.id}/1/{uuid4().hex}{extension}"
    descriptor, temporary_name = tempfile.mkstemp(prefix="vip-generated-")
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        await asyncio.to_thread(temporary.write_bytes, content)
        await storage_provider(settings.FILE_STORAGE_PROVIDER, settings.FILE_STORAGE_ROOT).put(
            temporary, key
        )
    finally:
        if await asyncio.to_thread(temporary.exists):
            await asyncio.to_thread(temporary.unlink)
    item.storage_key = key
    item.status = "ready"
    db.add(
        FileVersion(
            file_id=item.id,
            version_number=1,
            created_by_user_id=export.requested_by_user_id,
            storage_provider=item.storage_provider,
            storage_key=key,
            size_bytes=len(content),
            sha256=export.artifact_sha256,
            mime_type=export.artifact_content_type,
            scan_status="trusted_generated",
        )
    )
    db.add(
        FileScan(
            file_id=item.id,
            provider="internal-renderer",
            status="trusted_generated",
        )
    )
    await db.commit()
    return item.id


async def file_lifecycle(
    context: JobContextProtocol, payload: dict[str, object]
) -> dict[str, object]:
    batch_size_value = payload.get("batch_size", 100)
    batch_size = (
        max(1, min(int(batch_size_value), 1000)) if isinstance(batch_size_value, int | str) else 100
    )
    await context.progress(10, stage="cleanup", message="Scanning expired file records")
    result = await cleanup_expired_files(get_settings(), batch_size)
    await context.progress(100, stage="complete", message="File lifecycle cleanup completed")
    return result


registry.register("platform.file_lifecycle", file_lifecycle)
