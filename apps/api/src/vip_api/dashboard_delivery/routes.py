"""Governed B6.5 export, artifact, and delivery APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import require_csrf
from vip_api.core.config import Settings, get_settings
from vip_api.core.errors import ApplicationError
from vip_api.dashboard_delivery.schemas import (
    DeliveryRunResponse,
    DownloadTokenResponse,
    EmailPreviewRequest,
    EmailPreviewResponse,
    ExportCreate,
    ExportMutation,
    ExportResponse,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)
from vip_api.dashboard_delivery.services import (
    cancel_export,
    consume_download_token,
    create_download_token,
    create_export,
    create_schedule,
    delete_schedule,
    export_status,
    get_export,
    list_delivery_runs,
    list_exports,
    list_schedules,
    preview_email,
    retry_export,
    test_delivery,
    update_schedule,
)
from vip_api.dashboard_delivery.storage import FileArtifactStorage
from vip_api.database.session import get_db_session
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_governance
from vip_api.jobs.queue import RedisJobQueue
from vip_api.redis.client import RedisClient

router = APIRouter(tags=["dashboard exports and deliveries"])


def export_policy(permission: str, quota: str | None = None) -> object:
    return require_governance(
        permission,
        feature="dashboard_exports",
        entitlement="dashboard_exports",
        quota=quota,
    )


def delivery_policy(permission: str, quota: str | None = None) -> object:
    return require_governance(
        permission,
        feature="dashboard_delivery",
        entitlement="dashboard_delivery",
        quota=quota,
    )


@router.post(
    "/dashboards/{dashboard_id}/exports",
    response_model=ExportResponse,
    status_code=202,
    dependencies=[Depends(require_csrf)],
)
async def exports_create(
    dashboard_id: UUID,
    payload: ExportCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(export_policy("dashboard.export", "dashboard_exports.per_day")),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExportResponse:
    redis: RedisClient = request.app.state.redis
    queue = RedisJobQueue(redis.client, settings.JOB_QUEUE_PREFIX)
    return await create_export(db, context, dashboard_id, payload, settings, queue=queue)


@router.get("/dashboards/{dashboard_id}/exports", response_model=list[ExportResponse])
async def exports_index(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(export_policy("dashboard.export.read"))],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ExportResponse]:
    return await list_exports(db, context, dashboard_id, limit)


@router.get("/dashboard-exports/{export_id}", response_model=ExportResponse)
async def exports_show(
    export_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(export_policy("dashboard.export.read"))],
) -> ExportResponse:
    return await export_status(db, context, export_id)


@router.post(
    "/dashboard-exports/{export_id}/cancel",
    response_model=ExportResponse,
    dependencies=[Depends(require_csrf)],
)
async def exports_cancel(
    export_id: UUID,
    payload: ExportMutation,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(export_policy("dashboard.export.cancel"))],
) -> ExportResponse:
    return await cancel_export(db, context, export_id, payload.expected_version)


@router.post(
    "/dashboard-exports/{export_id}/retry",
    response_model=ExportResponse,
    dependencies=[Depends(require_csrf)],
)
async def exports_retry(
    export_id: UUID,
    payload: ExportMutation,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(export_policy("dashboard.export"))],
) -> ExportResponse:
    settings: Settings = request.app.state.settings
    redis: RedisClient = request.app.state.redis
    queue = RedisJobQueue(redis.client, settings.JOB_QUEUE_PREFIX)
    return await retry_export(db, context, export_id, payload.expected_version, queue)


@router.post(
    "/dashboard-exports/{export_id}/download-token",
    response_model=DownloadTokenResponse,
    dependencies=[Depends(require_csrf)],
)
async def exports_download_token(
    export_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(export_policy("dashboard.export.download"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DownloadTokenResponse:
    return await create_download_token(db, context, export_id, settings)


@router.get("/dashboard-exports/{export_id}/download")
async def exports_download(
    export_id: UUID,
    token: Annotated[str, Query(min_length=40, max_length=2048)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(export_policy("dashboard.export.download"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    item = await get_export(db, context, export_id)
    if item.status != "completed" or item.artifact_key is None:
        raise ApplicationError(
            code="DASHBOARD_EXPORT_NOT_READY",
            message="The export artifact is not ready.",
            status_code=409,
        )
    if item.expires_at is None or item.expires_at <= datetime.now(UTC):
        raise ApplicationError(
            code="DASHBOARD_EXPORT_EXPIRED",
            message="The export artifact has expired.",
            status_code=410,
        )
    redis_client: RedisClient = request.app.state.redis
    await consume_download_token(token, item, context, settings, redis_client.client)
    content = await FileArtifactStorage(settings).read(item.artifact_key)
    await record_audit(
        db,
        "dashboard.export.downloaded",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type="dashboard_export",
        resource_id=item.id,
    )
    await db.commit()
    return Response(
        content=content,
        media_type=item.artifact_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="dashboard.{item.format}"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/dashboard-deliveries", response_model=list[ScheduleResponse])
async def deliveries_all(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(delivery_policy("dashboard.delivery.read"))],
) -> list[ScheduleResponse]:
    return await list_schedules(db, context)


@router.get("/dashboards/{dashboard_id}/deliveries", response_model=list[ScheduleResponse])
async def deliveries_index(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(delivery_policy("dashboard.delivery.read"))],
) -> list[ScheduleResponse]:
    return await list_schedules(db, context, dashboard_id)


@router.post(
    "/dashboards/{dashboard_id}/deliveries",
    response_model=ScheduleResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def deliveries_create(
    dashboard_id: UUID,
    payload: ScheduleCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(delivery_policy("dashboard.delivery.manage", "dashboard_delivery_schedules.max")),
    ],
) -> ScheduleResponse:
    return await create_schedule(db, context, dashboard_id, payload)


@router.put(
    "/dashboard-deliveries/{schedule_id}",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_csrf)],
)
async def deliveries_update(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(delivery_policy("dashboard.delivery.manage"))],
) -> ScheduleResponse:
    return await update_schedule(db, context, schedule_id, payload)


@router.delete(
    "/dashboard-deliveries/{schedule_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def deliveries_delete(
    schedule_id: UUID,
    expected_version: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(delivery_policy("dashboard.delivery.manage"))],
) -> Response:
    await delete_schedule(db, context, schedule_id, expected_version)
    return Response(status_code=204)


@router.get(
    "/dashboard-deliveries/{schedule_id}/history",
    response_model=list[DeliveryRunResponse],
)
async def deliveries_history(
    schedule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(delivery_policy("dashboard.delivery.read"))],
) -> list[DeliveryRunResponse]:
    return await list_delivery_runs(db, context, schedule_id)


@router.post(
    "/dashboard-deliveries/{schedule_id}/test",
    response_model=DeliveryRunResponse,
    status_code=202,
    dependencies=[Depends(require_csrf)],
)
async def deliveries_test(
    schedule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(delivery_policy("dashboard.delivery.send"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeliveryRunResponse:
    return await test_delivery(db, context, schedule_id, settings)


@router.post(
    "/dashboards/{dashboard_id}/deliveries/preview-email",
    response_model=EmailPreviewResponse,
    dependencies=[Depends(require_csrf)],
)
async def deliveries_preview(
    dashboard_id: UUID,
    payload: EmailPreviewRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(delivery_policy("dashboard.delivery.manage"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailPreviewResponse:
    return await preview_email(db, context, dashboard_id, payload, settings)
