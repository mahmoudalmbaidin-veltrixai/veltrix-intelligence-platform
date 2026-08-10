"""Dashboard-export semantic parity harness for every supported widget type.

The suite combines immutable-definition checks, renderer-dispatch observation,
known-value assertions, and widget-body pixel inspection. It deliberately does
not treat successful file generation or a non-blank full dashboard as semantic
proof.
"""

from __future__ import annotations

import base64
import io
import os
import re
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args
from uuid import uuid4

import pytest
from PIL import Image

from vip_api.dashboard_delivery.rendering import (
    PdfDashboardRenderer,
    PngDashboardRenderer,
    RenderDocument,
)
from vip_api.dashboards.schemas import WidgetType
from vip_api.dashboards.visual_contracts import SCATTER_CONFIGURATION_ERROR

ALL_WIDGET_TYPES = (
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
)
DATA_WIDGET_TYPES = frozenset(ALL_WIDGET_TYPES[:14]) | {"map"}
CHART_DISPATCH_TYPES = ("bar", "stacked-bar", "column", "line", "area", "scatter")
PNG_CHART_DISPATCH_TYPES = (
    "bar",
    "stacked-bar",
    "column",
    "line",
    "area",
    "pie",
    "donut",
    "scatter",
)
PIVOT_CELLS = ("111", "222", "333", "444")
PIVOT_LABELS = ("Region A", "Region B", "Q1", "Q2")


def _evidence(name: str, content: bytes) -> None:
    directory = os.getenv("VIP_SEMANTIC_PARITY_EVIDENCE_DIR")
    if not directory:
        return
    target = Path(directory) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def _pdf_content_streams(content: bytes) -> bytes:
    """Decode ReportLab page streams with only Python's standard library."""

    decoded: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        value = match.group(1).strip()
        try:
            if value.endswith(b"~>"):
                value = base64.a85decode(value, adobe=True)
            decoded.append(zlib.decompress(value))
        except (ValueError, zlib.error):
            continue
    return b"\n".join(decoded)


