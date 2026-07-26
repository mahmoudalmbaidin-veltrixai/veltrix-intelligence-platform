"""Retention and temporary-token lifecycle maintenance."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, or_, select

from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.files.models import FileDownloadToken, FileVersion, PlatformFile
from vip_api.files.storage import storage_provider
from vip_api.governance.audit import record_audit


async def cleanup_expired_files(settings: Settings, batch_size: int = 100) -> dict[str, object]:
    """Purge provider objects in bounded batches while retaining audit metadata."""
    database = Database(settings)
    purged = 0
    tokens = 0
    now = datetime.now(UTC)
    try:
        async with database.session_factory() as db:
            token_result = await db.execute(
                delete(FileDownloadToken)
                .where(FileDownloadToken.expires_at < now)
                .returning(FileDownloadToken.id)
            )
            tokens = len(token_result.scalars().all())
            items = (
                await db.scalars(
                    select(PlatformFile)
                    .where(
                        PlatformFile.status != "purged",
                        or_(
                            PlatformFile.is_deleted.is_(True),
                            PlatformFile.retention_until < now,
                        ),
                    )
                    .order_by(PlatformFile.updated_at)
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
            for item in items:
                versions = (
                    await db.scalars(select(FileVersion).where(FileVersion.file_id == item.id))
                ).all()
                keys = {(row.storage_provider, row.storage_key) for row in versions}
                if item.storage_key:
                    keys.add((item.storage_provider, item.storage_key))
                for provider_name, key in keys:
                    await storage_provider(provider_name, settings.FILE_STORAGE_ROOT).delete(key)
                item.status = "purged"
                item.storage_key = None
                item.row_version += 1
                await record_audit(
                    db,
                    "file.purged",
                    actor_user_id=None,
                    organization_id=item.organization_id,
                    workspace_id=item.workspace_id,
                    resource_type="file",
                    resource_id=item.id,
                )
                purged += 1
            await db.commit()
    finally:
        await database.dispose()
    return {"purged_files": purged, "expired_download_tokens": tokens}
