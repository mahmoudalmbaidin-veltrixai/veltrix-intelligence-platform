"""B6.5 renderer, scheduler, signed-download, and cache security tests."""

import csv
import io
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import cast
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import SecretStr
from redis.asyncio import Redis

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.dashboard_delivery.cache import _digest
from vip_api.dashboard_delivery.email import DashboardEmail, EmailAttachment, _compose_message
from vip_api.dashboard_delivery.models import DashboardExport
from vip_api.dashboard_delivery.rendering import (
    CsvDashboardRenderer,
    JsonDashboardRenderer,
    PdfDashboardRenderer,
    PngDashboardRenderer,
    RenderDocument,
    _conditional_color,
    _display_text,
    _formatted_value,
    _wrap_text,
)
from vip_api.dashboard_delivery.scheduling import next_run
from vip_api.dashboard_delivery.schemas import ScheduleCreate
from vip_api.dashboard_delivery.services import (
    _encode,
    _token_payload,
    consume_download_token,
    verify_download_token,
)
from vip_api.governance.context import AuthorizationContext


def test_mixed_arabic_text_is_shaped_without_reversing_latin_text() -> None:
    source = "Enterprise Revenue / إيرادات المؤسسة"
    display = _display_text(source)
    assert display != source
    assert "Enterprise Revenue /" in display
    assert any("\ufb50" <= character <= "\ufeff" for character in display)


def test_bidi_wrapping_preserves_every_logical_word() -> None:
    source = "Enterprise الإيرادات 2026 / الإيرادات المؤسسية الطويلة"
    lines = _wrap_text(source, 90, lambda value: len(value) * 8)
    assert len(lines) > 1
    rendered = " ".join(lines)
    assert "Enterprise" in rendered
    assert "2026" in rendered
    assert all(len(line) > 0 for line in lines)


def test_export_number_and_conditional_formatting_matches_definition() -> None:
    widget: dict[str, object] = {
        "config": {
            "number_style": "currency",
            "currency": "SAR",
            "decimals": 2,
            "conditional": [{"when": "gt", "value": 40, "color": "#DC2626"}],
        }
    }
    assert _formatted_value(42, widget) == "SAR 42.00"
    assert _conditional_color(42, widget, "#000000") == "#DC2626"


def test_email_composition_preserves_attachments_and_hides_bcc() -> None:
    message = DashboardEmail(
        recipients=["owner@example.com"],
        cc=["finance@example.com"],
        bcc=["audit@example.com"],
        subject="Executive dashboard",
        html="<h1>Executive dashboard</h1>",
        attachments=[
            EmailAttachment(
                filename="dashboard.pdf",
                content_type="application/pdf",
                content=b"%PDF-1.7",
            )
        ],
    )
    email = _compose_message(message, "no-reply@example.com", uuid4())
    assert email["To"] == "owner@example.com"
    assert email["Cc"] == "finance@example.com"
    assert email["Bcc"] is None
    assert email["Message-ID"]
    attachment = next(
        part for part in email.iter_attachments() if part.get_filename() == "dashboard.pdf"
    )
    assert attachment.get_payload(decode=True) == b"%PDF-1.7"


def document(widget_type: str = "table") -> RenderDocument:
    dashboard_id, organization_id, workspace_id, widget_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    return RenderDocument(
        dashboard_id=dashboard_id,
        dashboard_version_id=uuid4(),
        dashboard_version=4,
        organization_id=organization_id,
        workspace_id=workspace_id,
        generated_at=datetime.now(UTC),
        dashboard_name="Quarterly Results",
        snapshot={
            "schema_version": 1,
            "dashboard": {"id": str(dashboard_id), "name": "Quarterly Results"},
            "filters": [{"key": "region", "label": "Region"}],
            "pages": [
                {
                    "key": "overview",
                    "name": "Overview",
                    "position": 0,
                    "widgets": [
                        {
                            "id": str(widget_id),
                            "type": widget_type,
                            "title": "Revenue",
                            "hidden": False,
                            "layout": {"x": 2, "y": 3, "w": 7, "h": 5},
                            "config": {"decimals": 0, "show_labels": True},
                            "interactions": {"crossFilter": True, "drillDown": False},
                        }
                    ],
                }
            ],
        },
        widget_results={
            str(widget_id): {
                "rows": [{"region": "EMEA", "revenue": 42}],
                "columns": [],
                "row_count": 1,
                "truncated": False,
                "shaped": {"value": 42},
                "execution": {"query_id": str(uuid4()), "sql": "SELECT secret"},
                "correlation_id": "internal",
            }
        },
        filters={"region": "EMEA"},
        locale="en-US",
        timezone="UTC",
    )


