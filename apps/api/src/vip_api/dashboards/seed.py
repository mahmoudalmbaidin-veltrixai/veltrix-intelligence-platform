"""Idempotent local Dashboard Studio demo seed."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.dashboards.models import Dashboard, DashboardPage, DashboardVersion, DashboardWidget
from vip_api.semantic.models import SemanticModel


async def seed_dashboard_demo(db: AsyncSession) -> None:
    model = await db.scalar(
        select(SemanticModel).where(
            SemanticModel.key == "sales_demo", SemanticModel.status == "published"
        )
    )
    if model is None or model.created_by_user_id is None:
        raise RuntimeError("Run B5 dataset and semantic seeds before seed-dashboard-demo")
    dashboard = await db.scalar(
        select(Dashboard).where(
            Dashboard.organization_id == model.organization_id,
            Dashboard.workspace_id == model.workspace_id,
            Dashboard.slug == "sales-performance",
        )
    )
    if dashboard is not None and dashboard.published_version_id is not None:
        return
    if dashboard is None:
        dashboard = Dashboard(
            id=uuid4(),
            organization_id=model.organization_id,
            workspace_id=model.workspace_id,
            slug="sales-performance",
            name="Sales Performance",
            description="Live B6 dashboard backed by the B5 Sales Analytics semantic model.",
            owner_user_id=model.created_by_user_id,
            created_by_user_id=model.created_by_user_id,
            updated_by_user_id=model.created_by_user_id,
            tags=["demo", "sales"],
        )
        page = DashboardPage(
            id=uuid4(),
            organization_id=model.organization_id,
            workspace_id=model.workspace_id,
            dashboard_id=dashboard.id,
            page_key="overview",
            name="Overview",
            position=0,
        )
        dashboard.default_page_id = page.id
        db.add_all(
            (
                dashboard,
                page,
                _widget(dashboard, page, model, "kpi", "Total Revenue", 0, 4),
                _widget(dashboard, page, model, "bar", "Revenue by Country", 4, 8),
            )
        )
        await db.flush()
    stored_page = await db.scalar(
        select(DashboardPage).where(DashboardPage.dashboard_id == dashboard.id)
    )
    assert stored_page is not None
    widgets = (
        await db.scalars(
            select(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard.id)
        )
    ).all()
    snapshot = {
        "schema_version": 1,
        "dashboard": {
            "id": str(dashboard.id),
            "slug": dashboard.slug,
            "name": dashboard.name,
            "description": dashboard.description,
            "tags": dashboard.tags,
        },
        "pages": [
            {
                "id": str(stored_page.id),
                "key": stored_page.page_key,
                "name": stored_page.name,
                "description": stored_page.description,
                "position": stored_page.position,
                "canvas": stored_page.canvas,
                "widgets": [_widget_snapshot(item) for item in widgets],
            }
        ],
        "filters": [],
    }
    version = DashboardVersion(
        id=uuid4(),
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        dashboard_id=dashboard.id,
        version_number=1,
        version_type="published",
        snapshot=snapshot,
        created_by_user_id=model.created_by_user_id,
        published_at=datetime.now(UTC),
        change_summary="Initial safe demo publication",
    )
    db.add(version)
    dashboard.published_version_id = version.id
    dashboard.status = "published"
    await db.commit()


def _widget(
    dashboard: Dashboard,
    page: DashboardPage,
    model: SemanticModel,
    kind: str,
    title: str,
    x: int,
    width: int,
) -> DashboardWidget:
    return DashboardWidget(
        organization_id=model.organization_id,
        workspace_id=model.workspace_id,
        dashboard_id=dashboard.id,
        page_id=page.id,
        widget_type=kind,
        title=title,
        semantic_model_id=model.id,
        query_definition={
            "metrics": ["total_revenue"],
            "dimensions": [] if kind == "kpi" else ["country"],
            "filters": [],
            "order_by": [] if kind == "kpi" else [{"field": "total_revenue", "direction": "desc"}],
            "limit": 1 if kind == "kpi" else 20,
        },
        visualization_config={"number_style": "currency", "currency": "SAR", "decimals": 2},
        layout={"x": x, "y": 0, "w": width, "h": 3 if kind == "kpi" else 5},
    )


def _widget_snapshot(widget: DashboardWidget) -> dict[str, object]:
    return {
        "id": str(widget.id),
        "page_id": str(widget.page_id),
        "type": widget.widget_type,
        "title": widget.title,
        "description": widget.description,
        "semantic_model_id": str(widget.semantic_model_id),
        "query": widget.query_definition,
        "config": widget.visualization_config,
        "layout": widget.layout,
        "filters": widget.filters,
        "interactions": widget.interactions,
        "content": widget.content,
        "hidden": widget.is_hidden,
    }
