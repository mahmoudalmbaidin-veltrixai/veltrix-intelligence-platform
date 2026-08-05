"""Dashboard widget adapter over the B5 semantic-query service."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.secrets import SecretProvider
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.dashboard_delivery.cache import cache_key, read_cache, write_cache
from vip_api.dashboards.models import DashboardVersion, DashboardWidget
from vip_api.dashboards.schemas import WidgetDataRequest, WidgetDataResponse, WidgetInput
from vip_api.dashboards.services import _access, get_dashboard
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.redis.client import RedisClient
from vip_api.semantic.query import execute_query
from vip_api.semantic.schemas import QueryFilter, QueryOrder, SemanticQueryRequest


def _shape(
    widget: WidgetInput, rows: list[dict[str, object]]
) -> tuple[dict[str, object], dict[str, object]]:
    metrics = widget.query.metrics
    dimensions = widget.query.dimensions
    if widget.type == "kpi":
        value = rows[0].get(metrics[0]) if rows else None
        return {"value": value}, {"value_field": metrics[0]}
    if widget.type == "table":
        return {"rows": rows}, {"columns": dimensions + metrics}
    categories = [row.get(dimensions[0]) for row in rows] if dimensions else list(range(len(rows)))
    series = [{"key": metric, "values": [row.get(metric) for row in rows]} for metric in metrics]
    return {"categories": categories, "series": series}, {
        "category_field": dimensions[0] if dimensions else None,
        "series_fields": metrics,
    }


async def execute_widget(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    widget_id: UUID,
    payload: WidgetDataRequest,
    settings: Settings,
    provider: SecretProvider,
    *,
    published_version_id: UUID | None = None,
    redis_client: RedisClient | None = None,
    locale: str = "en-US",
    timezone: str = "UTC",
) -> WidgetDataResponse:
    dashboard = await get_dashboard(db, context, dashboard_id)
    access = await _access(db, context, dashboard)
    widget: WidgetInput | None = None
    version_number = dashboard.row_version
    if payload.preview:
        if not access["can_edit"]:
            raise ApplicationError(
                code="DASHBOARD_ACCESS_DENIED",
                message="Draft preview access is denied.",
                status_code=403,
            )
        row = await db.scalar(
            select(DashboardWidget).where(
                DashboardWidget.id == widget_id,
                DashboardWidget.dashboard_id == dashboard.id,
                DashboardWidget.organization_id == dashboard.organization_id,
                DashboardWidget.workspace_id == dashboard.workspace_id,
            )
        )
        if row:
            widget = WidgetInput.model_validate(
                {
                    "id": row.id,
                    "page_id": row.page_id,
                    "type": row.widget_type,
                    "title": row.title,
                    "description": row.description,
                    "semantic_model_id": row.semantic_model_id,
                    "query": row.query_definition,
                    "config": row.visualization_config,
                    "layout": row.layout,
                    "filters": row.filters,
                    "interactions": row.interactions,
                    "content": row.content,
                    "hidden": row.is_hidden,
                }
            )
    else:
        if not access["can_view"] or dashboard.published_version_id is None:
            raise ApplicationError(
                code="DASHBOARD_ACCESS_DENIED",
                message="Dashboard access is denied.",
                status_code=403,
            )
        version = await db.scalar(
            select(DashboardVersion).where(
                DashboardVersion.id == (published_version_id or dashboard.published_version_id),
                DashboardVersion.dashboard_id == dashboard.id,
                DashboardVersion.organization_id == dashboard.organization_id,
                DashboardVersion.workspace_id == dashboard.workspace_id,
                DashboardVersion.version_type == "published",
            )
        )
        if version is not None:
            version_number = version.version_number
            if (
                payload.dashboard_version is not None
                and payload.dashboard_version != version_number
            ):
                raise ApplicationError(
                    code="DASHBOARD_VERSION_NOT_FOUND",
                    message="The requested published dashboard version is unavailable.",
                    status_code=404,
                )
            pages = cast(list[dict[str, object]], version.snapshot.get("pages", []))
            for page in pages:
                items = cast(list[dict[str, object]], page.get("widgets", []))
                for item in items:
                    if str(item.get("id")) == str(widget_id) and not item.get("hidden", False):
                        widget = WidgetInput.model_validate(item)
                        break
    if widget is None or widget.semantic_model_id is None:
        raise ApplicationError(
            code="DASHBOARD_WIDGET_NOT_FOUND",
            message="The requested widget was not found.",
            status_code=404,
        )
    result_cache_key: str | None = None
    if not payload.preview and version is not None:
        result_cache_key = await cache_key(
            db,
            context,
            dashboard.id,
            version.id,
            version.version_number,
            widget,
            payload,
            access,
            locale,
            timezone,
        )
        cached = await read_cache(redis_client, result_cache_key, context, settings)
        if cached is not None:
            return cached
    runtime_filters: list[QueryFilter] = []
    allowed = {item.field for item in widget.query.filters} | set(widget.query.dimensions)
    if not payload.preview and version is not None:
        snapshot_filters = cast(list[dict[str, object]], version.snapshot.get("filters", []))
        for item in snapshot_filters:
            mapped_widgets = cast(list[object], item.get("widget_ids", []))
            if str(widget_id) in {str(value) for value in mapped_widgets} and str(
                item.get("semantic_model_id")
            ) == str(widget.semantic_model_id):
                dimension_key = item.get("dimension_key")
                if isinstance(dimension_key, str):
                    allowed.add(dimension_key)
    for key, value in sorted(payload.filters.items()):
        if key not in allowed:
            raise ApplicationError(
                code="DASHBOARD_FILTER_INVALID",
                message="A runtime filter is not valid for this widget.",
                status_code=422,
            )
        runtime_filters.append(
            QueryFilter(
                field=key, operator="in" if isinstance(value, list) else "equals", value=value
            )
        )
    query = SemanticQueryRequest(
        semantic_model_id=widget.semantic_model_id,
        metrics=widget.query.metrics,
        dimensions=widget.query.dimensions,
        filters=[QueryFilter.model_validate(item.model_dump()) for item in widget.query.filters]
        + runtime_filters,
        order_by=[QueryOrder.model_validate(item.model_dump()) for item in widget.query.order_by],
        limit=payload.limit_override or widget.query.limit,
    )
    try:
        result = await execute_query(db, context, query, settings, provider)
    except ApplicationError as exc:
        await record_audit(
            db,
            "dashboard.query.failed",
            actor_user_id=context.user_id,
            organization_id=dashboard.organization_id,
            workspace_id=dashboard.workspace_id,
            outcome="failure",
            reason_code=exc.code,
            resource_type="dashboard",
            resource_id=dashboard.id,
            metadata={"widget_id": str(widget_id), "widget_type": widget.type},
        )
        await db.commit()
        raise ApplicationError(
            code="DASHBOARD_QUERY_FAILED",
            message="The widget data could not be loaded.",
            status_code=exc.status_code,
        ) from exc
    rows = cast(list[dict[str, object]], [dict(row) for row in result.rows])
    shaped, hint = _shape(widget, rows)
    response = WidgetDataResponse(
        dashboard_id=dashboard.id,
        widget_id=widget_id,
        dashboard_version=version_number,
        widget_type=widget.type,
        columns=[item.model_dump(mode="json") for item in result.columns],
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        render_hint=hint,
        shaped=shaped,
        execution={"query_id": str(result.query_id), **result.execution.model_dump(mode="json")},
        correlation_id=result.correlation_id,
    )
    if result_cache_key is not None:
        await write_cache(redis_client, result_cache_key, response, settings)
    return response