def test_renderers_produce_real_bounded_formats_without_query_metadata() -> None:
    source = document()
    pdf = PdfDashboardRenderer().render(source)
    png = PngDashboardRenderer().render(source)
    json_export = JsonDashboardRenderer().render(source)
    csv = CsvDashboardRenderer().render(source)
    assert pdf.content.startswith(b"%PDF") and pdf.content_type == "application/pdf"
    assert png.content.startswith(b"\x89PNG") and png.content_type == "image/png"
    assert b"SELECT secret" not in json_export.content
    assert b"query_id" not in json_export.content
    assert b"EMEA" in csv.content and csv.content_type.startswith("text/csv")


def test_exports_preserve_the_published_definition_and_grid_contract() -> None:
    source = document()
    json_artifact = JsonDashboardRenderer().render(source)
    payload = json.loads(json_artifact.content)
    assert payload["definition"]["pages"] == source.snapshot["pages"]
    assert payload["definition"]["filters"] == source.snapshot["filters"]
    assert payload["definition"]["dashboard_version_id"] == str(source.dashboard_version_id)
    assert payload["widget_data"] == {
        key: {
            field: value
            for field, value in cast(dict[str, object], result).items()
            if field in {"columns", "rows", "row_count", "truncated", "render_hint", "shaped"}
        }
        for key, result in source.widget_results.items()
    }

    csv_artifact = CsvDashboardRenderer().render(source)
    assert b"Grid Layout,x=2,y=3,w=7,h=5" in csv_artifact.content
    records = list(csv.reader(io.StringIO(csv_artifact.content.decode("utf-8-sig"))))
    manifest = json.loads(next(row[1] for row in records if row[0] == "Canonical Definition"))
    assert manifest == payload["definition"]

    png_artifact = PngDashboardRenderer().render(source)
    with Image.open(io.BytesIO(png_artifact.content)) as image:
        metadata = cast(dict[str, str], getattr(image, "text", {}))
        manifest = json.loads(metadata["vip.dashboard.definition"])
    assert manifest["pages"] == source.snapshot["pages"]


def test_csv_exports_available_widget_data_without_requiring_a_table() -> None:
    artifact = CsvDashboardRenderer().render(document("kpi"))
    assert b"Revenue" in artifact.content
    assert b"42" in artifact.content


def test_csv_preserves_non_tabular_widget_without_result_rows() -> None:
    source = document("text")
    pages = cast(list[dict[str, object]], source.snapshot["pages"])
    widget = cast(
        list[dict[str, object]],
        pages[0]["widgets"],
    )[0]
    widget["content"] = "تقرير Enterprise 2026"
    source.widget_results.clear()
    artifact = CsvDashboardRenderer().render(source)
    records = list(csv.reader(io.StringIO(artifact.content.decode("utf-8-sig"))))
    manifest = json.loads(next(row[1] for row in records if row[0] == "Canonical Definition"))
    assert manifest["pages"][0]["widgets"][0] == widget


