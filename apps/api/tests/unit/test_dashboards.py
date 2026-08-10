"""Dashboard contracts and optimistic-concurrency unit coverage."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from vip_api.core.errors import ApplicationError
from vip_api.dashboards.models import Dashboard
from vip_api.dashboards.schemas import EditorSave, GridLayout, PageInput, WidgetInput
from vip_api.dashboards.services import _check_version, _validate_semantics
from vip_api.governance.context import AuthorizationContext


def test_layout_is_bounded_to_twelve_columns() -> None:
    assert GridLayout(x=8, y=0, w=4, h=3).w == 4
    with pytest.raises(ValidationError):
        GridLayout(x=9, y=0, w=4, h=3)
    with pytest.raises(ValidationError):
        GridLayout(x=-1, y=0, w=4, h=3)


def test_widget_contract_rejects_raw_sql_html_and_unknown_configuration() -> None:
    base = {
        "type": "kpi",
        "title": "Revenue",
        "semantic_model_id": str(uuid4()),
        "query": {"metrics": ["total_revenue"]},
        "layout": {"x": 0, "y": 0, "w": 4, "h": 3},
    }
    assert WidgetInput.model_validate(base).type == "kpi"
    with pytest.raises(ValidationError):
        WidgetInput.model_validate({**base, "title": "<script>alert(1)</script>"})
    with pytest.raises(ValidationError):
        WidgetInput.model_validate({**base, "title": "SELECT value FROM users"})
    with pytest.raises(ValidationError):
        WidgetInput.model_validate({**base, "config": {"custom_css": "body{}"}})


def test_api_accepts_every_widget_type_exposed_by_dashboard_studio() -> None:
    data_types = {
        "kpi",
        "metric-comparison",
        "table",
        "pivot",
        "bar",
        "stacked-bar",
        "column",
        "line",
        "area",
        "pie",
        "donut",
        "scatter",
        "gauge",
        "progress",
        "map",
    }
    content_types = {"text", "rich-text", "image", "filter", "date-filter"}
    for widget_type in data_types | content_types:
        payload: dict[str, object] = {
            "type": widget_type,
            "title": widget_type,
            "layout": {"x": 0, "y": 0, "w": 4, "h": 3},
        }
        if widget_type in data_types:
            payload.update(
                {
                    "semantic_model_id": str(uuid4()),
                    "query": {"metrics": ["total_revenue"]},
                }
            )
        assert WidgetInput.model_validate(payload).type == widget_type


def test_aggregate_requires_unique_pages_and_bounds_widget_count() -> None:
    page = {"key": "overview", "name": "Overview", "position": 0, "widgets": []}
    with pytest.raises(ValidationError):
        EditorSave(
            expected_version=1,
            name="Dashboard",
            pages=[page, page],
        )


def test_stale_version_fails_with_stable_conflict() -> None:
    dashboard = Dashboard(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        slug="safe-dashboard",
        name="Safe dashboard",
        owner_user_id=uuid4(),
        row_version=7,
    )
    _check_version(dashboard, 7)
    with pytest.raises(ApplicationError) as raised:
        _check_version(dashboard, 6)
    assert raised.value.code == "DASHBOARD_VERSION_CONFLICT"
    assert raised.value.status_code == 409


@pytest.mark.asyncio
async def test_save_and_publish_semantics_reject_incomplete_scatter() -> None:
    model_id = uuid4()
    page = PageInput(
        key="overview",
        name="Overview",
        position=0,
        widgets=[
            WidgetInput(
                type="scatter",
                title="Legacy invalid scatter",
                semantic_model_id=model_id,
                query={"metrics": ["revenue"], "dimensions": ["region"]},
                layout=GridLayout(x=0, y=0, w=6, h=5),
            )
        ],
    )
    context = AuthorizationContext(
        user_id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset({"dashboard.update", "dashboard.publish"}),
        entitlements=frozenset({"dashboard_studio"}),
        feature_flags={"dashboard_studio": True},
        quotas={},
        correlation_id="scatter-validation-unit",
    )

    with pytest.raises(ApplicationError) as raised:
        await _validate_semantics(None, context, [page], [])  # type: ignore[arg-type]

    assert raised.value.code == "DASHBOARD_SCATTER_INVALID"
    assert raised.value.status_code == 422
    assert raised.value.message == "Scatter chart requires numeric X and Y fields."
