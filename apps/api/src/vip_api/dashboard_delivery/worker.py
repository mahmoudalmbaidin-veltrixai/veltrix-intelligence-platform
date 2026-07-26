"""Durable single-purpose B6.5 worker; replaceable by the future common job runner."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vip_api.connections.crypto import EnvironmentEncryptionKeyProvider
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings, get_settings
from vip_api.core.errors import ApplicationError
from vip_api.core.logging import configure_logging
from vip_api.dashboard_delivery.email import (
    DashboardEmail,
    EmailAttachment,
    get_email_provider,
    render_email_html,
)
from vip_api.dashboard_delivery.models import (
    DashboardDeliveryRun,
    DashboardDeliverySchedule,
    DashboardExport,
)
from vip_api.dashboard_delivery.rendering import RenderDocument, RendererRegistry
from vip_api.dashboard_delivery.storage import FileArtifactStorage
from vip_api.dashboards.models import Dashboard, DashboardVersion
from vip_api.dashboards.query import execute_widget
from vip_api.dashboards.schemas import WidgetDataRequest
from vip_api.dashboards.services import _access
from vip_api.database.session import Database
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import (
    GovernanceRequirement,
    authorize,
    resolve_authorization_context,
)
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.models import (
    MembershipStatus,
    OrganizationMembership,
    WorkspaceMembership,
)

logger = logging.getLogger(__name__)


async def _context(db: AsyncSession, job: DashboardExport) -> AuthorizationContext:
    organization_membership = await db.scalar(
        select(OrganizationMembership)
        .options(selectinload(OrganizationMembership.role))
        .where(
            OrganizationMembership.organization_id == job.organization_id,
            OrganizationMembership.user_id == job.requested_by_user_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    workspace_membership = await db.scalar(
        select(WorkspaceMembership)
        .options(selectinload(WorkspaceMembership.role))
        .where(
            WorkspaceMembership.organization_id == job.organization_id,
            WorkspaceMembership.workspace_id == job.workspace_id,
            WorkspaceMembership.user_id == job.requested_by_user_id,
            WorkspaceMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if organization_membership is None or workspace_membership is None:
        raise ApplicationError(
            code="DASHBOARD_EXPORT_ACCESS_REVOKED",
            message="Export access is no longer available.",
            status_code=403,
        )
    tenant = TenantContext(
        user_id=job.requested_by_user_id,
        organization_id=job.organization_id,
        workspace_id=job.workspace_id,
        organization_membership_id=organization_membership.id,
        workspace_membership_id=workspace_membership.id,
        organization_role=organization_membership.role.key,
        workspace_role=workspace_membership.role.key,
        correlation_id=f"dashboard-export-{job.id}",
    )
    return await resolve_authorization_context(db, tenant)


async def claim(db: AsyncSession, settings: Settings, owner: str) -> UUID | None:
    now = datetime.now(UTC)
    job = await db.scalar(
        select(DashboardExport)
        .where(
            or_(
                DashboardExport.status == "queued",
                (
                    (DashboardExport.status == "rendering")
                    & (DashboardExport.lease_expires_at < now)
                ),
            ),
            DashboardExport.available_at <= now,
            DashboardExport.cancellation_requested.is_(False),
        )
        .order_by(DashboardExport.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = "rendering"
    job.progress = 5
    job.attempts += 1
    job.started_at = job.started_at or now
    job.lease_owner = owner
    job.lease_expires_at = now + timedelta(seconds=settings.DASHBOARD_EXPORT_LEASE_SECONDS)
    job.row_version += 1
    await db.commit()
    return job.id


async def _cancelled(db: AsyncSession, job_id: UUID) -> bool:
    value = await db.scalar(
        select(DashboardExport.cancellation_requested).where(DashboardExport.id == job_id)
    )
    return bool(value)


async def _complete_delivery(
    db: AsyncSession,
    job: DashboardExport,
    artifact: bytes,
    settings: Settings,
    dashboard: Dashboard,
    version: DashboardVersion,
) -> None:
    if job.delivery_run_id is None:
        return
    run = await db.scalar(
        select(DashboardDeliveryRun).where(
            DashboardDeliveryRun.id == job.delivery_run_id,
            DashboardDeliveryRun.organization_id == job.organization_id,
            DashboardDeliveryRun.workspace_id == job.workspace_id,
        )
    )
    if run is None:
        return
    schedule = await db.scalar(
        select(DashboardDeliverySchedule).where(
            DashboardDeliverySchedule.id == run.schedule_id,
            DashboardDeliverySchedule.organization_id == job.organization_id,
            DashboardDeliverySchedule.workspace_id == job.workspace_id,
        )
    )
    if schedule is None:
        run.status = "failed"
        run.safe_error_code = "DASHBOARD_DELIVERY_NOT_FOUND"
        run.safe_error_message = "The delivery definition is unavailable."
        run.completed_at = datetime.now(UTC)
        return
    dashboard_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/dashboards/{dashboard.id}"
        if schedule.include_dashboard_link
        else None
    )
    message = DashboardEmail(
        recipients=schedule.recipients,
        cc=schedule.cc,
        bcc=schedule.bcc,
        subject=schedule.subject,
        html=render_email_html(
            dashboard.name, version.version_number, datetime.now(UTC).isoformat(), dashboard_url
        ),
        attachments=[
            EmailAttachment(
                filename=f"dashboard.{job.format}",
                content_type=job.artifact_content_type or "application/octet-stream",
                content=artifact,
            )
        ],
    )
    run.status = "sending"
    await db.commit()
    message_id = await get_email_provider(settings).send(message, run.id)
    run.provider_message_id = message_id
    run.status = "sent"
    run.sent_at = datetime.now(UTC)
    run.completed_at = run.sent_at
    schedule.last_run_at = run.sent_at
    schedule.status = "sent"
    await record_audit(
        db,
        "dashboard.delivery.sent",
        actor_user_id=job.requested_by_user_id,
        organization_id=job.organization_id,
        workspace_id=job.workspace_id,
        resource_type="dashboard_delivery_run",
        resource_id=run.id,
        metadata={"recipient_count": len(set(schedule.recipients + schedule.cc + schedule.bcc))},
    )


async def process(
    db: AsyncSession,
    job_id: UUID,
    settings: Settings,
    storage: FileArtifactStorage,
    renderers: RendererRegistry,
) -> None:
    job = await db.scalar(select(DashboardExport).where(DashboardExport.id == job_id))
    if job is None:
        return
    try:
        context = await _context(db, job)
        await authorize(
            db,
            context,
            GovernanceRequirement(
                "dashboard.export", feature="dashboard_exports", entitlement="dashboard_exports"
            ),
        )
        dashboard = await db.scalar(
            select(Dashboard).where(
                Dashboard.id == job.dashboard_id,
                Dashboard.organization_id == job.organization_id,
                Dashboard.workspace_id == job.workspace_id,
            )
        )
        version = await db.scalar(
            select(DashboardVersion).where(
                DashboardVersion.id == job.dashboard_version_id,
                DashboardVersion.dashboard_id == job.dashboard_id,
                DashboardVersion.organization_id == job.organization_id,
                DashboardVersion.workspace_id == job.workspace_id,
                DashboardVersion.version_type == "published",
            )
        )
        if (
            dashboard is None
            or version is None
            or not (await _access(db, context, dashboard))["can_view"]
        ):
            raise ApplicationError(
                code="DASHBOARD_EXPORT_ACCESS_REVOKED",
                message="Export access is no longer available.",
                status_code=403,
            )
        provider = DatabaseEncryptedSecretProvider(EnvironmentEncryptionKeyProvider(settings))
        pages = cast(list[dict[str, object]], version.snapshot.get("pages", []))
        widgets = [
            widget
            for page in pages
            for widget in cast(list[dict[str, object]], page.get("widgets", []))
            if widget.get("semantic_model_id") and not widget.get("hidden", False)
        ]
        results: dict[str, object] = {}
        for index, widget in enumerate(widgets):
            if await _cancelled(db, job.id):
                job.status = "cancelled"
                job.cancelled_at = datetime.now(UTC)
                job.progress = 0
                job.row_version += 1
                await db.commit()
                return
            widget_id = UUID(str(widget["id"]))
            result = await execute_widget(
                db,
                context,
                dashboard.id,
                widget_id,
                WidgetDataRequest(
                    dashboard_version=version.version_number,
                    preview=False,
                    filters=job.filters,
                ),
                settings,
                provider,
                published_version_id=version.id,
            )
            results[str(widget_id)] = result.model_dump(mode="json")
            job.progress = 10 + int(((index + 1) / max(len(widgets), 1)) * 60)
            job.lease_expires_at = datetime.now(UTC) + timedelta(
                seconds=settings.DASHBOARD_EXPORT_LEASE_SECONDS
            )
            await db.commit()
        document = RenderDocument(
            dashboard_id=dashboard.id,
            dashboard_version=version.version_number,
            organization_id=job.organization_id,
            workspace_id=job.workspace_id,
            generated_at=datetime.now(UTC),
            dashboard_name=dashboard.name,
            snapshot=version.snapshot,
            widget_results=results,
            filters=job.filters,
            locale=job.locale,
            timezone=job.timezone,
        )
        artifact = await asyncio.to_thread(renderers.get(job.format).render, document)
        if len(artifact.content) > settings.DASHBOARD_EXPORT_MAX_ARTIFACT_BYTES:
            raise ApplicationError(
                code="DASHBOARD_EXPORT_TOO_LARGE",
                message="The generated export exceeded the configured size limit.",
                status_code=422,
            )
        key = storage.key(job.organization_id, job.workspace_id, job.id, artifact.extension)
        stored = await storage.put(key, artifact.content)
        job.artifact_key = stored.key
        job.artifact_content_type = artifact.content_type
        job.artifact_size_bytes = stored.size_bytes
        job.artifact_sha256 = hashlib.sha256(artifact.content).hexdigest()
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.now(UTC)
        job.expires_at = job.completed_at + timedelta(
            hours=settings.DASHBOARD_EXPORT_RETENTION_HOURS
        )
        job.lease_owner = None
        job.lease_expires_at = None
        job.row_version += 1
        await _complete_delivery(db, job, artifact.content, settings, dashboard, version)
        await record_audit(
            db,
            "dashboard.export.completed",
            actor_user_id=job.requested_by_user_id,
            organization_id=job.organization_id,
            workspace_id=job.workspace_id,
            resource_type="dashboard_export",
            resource_id=job.id,
            metadata={"format": job.format, "size_bytes": stored.size_bytes},
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        job = await db.scalar(select(DashboardExport).where(DashboardExport.id == job_id))
        if job is None:
            return
        logger.exception(
            "Dashboard export worker failed", extra={"dashboard_export_id": str(job_id)}
        )
        job.safe_error_code = (
            exc.code if isinstance(exc, ApplicationError) else "DASHBOARD_EXPORT_FAILED"
        )
        job.safe_error_message = "The dashboard export could not be completed."
        job.lease_owner = None
        job.lease_expires_at = None
        job.row_version += 1
        if job.attempts < job.max_attempts and not job.cancellation_requested:
            job.status = "queued"
            job.available_at = datetime.now(UTC) + timedelta(seconds=2**job.attempts)
            job.progress = 0
        else:
            job.status = "failed"
            job.completed_at = datetime.now(UTC)
        if job.delivery_run_id:
            run = await db.scalar(
                select(DashboardDeliveryRun).where(DashboardDeliveryRun.id == job.delivery_run_id)
            )
            if run:
                run.status = "failed"
                run.safe_error_code = job.safe_error_code
                run.safe_error_message = job.safe_error_message
                run.completed_at = datetime.now(UTC)
        await record_audit(
            db,
            "dashboard.export.failed",
            actor_user_id=job.requested_by_user_id,
            organization_id=job.organization_id,
            workspace_id=job.workspace_id,
            outcome="failure",
            reason_code=job.safe_error_code,
            resource_type="dashboard_export",
            resource_id=job.id,
        )
        await db.commit()


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)
    database = Database(settings)
    storage = FileArtifactStorage(settings)
    renderers = RendererRegistry()
    owner = f"{socket.gethostname()}-{os.getpid()}"
    logger.info("Dashboard export worker started")
    try:
        while True:
            async with database.session_factory() as db:
                job_id = await claim(db, settings, owner)
            if job_id is None:
                await asyncio.sleep(settings.DASHBOARD_EXPORT_WORKER_POLL_SECONDS)
                continue
            async with database.session_factory() as db:
                await process(db, job_id, settings, storage, renderers)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(run())