def test_csv_merges_multiple_tables_with_ordered_headers() -> None:
    source = document()
    first = cast(list[dict[str, object]], source.snapshot["pages"])[0]["widgets"]
    widgets = cast(list[dict[str, object]], first)
    second_id = uuid4()
    widgets.append(
        {
            "id": str(second_id),
            "type": "table",
            "title": "Orders",
            "hidden": False,
        }
    )
    source.widget_results[str(second_id)] = {
        "columns": [{"key": "orders", "label": "Orders"}],
        "rows": [{"orders": 7}],
    }
    artifact = CsvDashboardRenderer().render(source)
    assert b"Widget 1,Revenue" in artifact.content
    assert b"Widget 2,Orders" in artifact.content


def test_all_twenty_widget_types_render_and_preserve_definition() -> None:
    widget_types = [
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
        "text",
        "rich-text",
        "image",
        "filter",
        "date-filter",
        "map",
    ]
    source = document()
    pages: list[dict[str, object]] = []
    source.widget_results.clear()
    for index, widget_type in enumerate(widget_types):
        widget_id = uuid4()
        widget = {
            "id": str(widget_id),
            "type": widget_type,
            "title": f"{widget_type} / الإيرادات 2026",
            "description": "English ثم العربية 123",
            "content": "ملاحظة Enterprise طويلة 2026",
            "hidden": False,
            "layout": {"x": 0, "y": 0, "w": 12, "h": 4},
            "query": {"metrics": ["revenue"], "dimensions": ["region"]},
            "filters": [{"field": "region", "operator": "equals", "value": "الرياض"}],
            "config": {
                "number_style": "currency",
                "currency": "SAR",
                "decimals": 2,
                "show_legend": True,
                "show_labels": True,
                "show_gridlines": True,
                "legend_position": "bottom",
                "background": "#FFF7ED",
                "border": True,
                "color_scheme": "sunset",
                "conditional": [{"when": "gt", "value": 40, "color": "#DC2626"}],
                "locked": index % 2 == 0,
                "aria_label": f"Accessible {widget_type}",
            },
            "interactions": {
                "crossFilter": True,
                "drillDown": True,
                "drillThrough": "details",
                "tooltip": True,
                "exportable": True,
            },
        }
        pages.append(
            {
                "key": f"page_{index}",
                "name": f"Page {index + 1} / الصفحة",
                "position": index,
                "widgets": [widget],
            }
        )
        source.widget_results[str(widget_id)] = {
            "columns": [
                {"key": "region", "label": "Region / المنطقة", "role": "dimension"},
                {"key": "revenue", "label": "Revenue / الإيرادات", "role": "measure"},
                {"key": "profit", "label": "Profit / الربح", "role": "measure"},
            ],
            "rows": [
                {"region": "Enterprise Riyadh / الرياض", "revenue": 42, "profit": 18},
                {"region": "Jeddah / جدة", "revenue": 64, "profit": 27},
            ],
            "row_count": 2,
            "truncated": False,
        }
    source.snapshot["pages"] = pages
    dashboard = cast(dict[str, object], source.snapshot["dashboard"])
    dashboard["title"] = "Enterprise / المؤسسة"
    expected_types = widget_types

    json_payload = json.loads(JsonDashboardRenderer().render(source).content)
    assert [
        page["widgets"][0]["type"] for page in json_payload["definition"]["pages"]
    ] == expected_types
    csv_records = list(
        csv.reader(io.StringIO(CsvDashboardRenderer().render(source).content.decode("utf-8-sig")))
    )
    csv_manifest = json.loads(
        next(row[1] for row in csv_records if row[0] == "Canonical Definition")
    )
    assert [page["widgets"][0]["type"] for page in csv_manifest["pages"]] == expected_types
    pdf = PdfDashboardRenderer().render(source)
    assert pdf.content.startswith(b"%PDF")
    png = PngDashboardRenderer().render(source)
    with Image.open(io.BytesIO(png.content)) as image:
        metadata = cast(dict[str, str], getattr(image, "text", {}))
        png_manifest = json.loads(metadata["vip.dashboard.definition"])
        colors = image.convert("RGB").getcolors(maxcolors=image.width * image.height)
    assert [page["widgets"][0]["type"] for page in png_manifest["pages"]] == expected_types
    assert colors is not None
    assert any(color == (255, 247, 237) for _, color in colors)
    assert any(color == (220, 38, 38) for _, color in colors)


