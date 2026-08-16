"""Published Dashboard Viewer API contract regression coverage."""

from typing import cast

from vip_api.core.config import Settings
from vip_api.main import create_application


def _component(document: dict[str, object], name: str) -> dict[str, object]:
    components = cast(dict[str, object], document["components"])
    schemas = cast(dict[str, object], components["schemas"])
    return cast(dict[str, object], schemas[name])


def test_published_viewer_openapi_declares_the_runtime_contract(settings: Settings) -> None:
    document = create_application(settings).openapi()
    paths = cast(dict[str, object], document["paths"])
    path = cast(dict[str, object], paths["/api/v1/dashboards/{dashboard_id}/viewer"])
    operation = cast(dict[str, object], path["get"])
    responses = cast(dict[str, object], operation["responses"])
    success = cast(dict[str, object], responses["200"])
    content = cast(dict[str, object], success["content"])
    media_type = cast(dict[str, object], content["application/json"])

    assert media_type["schema"] == {"$ref": "#/components/schemas/PublishedDashboardViewerResponse"}
    viewer = _component(document, "PublishedDashboardViewerResponse")
    assert set(cast(list[str], viewer["required"])) == {
        "dashboard",
        "version",
        "snapshot",
        "access",
    }
    assert viewer["additionalProperties"] is False

    dashboard = _component(document, "PublishedDashboardMetadata")
    assert set(cast(list[str], dashboard["required"])) == {
        "id",
        "slug",
        "name",
        "description",
        "tags",
        "status",
        "owner_user_id",
        "published_at",
    }
    snapshot = _component(document, "PublishedDashboardSnapshot")
    assert set(cast(list[str], snapshot["required"])) == {
        "schema_version",
        "dashboard",
        "pages",
        "filters",
    }
    assert snapshot["additionalProperties"] is False