def _widget(
    widget_type: str, *, invalid_scatter: bool = False
) -> tuple[dict[str, object], dict[str, object]]:
    widget_id = str(uuid4())
    metrics = ["revenue"] if widget_type in DATA_WIDGET_TYPES else []
    dimensions = ["category"] if widget_type in DATA_WIDGET_TYPES else []
    columns: list[dict[str, object]] = [
        {"key": "category", "label": "Category", "data_type": "string", "role": "dimension"},
        {"key": "revenue", "label": "Revenue", "data_type": "integer", "role": "metric"},
        {"key": "profit", "label": "Profit", "data_type": "decimal", "role": "metric"},
    ]
    rows: list[dict[str, object]] = [
        {"category": "Alpha", "revenue": 100, "profit": -10},
        {"category": "Beta", "revenue": 23, "profit": 7},
    ]
    content = None

    if widget_type == "pivot":
        dimensions = ["region", "quarter"]
        columns = [
            {"key": "region", "label": "Region", "data_type": "string", "role": "dimension"},
            {"key": "quarter", "label": "Quarter", "data_type": "string", "role": "dimension"},
            {"key": "revenue", "label": "Revenue", "data_type": "integer", "role": "metric"},
        ]
        rows = [
            {"region": "Region A", "quarter": "Q1", "revenue": 111},
            {"region": "Region A", "quarter": "Q2", "revenue": 222},
            {"region": "Region B", "quarter": "Q1", "revenue": 333},
            {"region": "Region B", "quarter": "Q2", "revenue": 444},
        ]
    elif widget_type == "scatter":
        metrics = ["revenue"] if invalid_scatter else ["revenue", "profit"]
        rows = [
            {"category": "Alpha", "revenue": -20, "profit": 5},
            {"category": "Beta", "revenue": 0, "profit": None},
            {"category": "Gamma", "revenue": 40, "profit": 30},
        ]
    elif widget_type == "map":
        dimensions = ["category", "latitude", "longitude"]
        columns = [
            {"key": "category", "label": "City", "data_type": "string", "role": "dimension"},
            {"key": "latitude", "label": "Latitude", "data_type": "decimal", "role": "dimension"},
            {"key": "longitude", "label": "Longitude", "data_type": "decimal", "role": "dimension"},
            {"key": "revenue", "label": "Revenue", "data_type": "integer", "role": "metric"},
        ]
        rows = [
            {"category": "Riyadh", "latitude": 24.7136, "longitude": 46.6753, "revenue": 100},
            {"category": "Jeddah", "latitude": 21.4858, "longitude": 39.1925, "revenue": 23},
        ]
    elif widget_type not in DATA_WIDGET_TYPES:
        content = {
            "text": "Visible plain text",
            "rich-text": "Visible rich semantic text",
            "image": "Expected asset: qa-logo",
            "filter": "Selected region: Region A",
            "date-filter": "Selected dates: 2026-01-01 to 2026-03-31",
        }[widget_type]
        columns, rows = [], []

    widget: dict[str, object] = {
        "id": widget_id,
        "type": widget_type,
        "title": f"QA {widget_type}",
        "description": content or "",
        "semantic_model_id": str(uuid4()) if widget_type in DATA_WIDGET_TYPES else None,
        "hidden": False,
        "layout": {"x": 0, "y": 0, "w": 12, "h": 8},
        "query": {"dimensions": dimensions, "metrics": metrics},
        "config": {
            "number_style": "plain",
            "decimals": 0,
            "show_legend": True,
            "show_gridlines": True,
        },
        "content": content,
    }
    result = {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": False}
    return widget, result


def _document(
    widget_types: tuple[str, ...] = ALL_WIDGET_TYPES, *, invalid_scatter: bool = False
) -> RenderDocument:
    pages: list[dict[str, object]] = []
    results: dict[str, dict[str, object]] = {}
    for index, widget_type in enumerate(widget_types):
        widget, result = _widget(
            widget_type, invalid_scatter=invalid_scatter and widget_type == "scatter"
        )
        pages.append(
            {
                "id": str(uuid4()),
                "name": f"{index + 1:02d} {widget_type}",
                "position": index,
                "widgets": [widget],
            }
        )
        results[str(widget["id"])] = result
    return RenderDocument(
        dashboard_id=uuid4(),
        dashboard_version_id=uuid4(),
        dashboard_version=7,
        organization_id=uuid4(),
        workspace_id=uuid4(),
        generated_at=datetime.now(UTC),
        dashboard_name="Phase 2 semantic parity",
        snapshot={"dashboard": {"name": "Phase 2 semantic parity"}, "pages": pages, "filters": []},
        widget_results=results,
        filters={"region": "Region A", "date": ["2026-01-01", "2026-03-31"]},
        locale="en-US",
        timezone="UTC",
    )


def _body_crop(content: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(content)).convert("RGB")
    # Single-page fixture: exclude dashboard/page/card chrome so another region
    # cannot make a semantically empty widget pass.
    return image.crop((120, 492, image.width - 120, min(image.height - 80, 1660)))


def _non_white_ratio(image: Image.Image) -> float:
    pixels = list(image.get_flattened_data())
    non_white = sum(1 for red, green, blue in pixels if min(red, green, blue) < 242)
    return non_white / max(1, len(pixels))


def _color_count(image: Image.Image, color: tuple[int, int, int]) -> int:
    return list(image.get_flattened_data()).count(color)


def test_inventory_matches_the_authoritative_backend_contract() -> None:
    assert tuple(get_args(WidgetType)) == ALL_WIDGET_TYPES


def test_pdf_preserves_all_widget_definitions_and_known_text_semantics() -> None:
    artifact = PdfDashboardRenderer().render(_document())
    _evidence("all-widget-direct-renderer.pdf", artifact.content)
    assert artifact.content.startswith(b"%PDF-")
    visible_content = _pdf_content_streams(artifact.content)
    for widget_type in ALL_WIDGET_TYPES:
        assert f"QA {widget_type}".encode() in visible_content
    for value in (*PIVOT_LABELS, *PIVOT_CELLS, "Visible plain text", "qa-logo"):
        assert value.encode() in visible_content
    # Live KPI sums 100 + 23; PDF must use the same aggregate, not row zero.
    assert b"123" in visible_content


@pytest.mark.parametrize("widget_type", ALL_WIDGET_TYPES)
def test_png_widget_body_is_independently_nonblank(widget_type: str) -> None:
    artifact = PngDashboardRenderer().render(_document((widget_type,)))
    if widget_type in {"pivot", "scatter"}:
        _evidence(f"{widget_type}/valid.png", artifact.content)
    body = _body_crop(artifact.content)
    assert _non_white_ratio(body) > 0.00005, f"{widget_type} body is visually blank"
    if widget_type == "pivot":
        brand_dark = _color_count(body, (22, 58, 112))
        assert brand_dark > 500, "Pivot matrix header is absent from its own PNG region"
    if widget_type == "scatter":
        brand = _color_count(body, (37, 99, 235))
        assert 20 < brand < 2500, "Scatter points are absent or have bar-sized fill area"


def test_pdf_and_png_dispatch_each_chart_as_its_persisted_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_seen: list[str] = []
    png_seen: list[str] = []
    pdf_original = PdfDashboardRenderer._chart
    png_original = PngDashboardRenderer._draw_chart

    def pdf_capture(*args: object, **kwargs: object) -> None:
        pdf_seen.append(str(args[2]))
        pdf_original(*args, **kwargs)  # type: ignore[arg-type]

    def png_capture(*args: object, **kwargs: object) -> None:
        png_seen.append(str(args[2]))
        png_original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(PdfDashboardRenderer, "_chart", staticmethod(pdf_capture))
    monkeypatch.setattr(PngDashboardRenderer, "_draw_chart", staticmethod(png_capture))
    PdfDashboardRenderer().render(_document())
    PngDashboardRenderer().render(_document())
    assert tuple(pdf_seen) == CHART_DISPATCH_TYPES
    assert tuple(png_seen) == PNG_CHART_DISPATCH_TYPES


def test_invalid_scatter_is_explicit_and_never_bar_sized() -> None:
    document = _document(("scatter",), invalid_scatter=True)
    pdf = PdfDashboardRenderer().render(document)
    invalid_png = PngDashboardRenderer().render(document)
    _evidence("scatter/invalid.pdf", pdf.content)
    _evidence("scatter/invalid.png", invalid_png.content)
    assert SCATTER_CONFIGURATION_ERROR.encode() in _pdf_content_streams(pdf.content)
    body = _body_crop(invalid_png.content)
    brand = _color_count(body, (37, 99, 235))
    assert brand == 0, "Invalid Scatter rendered data marks (possible Bar fallback)"
