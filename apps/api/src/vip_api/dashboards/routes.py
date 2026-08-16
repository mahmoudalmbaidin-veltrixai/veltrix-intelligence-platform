"""Live, governed Dashboard Studio APIs."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import require_csrf
from vip_api.connections.dependencies import get_secret_provider
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings, get_settings
from vip_api.dashboards.query import execute_widget
from vip_api.dashboards.schemas import (
    DashboardCreate,
    DashboardDetail,
    DashboardSummary,
    EditorResponse,
    EditorSave,
    PublishedDashboardViewerResponse,
    ShareCreate,
    ShareResponse,
    SnapshotCreate,
    SnapshotResponse,
    VersionMutation,
    VersionResponse,
    WidgetDataRequest,
    WidgetDataResponse,
)
from vip_api.dashboards.services import (
    archive,
    create_dashboard,
    create_share,
    create_snapshot,
    editor,
    get_dashboard,
    list_dashboards,
    list_shares,
    list_snapshots,
    publish,
    restore,
    revoke_share,
    save_editor,
    versions,
    viewer,
)
from vip_api.database.session import get_db_session
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_capability, require_governance
from vip_api.redis.client import RedisClient

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


def policy(
    permission: str,
    *,
    feature: str = "dashboard_studio",
    entitlement: str = "dashboard_studio",
    quota: str | None = None,
) -> object:
    return require_governance(permission, feature=feature, entitlement=entitlement, quota=quota)


dashboard_capability = require_capability("dashboard_studio", "dashboard_studio")


@router.get("", response_model=list[DashboardSummary])
async def index(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(policy("dashboard.read"))],
    search: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern="^(draft|published)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[DashboardSummary]:
    return await list_dashboards(
        db, context, search=search, status=status, limit=limit, offset=offset
    )


@router.post(
    "", response_model=DashboardDetail, status_code=201, dependencies=[Depends(require_csrf)]
)
async def create(
    payload: DashboardCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(policy("dashboard.create", quota="dashboards.max"))
    ],
) -> DashboardDetail:
    return await create_dashboard(db, context, payload)


@router.get("/{dashboard_id}", response_model=DashboardDetail)
async def show(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(policy("dashboard.read"))],
) -> DashboardDetail:
    from vip_api.dashboards.services import detail

    return await detail(db, context, await get_dashboard(db, context, dashboard_id))


@router.get("/{dashboard_id}/editor", response_model=EditorResponse)
async def show_editor(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dashboard_capability)],
) -> EditorResponse:
    return await editor(db, context, dashboard_id)


@router.put(
    "/{dashboard_id}/editor", response_model=EditorResponse, dependencies=[Depends(require_csrf)]
)
async def update_editor(
    dashboard_id: UUID,
    payload: EditorSave,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dashboard_capability)],
) -> EditorResponse:
    return await save_editor(db, context, dashboard_id, payload)


@router.post(
    "/{dashboard_id}/publish", response_model=VersionResponse, dependencies=[Depends(require_csrf)]
)
async def publish_dashboard(
    dashboard_id: UUID,
    payload: VersionMutation,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(
            policy(
                "dashboard.publish",
                feature="dashboard_publishing",
                entitlement="dashboard_publishing",
            )
        ),
    ],
) -> VersionResponse:
    return await publish(
        db, context, dashboard_id, payload.expected_version, payload.change_summary
    )


@router.post("/{dashboard_id}/archive", status_code=204, dependencies=[Depends(require_csrf)])
async def archive_dashboard(
    dashboard_id: UUID,
    expected_version: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(policy("dashboard.archive"))],
) -> Response:
    await archive(db, context, dashboard_id, expected_version)
    return Response(status_code=204)


@router.delete("/{dashboard_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_dashboard(
    dashboard_id: UUID,
    expected_version: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(policy("dashboard.delete"))],
) -> Response:
    await archive(db, context, dashboard_id, expected_version)
    return Response(status_code=204)


@router.get("/{dashboard_id}/viewer", response_model=PublishedDashboardViewerResponse)
async def published_viewer(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dashboard_capability)],
) -> PublishedDashboardViewerResponse:
    return await viewer(db, context, dashboard_id)


@router.get("/{dashboard_id}/versions", response_model=list[VersionResponse])
async def version_history(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(policy("dashboard.versions.read"))],
) -> list[VersionResponse]:
    return await versions(db, context, dashboard_id)


@router.post(
    "/{dashboard_id}/versions/{version_id}/restore",
    response_model=EditorResponse,
    dependencies=[Depends(require_csrf)],
)
async def restore_version(
    dashboard_id: UUID,
    version_id: UUID,
    payload: VersionMutation,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(policy("dashboard.versions.restore"))],
) -> EditorResponse:
    return await restore(db, context, dashboard_id, version_id, payload.expected_version)


@router.get("/{dashboard_id}/shares", response_model=list[ShareResponse])
async def shares_index(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(
            policy("dashboard.share", feature="dashboard_sharing", entitlement="dashboard_sharing")
        ),
    ],
) -> list[ShareResponse]:
    return await list_shares(db, context, dashboard_id)


@router.post(
    "/{dashboard_id}/shares",
    response_model=ShareResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def shares_create(
    dashboard_id: UUID,
    payload: ShareCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(
            policy("dashboard.share", feature="dashboard_sharing", entitlement="dashboard_sharing")
        ),
    ],
) -> ShareResponse:
    return await create_share(db, context, dashboard_id, payload)


@router.delete(
    "/{dashboard_id}/shares/{share_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def shares_revoke(
    dashboard_id: UUID,
    share_id: UUID,
    expected_version: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(
            policy("dashboard.share", feature="dashboard_sharing", entitlement="dashboard_sharing")
        ),
    ],
) -> Response:
    await revoke_share(db, context, dashboard_id, share_id, expected_version)
    return Response(status_code=204)


@router.get("/{dashboard_id}/snapshots", response_model=list[SnapshotResponse])
async def snapshots_index(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(
            policy(
                "dashboard.snapshot.read",
                feature="dashboard_snapshots",
                entitlement="dashboard_snapshots",
            )
        ),
    ],
) -> list[SnapshotResponse]:
    return await list_snapshots(db, context, dashboard_id)


@router.post(
    "/{dashboard_id}/snapshots",
    response_model=SnapshotResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def snapshots_create(
    dashboard_id: UUID,
    payload: SnapshotCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext,
        Depends(
            policy(
                "dashboard.snapshot.create",
                feature="dashboard_snapshots",
                entitlement="dashboard_snapshots",
                quota="dashboard_snapshots.max_per_dashboard",
            )
        ),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
) -> SnapshotResponse:
    published = await viewer(db, context, dashboard_id)
    version_number = published.version
    results: dict[str, object] = {}
    for page in published.snapshot.pages:
        for widget in page.widgets:
            if widget.semantic_model_id is None or widget.hidden:
                continue
            result = await execute_widget(
                db,
                context,
                dashboard_id,
                widget.id,
                WidgetDataRequest(
                    dashboard_version=version_number,
                    preview=False,
                    filters=payload.filter_state,
                ),
                settings,
                provider,
            )
            results[str(widget.id)] = result.model_dump(mode="json")
    data_snapshot: dict[str, object] = {
        "schema_version": 1,
        "dashboard_version": version_number,
        "widgets": results,
    }
    if (
        len(json.dumps(data_snapshot, separators=(",", ":")).encode())
        > settings.DASHBOARD_SNAPSHOT_MAX_BYTES
    ):
        from vip_api.core.errors import ApplicationError

        raise ApplicationError(
            code="DASHBOARD_SNAPSHOT_TOO_LARGE",
            message="The dashboard result is too large to snapshot.",
            status_code=422,
        )
    return await create_snapshot(db, context, dashboard_id, payload, settings, data_snapshot)


@router.post(
    "/{dashboard_id}/widgets/{widget_id}/data",
    response_model=WidgetDataResponse,
    dependencies=[Depends(require_csrf)],
)
async def widget_data(
    dashboard_id: UUID,
    widget_id: UUID,
    payload: WidgetDataRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(dashboard_capability)],
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
    request: Request,
) -> WidgetDataResponse:
    redis_client: RedisClient = request.app.state.redis
    return await execute_widget(
        db,
        context,
        dashboard_id,
        widget_id,
        payload,
        settings,
        provider,
        redis_client=redis_client,
        locale=request.headers.get("X-Locale", "en-US")[:32],
        timezone=request.headers.get("X-Timezone", "UTC")[:64],
    )