def test_scheduler_supports_one_time_and_recurring_timezones() -> None:
    run_at = datetime.now(UTC) + timedelta(hours=2)
    one_time = ScheduleCreate(
        name="Once",
        recipients=["owner@example.com"],
        subject="Results",
        format="pdf",
        schedule_type="one_time",
        run_at=run_at,
        timezone="UTC",
    )
    assert next_run(one_time) == run_at
    assert ScheduleCreate.model_validate({**one_time.model_dump(), "format": "csv"}).format == "csv"
    assert (
        ScheduleCreate.model_validate({**one_time.model_dump(), "format": "json"}).format == "json"
    )
    daily = one_time.model_copy(
        update={"schedule_type": "daily", "run_at": None, "timezone": "Asia/Riyadh"}
    )
    assert next_run(daily) > datetime.now(UTC) + timedelta(hours=23)


def test_cache_material_changes_for_every_security_scope() -> None:
    base = {
        "organization": str(uuid4()),
        "workspace": str(uuid4()),
        "dashboard": str(uuid4()),
        "published_version": 3,
        "semantic_version": 2,
        "widget": str(uuid4()),
        "filters": {"country": ["SA"]},
        "user": str(uuid4()),
        "permissions": ["dashboard.query"],
        "features": ["dashboard_studio"],
        "entitlements": ["dashboard_studio"],
        "locale": "en-US",
        "timezone": "Asia/Riyadh",
    }
    original = _digest(base)
    for field in base:
        changed = {**base, field: f"different-{field}"}
        assert _digest(changed) != original


@pytest.mark.asyncio
async def test_download_token_is_bound_and_single_use(settings: Settings) -> None:
    signing_settings = settings.model_copy(
        update={"DASHBOARD_DOWNLOAD_SIGNING_KEY": SecretStr("unit-test-download-signing-key")}
    )
    organization_id, workspace_id, user_id, export_id = uuid4(), uuid4(), uuid4(), uuid4()
    context = AuthorizationContext(
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        organization_role_key="organization_member",
        workspace_role_key="viewer",
        permissions=frozenset({"dashboard.export.download"}),
        entitlements=frozenset({"dashboard_exports"}),
        feature_flags=MappingProxyType({"dashboard_exports": True}),
        quotas=MappingProxyType({}),
        correlation_id="download-test",
    )
    item = DashboardExport(
        id=export_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        dashboard_id=uuid4(),
        dashboard_version_id=uuid4(),
        requested_by_user_id=user_id,
        format="pdf",
    )
    expires = datetime.now(UTC) + timedelta(minutes=2)
    payload = _token_payload(item, context, expires)
    import hashlib
    import hmac

    signature = hmac.new(
        signing_settings.dashboard_download_signing_key.encode(), payload, hashlib.sha256
    ).digest()
    token = f"{_encode(payload)}.{_encode(signature)}"

    class RedisStub:
        def __init__(self) -> None:
            self.keys: set[str] = set()

        async def set(self, key: str, _value: str, *, ex: int, nx: bool) -> bool:
            assert ex > 0 and nx
            if key in self.keys:
                return False
            self.keys.add(key)
            return True

    redis = cast(Redis, RedisStub())
    await consume_download_token(token, item, context, signing_settings, redis)
    with pytest.raises(ApplicationError) as replay:
        await consume_download_token(token, item, context, signing_settings, redis)
    assert replay.value.code == "DASHBOARD_DOWNLOAD_TOKEN_INVALID"
    other_user = replace(context, user_id=uuid4())
    with pytest.raises(ApplicationError) as raised:
        verify_download_token(token, item, other_user, signing_settings)
    assert raised.value.code == "DASHBOARD_DOWNLOAD_TOKEN_INVALID"
