"""Tenant-qualified export, signed-download, and delivery services."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.dashboard_delivery.email import render_email_html
from vip_api.dashboard_delivery.models import (
    DashboardDeliveryRun,
    DashboardDeliverySchedule,
    DashboardExport,
)
from vip_api.dashboard_delivery.scheduling import next_run
from vip_api.dashboard_delivery.schemas import (
    DeliveryRunResponse,
    DownloadTokenResponse,
    EmailPreviewRequest,
    EmailPreviewResponse,
    ExportCreate,
    ExportFormat,
    ExportResponse,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)
from vip_api.dashboards.models import Dashboard, DashboardVersion
from vip_api.dashboards.services import _access, get_dashboard
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import consume_quota, release_quota
from vip_api.jobs.models import Job, JobPayload
from vip_api.jobs.queue import JobQueue

logger = logging.getLogger(__name__)


def _workspace(context: AuthorizationContext) -> UUID:
    if context.workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    return context.workspace_id


def _conflict() -> ApplicationError:
    return ApplicationError(
        code="DASHBOARD_EXPORT_VERSION_CONFLICT",
        message="This resource changed. Reload before trying again.",
        status_code=409,
    )


def _export_response(item: DashboardExport) -> ExportResponse:
    return ExportResponse.model_validate(item, from_attributes=True)


def _schedule_response(item: DashboardDeliverySchedule) -> ScheduleResponse:
    return ScheduleResponse.model_validate(item, from_attributes=True)


async def _published(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID
) -> tuple[Dashboard, DashboardVersion]:
    dashboard = await get_dashboard(db, context, dashboard_id)
    access = await _access(db, context, dashboard)
    if not access["can_view"] or dashboard.published_version_id is None:
        raise ApplicationError(
            code="DASHBOARD_NOT_PUBLISHED",
            message="The requested dashboard is unavailable.",
            status_code=404,
        )
    version = await db.scalar(
        select(DashboardVersion).where(
            DashboardVersion.id == dashboard.published_version_id,
            DashboardVersion.dashboard_id == dashboard.id,
            DashboardVersion.organization_id == context.organization_id,
            DashboardVersion.workspace_id == _workspace(context),
            DashboardVersion.version_type == "published",
        )
    )
    if version is None:
        raise ApplicationError(
            code="DASHBOARD_NOT_PUBLISHED",
            message="The requested dashboard is unavailable.",
            status_code=404,
        )
    return dashboard, version


async def create_export(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    payload: ExportCreate,
    settings: Settings,
    *,
    delivery_run_id: UUID | None = None,
    queue: JobQueue | None = None,
) -> ExportResponse:
    dashboard, version = await _published(db, context, dashboard_id)
    await consume_quota(db, context, "dashboard_exports.per_day")
    export = DashboardExport(
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        dashboard_id=dashboard.id,
        dashboard_version_id=version.id,
        requested_by_user_id=context.user_id,
        delivery_run_id=delivery_run_id,
        format=payload.format,
        filters=payload.filters,
        locale=payload.locale,
        timezone=payload.timezone,
        max_attempts=settings.DASHBOARD_EXPORT_MAX_ATTEMPTS,
    )
    db.add(export)
    await db.flush()
    job_payload: dict[str, object] = {"dashboard_export_id": str(export.id)}
    encoded_payload = json.dumps(job_payload, separators=(",", ":")).encode()
    platform_job = Job(
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        job_type="export",
        handler="dashboard.export",
        queue_name="dashboard",
        name=f"Dashboard export ({payload.format.upper()})",
        idempotency_key=f"dashboard-export:{export.id}",
        correlation_id=context.correlation_id,
        created_by_user_id=context.user_id,
        max_attempts=settings.DASHBOARD_EXPORT_MAX_ATTEMPTS,
        timeout_seconds=settings.JOB_DEFAULT_TIMEOUT_SECONDS,
    )
    db.add(platform_job)
    await db.flush()
    export.platform_job_id = platform_job.id
    db.add(
        JobPayload(
            job_id=platform_job.id,
            payload=job_payload,
            size_bytes=len(encoded_payload),
            sha256=hashlib.sha256(encoded_payload).hexdigest(),
        )
    )
    await record_audit(
        db,
        "dashboard.export.queued",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_export",
        resource_id=export.id,
        metadata={"dashboard_id": str(dashboard.id), "format": payload.format},
    )
    await db.commit()
    if queue is not None:
        try:
            await queue.enqueue("dashboard", platform_job.id)
        except Exception as exc:
            logger.warning(
                "Redis enqueue failed; database fallback will claim dashboard export",
                extra={
                    "platform_job_id": str(platform_job.id),
                    "exception_type": type(exc).__name__,
                },
            )
    await db.refresh(export)
    return _export_response(export)


async def list_exports(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID, limit: int = 50
) -> list[ExportResponse]:
    await get_dashboard(db, context, dashboard_id)
    rows = (
        await db.scalars(
            select(DashboardExport)
            .where(
                DashboardExport.organization_id == context.organization_id,
                DashboardExport.workspace_id == _workspace(context),
                DashboardExport.dashboard_id == dashboard_id,
            )
            .order_by(DashboardExport.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [_export_response(item) for item in rows]


async def get_export(
    db: AsyncSession, context: AuthorizationContext, export_id: UUID, *, lock: bool = False
) -> DashboardExport:
    statement = select(DashboardExport).where(
        DashboardExport.id == export_id,
        DashboardExport.organization_id == context.organization_id,
        DashboardExport.workspace_id == _workspace(context),
    )
    if lock:
        statement = statement.with_for_update()
    item = await db.scalar(statement)
    if item is None:
        raise ApplicationError(
            code="DASHBOARD_EXPORT_NOT_FOUND",
            message="The requested export was not found.",
            status_code=404,
        )
    dashboard = await get_dashboard(db, context, item.dashboard_id)
    if not (await _access(db, context, dashboard))["can_view"]:
        raise ApplicationError(
            code="DASHBOARD_EXPORT_NOT_FOUND",
            message="The requested export was not found.",
            status_code=404,
        )
    return item


async def export_status(
    db: AsyncSession, context: AuthorizationContext, export_id: UUID
) -> ExportResponse:
    return _export_response(await get_export(db, context, export_id))


async def cancel_export(
    db: AsyncSession, context: AuthorizationContext, export_id: UUID, expected_version: int
) -> ExportResponse:
    item = await get_export(db, context, export_id, lock=True)
    if item.row_version != expected_version:
        raise _conflict()
    was_active = item.status != "cancelled"
    if item.status in {"completed", "failed", "cancelled", "expired"}:
        raise ApplicationError(
            code="DASHBOARD_EXPORT_NOT_CANCELLABLE",
            message="This export can no longer be cancelled.",
            status_code=409,
        )
    item.cancellation_requested = True
    if item.platform_job_id is not None:
        platform_job = await db.get(Job, item.platform_job_id)
        if platform_job is not None:
            platform_job.cancellation_requested = True
            platform_job.cancelled_by_user_id = context.user_id
            if platform_job.status in {"queued", "pending", "retrying", "waiting"}:
                platform_job.status = "cancelled"
                platform_job.cancelled_at = datetime.now(UTC)
                platform_job.completed_at = platform_job.cancelled_at
    item.row_version += 1
    if item.status == "queued":
        item.status = "cancelled"
        item.cancelled_at = datetime.now(UTC)
    await record_audit(
        db,
        "dashboard.export.cancelled",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_export",
        resource_id=item.id,
    )
    if was_active:
        await release_quota(db, context, "dashboard_delivery_schedules.max")
    await db.commit()
    return _export_response(item)


async def retry_export(
    db: AsyncSession,
    context: AuthorizationContext,
    export_id: UUID,
    expected_version: int,
    queue: JobQueue | None = None,
) -> ExportResponse:
    item = await get_export(db, context, export_id, lock=True)
    if item.row_version != expected_version:
        raise _conflict()
    if item.status not in {"failed", "cancelled"}:
        raise ApplicationError(
            code="DASHBOARD_EXPORT_NOT_RETRYABLE",
            message="This export cannot be retried.",
            status_code=409,
        )
    item.status = "queued"
    item.progress = 0
    item.cancellation_requested = False
    item.safe_error_code = None
    item.safe_error_message = None
    item.available_at = datetime.now(UTC)
    item.row_version += 1
    if item.platform_job_id is not None:
        platform_job = await db.get(Job, item.platform_job_id)
        if platform_job is not None:
            platform_job.status = "queued"
            platform_job.cancellation_requested = False
            platform_job.cancelled_at = None
            platform_job.completed_at = None
            platform_job.available_at = datetime.now(UTC)
            platform_job.row_version += 1
    await record_audit(
        db,
        "dashboard.export.retried",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_export",
        resource_id=item.id,
    )
    await db.commit()
    if queue is not None and item.platform_job_id is not None:
        try:
            await queue.enqueue("dashboard", item.platform_job_id)
        except Exception as exc:
            logger.warning(
                "Redis enqueue failed; database fallback will claim retried export",
                extra={
                    "platform_job_id": str(item.platform_job_id),
                    "exception_type": type(exc).__name__,
                },
            )
    return _export_response(item)


def _token_payload(
    item: DashboardExport, context: AuthorizationContext, expires_at: datetime
) -> bytes:
    return json.dumps(
        {
            "e": str(item.id),
            "u": str(context.user_id),
            "o": str(context.organization_id),
            "w": str(_workspace(context)),
            "x": int(expires_at.timestamp()),
            "n": secrets.token_urlsafe(8),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


async def create_download_token(
    db: AsyncSession,
    context: AuthorizationContext,
    export_id: UUID,
    settings: Settings,
) -> DownloadTokenResponse:
    item = await get_export(db, context, export_id)
    if item.status != "completed" or item.artifact_key is None:
        raise ApplicationError(
            code="DASHBOARD_EXPORT_NOT_READY",
            message="The export artifact is not ready.",
            status_code=409,
        )
    expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.DASHBOARD_DOWNLOAD_TOKEN_TTL_SECONDS
    )
    payload = _token_payload(item, context, expires_at)
    signature = hmac.new(
        settings.dashboard_download_signing_key.encode(), payload, hashlib.sha256
    ).digest()
    token = f"{_encode(payload)}.{_encode(signature)}"
    await record_audit(
        db,
        "dashboard.export.download_token.created",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_export",
        resource_id=item.id,
    )
    await db.commit()
    return DownloadTokenResponse(
        url=f"/api/v1/dashboard-exports/{item.id}/download?token={token}",
        expires_at=expires_at,
    )


def verify_download_token(
    token: str,
    item: DashboardExport,
    context: AuthorizationContext,
    settings: Settings,
) -> int:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = _decode(encoded_payload)
        signature = _decode(encoded_signature)
        expected = hmac.new(
            settings.dashboard_download_signing_key.encode(), payload, hashlib.sha256
        ).digest()
        values = cast(dict[str, object], json.loads(payload))
        valid = hmac.compare_digest(signature, expected) and all(
            (
                values.get("e") == str(item.id),
                values.get("u") == str(context.user_id),
                values.get("o") == str(context.organization_id),
                values.get("w") == str(_workspace(context)),
                int(cast(int, values.get("x", 0))) >= int(datetime.now(UTC).timestamp()),
            )
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        valid = False
    if not valid:
        raise ApplicationError(
            code="DASHBOARD_DOWNLOAD_TOKEN_INVALID",
            message="The download link is invalid or expired.",
            status_code=403,
        )
    return int(cast(int, values["x"]))


async def consume_download_token(
    token: str,
    item: DashboardExport,
    context: AuthorizationContext,
    settings: Settings,
    redis: Redis,
) -> None:
    """Atomically enforce the documented single-use export download contract."""
    expires_at = verify_download_token(token, item, context, settings)
    token_digest = hashlib.sha256(token.encode()).hexdigest()
    key = (
        f"{settings.JOB_QUEUE_PREFIX}:download:dashboard:"
        f"{context.organization_id}:{_workspace(context)}:{token_digest}"
    )
    ttl = max(1, expires_at - int(datetime.now(UTC).timestamp()) + 1)
    if not await redis.set(key, "used", ex=ttl, nx=True):
        raise ApplicationError(
            code="DASHBOARD_DOWNLOAD_TOKEN_INVALID",
            message="The download link is invalid or expired.",
            status_code=403,
        )


async def list_schedules(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID | None = None
) -> list[ScheduleResponse]:
    statement = select(DashboardDeliverySchedule).where(
        DashboardDeliverySchedule.organization_id == context.organization_id,
        DashboardDeliverySchedule.workspace_id == _workspace(context),
    )
    if dashboard_id is not None:
        await get_dashboard(db, context, dashboard_id)
        statement = statement.where(DashboardDeliverySchedule.dashboard_id == dashboard_id)
    rows = (
        await db.scalars(statement.order_by(DashboardDeliverySchedule.created_at.desc()).limit(100))
    ).all()
    return [_schedule_response(item) for item in rows]


async def create_schedule(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    payload: ScheduleCreate,
) -> ScheduleResponse:
    dashboard, version = await _published(db, context, dashboard_id)
    await consume_quota(db, context, "dashboard_delivery_schedules.max")
    item = DashboardDeliverySchedule(
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        dashboard_id=dashboard.id,
        dashboard_version_id=version.id,
        name=payload.name,
        recipients=payload.recipients,
        cc=payload.cc,
        bcc=payload.bcc,
        subject=payload.subject,
        format=payload.format,
        filters=payload.filters,
        schedule_type=payload.schedule_type,
        schedule_expression=payload.schedule_expression,
        timezone=payload.timezone,
        include_dashboard_link=payload.include_dashboard_link,
        enabled=payload.enabled,
        status="scheduled" if payload.enabled else "paused",
        max_retries=payload.max_retries,
        created_by_user_id=context.user_id,
        next_run_at=next_run(payload) if payload.enabled else None,
    )
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        "dashboard.delivery_schedule.created",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_delivery_schedule",
        resource_id=item.id,
        metadata={"dashboard_id": str(dashboard.id), "format": payload.format},
    )
    await db.commit()
    await db.refresh(item)
    return _schedule_response(item)


async def get_schedule(
    db: AsyncSession, context: AuthorizationContext, schedule_id: UUID, *, lock: bool = False
) -> DashboardDeliverySchedule:
    statement = select(DashboardDeliverySchedule).where(
        DashboardDeliverySchedule.id == schedule_id,
        DashboardDeliverySchedule.organization_id == context.organization_id,
        DashboardDeliverySchedule.workspace_id == _workspace(context),
    )
    if lock:
        statement = statement.with_for_update()
    item = await db.scalar(statement)
    if item is None:
        raise ApplicationError(
            code="DASHBOARD_DELIVERY_NOT_FOUND",
            message="The requested delivery was not found.",
            status_code=404,
        )
    await get_dashboard(db, context, item.dashboard_id)
    return item


async def update_schedule(
    db: AsyncSession,
    context: AuthorizationContext,
    schedule_id: UUID,
    payload: ScheduleUpdate,
) -> ScheduleResponse:
    item = await get_schedule(db, context, schedule_id, lock=True)
    if item.row_version != payload.expected_version:
        raise _conflict()
    for field in (
        "name",
        "recipients",
        "cc",
        "bcc",
        "subject",
        "format",
        "filters",
        "schedule_type",
        "schedule_expression",
        "timezone",
        "include_dashboard_link",
        "enabled",
        "max_retries",
    ):
        setattr(item, field, getattr(payload, field))
    item.status = "scheduled" if payload.enabled else "paused"
    item.next_run_at = next_run(payload) if payload.enabled else None
    item.row_version += 1
    await record_audit(
        db,
        "dashboard.delivery_schedule.updated",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_delivery_schedule",
        resource_id=item.id,
    )
    await db.commit()
    return _schedule_response(item)


async def delete_schedule(
    db: AsyncSession, context: AuthorizationContext, schedule_id: UUID, expected_version: int
) -> None:
    item = await get_schedule(db, context, schedule_id, lock=True)
    if item.row_version != expected_version:
        raise _conflict()
    item.enabled = False
    item.status = "cancelled"
    item.next_run_at = None
    item.row_version += 1
    await record_audit(
        db,
        "dashboard.delivery_schedule.cancelled",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_delivery_schedule",
        resource_id=item.id,
    )
    await db.commit()


async def list_delivery_runs(
    db: AsyncSession, context: AuthorizationContext, schedule_id: UUID
) -> list[DeliveryRunResponse]:
    item = await get_schedule(db, context, schedule_id)
    rows = (
        await db.scalars(
            select(DashboardDeliveryRun)
            .where(
                DashboardDeliveryRun.schedule_id == item.id,
                DashboardDeliveryRun.organization_id == context.organization_id,
                DashboardDeliveryRun.workspace_id == _workspace(context),
            )
            .order_by(DashboardDeliveryRun.created_at.desc())
            .limit(100)
        )
    ).all()
    return [DeliveryRunResponse.model_validate(row, from_attributes=True) for row in rows]


async def test_delivery(
    db: AsyncSession,
    context: AuthorizationContext,
    schedule_id: UUID,
    settings: Settings,
) -> DeliveryRunResponse:
    schedule = await get_schedule(db, context, schedule_id)
    run = DashboardDeliveryRun(
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        schedule_id=schedule.id,
        status="queued",
    )
    db.add(run)
    await db.flush()
    export = await create_export(
        db,
        context,
        schedule.dashboard_id,
        ExportCreate(
            format=cast(ExportFormat, schedule.format),
            filters=schedule.filters,
            timezone=schedule.timezone,
        ),
        settings,
        delivery_run_id=run.id,
    )
    run.export_id = export.id
    await record_audit(
        db,
        "dashboard.delivery.test.queued",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=_workspace(context),
        resource_type="dashboard_delivery_run",
        resource_id=run.id,
    )
    await db.commit()
    await db.refresh(run)
    return DeliveryRunResponse.model_validate(run, from_attributes=True)


async def preview_email(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    payload: EmailPreviewRequest,
    settings: Settings,
) -> EmailPreviewResponse:
    dashboard, version = await _published(db, context, dashboard_id)
    url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/dashboards/{dashboard.id}"
        if payload.include_dashboard_link
        else None
    )
    body = render_email_html(
        dashboard.name, version.version_number, datetime.now(UTC).isoformat(), url
    )
    return EmailPreviewResponse(
        subject=payload.subject,
        html=body,
        recipients=len(set(payload.recipients + payload.cc + payload.bcc)),
        attachments=["dashboard.pdf or dashboard.png"],
    )
