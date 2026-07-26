"""B6.5 renderer, scheduler, signed-download, and cache security tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import cast
from uuid import uuid4

import pytest
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
    assert any(part.get_filename() == "dashboard.pdf" for part in email.iter_attachments())


def document(widget_type: str = "table") -> RenderDocument:
    dashboard_id, organization_id, workspace_id, widget_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    return RenderDocument(
        dashboard_id=dashboard_id,
        dashboard_version=4,
        organization_id=organization_id,
        workspace_id=workspace_id,
        generated_at=datetime.now(UTC),
        dashboard_name="Quarterly Results",
        snapshot={
            "pages": [
                {
                    "widgets": [
                        {
                            "id": str(widget_id),
                            "type": widget_type,
                            "title": "Revenue",
                            "hidden": False,
                        }
                    ]
                }
            ]
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


def test_csv_exports_available_widget_data_without_requiring_a_table() -> None:
    artifact = CsvDashboardRenderer().render(document("kpi"))
    assert b"Revenue" in artifact.content
    assert b"42" in artifact.content


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
    assert b"Table 1,Revenue" in artifact.content
    assert b"Table 2,Orders" in artifact.content


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
