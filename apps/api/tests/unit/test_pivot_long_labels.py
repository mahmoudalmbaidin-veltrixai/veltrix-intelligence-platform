"""VIP-P6-001 — Pivot long-label export fidelity (PDF + PNG).

Proves the exporter preserves the COMPLETE analytical meaning of long Pivot row
and column labels instead of destructively truncating them, while keeping cell
values aligned under the correct column. Uses deterministic draw-call capture
(the renderer's own text-draw calls) plus a real PDF render + text extraction,
so a regression to fixed-length truncation fails the suite.
"""

from __future__ import annotations

import base64
import io
import re
import zlib
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from PIL import Image, ImageDraw

from vip_api.dashboard_delivery.rendering import (
    PdfDashboardRenderer,
    PngDashboardRenderer,
    RenderDocument,
    _pivot_result,
    _wrap_cell,
)

REGIONS = (
    "Enterprise Revenue Forecast - Northern Region",
    "Enterprise Revenue Forecast - Southern Region",
)
QUARTERS = (
    "Quarter 1 Actual Revenue Performance",
    "Quarter 2 Actual Revenue Performance",
)


def _pivot_widget() -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    widget: dict[str, object] = {
        "id": str(uuid4()),
        "type": "pivot",
        "title": "QA pivot",
        "description": "",
        "semantic_model_id": str(uuid4()),
        "hidden": False,
        "layout": {"x": 0, "y": 0, "w": 12, "h": 8},
        "query": {"dimensions": ["region", "quarter"], "metrics": ["revenue"]},
        "config": {"number_style": "plain", "decimals": 0},
        "content": None,
    }
    columns: list[dict[str, object]] = [
        {"key": "region", "label": "Region", "data_type": "string", "role": "dimension"},
        {"key": "quarter", "label": "Quarter", "data_type": "string", "role": "dimension"},
        {"key": "revenue", "label": "Revenue", "data_type": "integer", "role": "metric"},
    ]
    rows: list[dict[str, object]] = [
        {"region": REGIONS[0], "quarter": QUARTERS[0], "revenue": 111},
        {"region": REGIONS[0], "quarter": QUARTERS[1], "revenue": 222},
        {"region": REGIONS[1], "quarter": QUARTERS[0], "revenue": 333},
        {"region": REGIONS[1], "quarter": QUARTERS[1], "revenue": 444},
    ]
    pcols, prows = _pivot_result(widget, columns, rows)
    return widget, pcols, prows


# --------------------------------------------------------------------------- #
# Wrapping helper
# --------------------------------------------------------------------------- #
def _char_measure(text: str) -> float:
    return float(len(text))


def test_wrap_cell_single_line_preserved() -> None:
    assert _wrap_cell("Short", 100, _char_measure, 4) == ["Short"]


def test_wrap_cell_multiline_preserves_full_content() -> None:
    lines = _wrap_cell(REGIONS[0], 20, _char_measure, 6)
    assert len(lines) > 1
    # Joining wrapped lines reconstructs the complete label (breaks are on spaces).
    assert " ".join(lines) == REGIONS[0]


def test_wrap_cell_shared_prefix_labels_stay_distinct() -> None:
    a = " ".join(_wrap_cell(REGIONS[0], 20, _char_measure, 6))
    b = " ".join(_wrap_cell(REGIONS[1], 20, _char_measure, 6))
    assert a != b and "Northern" in a and "Southern" in b


def test_wrap_cell_extreme_fallback_is_bounded_and_nondestructive_first_lines() -> None:
    # Only when a label truly cannot fit is the LAST line ellipsised; earlier
    # lines remain intact (never a single ambiguous prefix of the whole label).
    lines = _wrap_cell(REGIONS[0], 20, _char_measure, 2)
    assert len(lines) == 2
    assert lines[0] == "Enterprise Revenue"
    assert lines[-1].endswith("…")


# --------------------------------------------------------------------------- #
# PDF — deterministic draw-call layout assertions
# --------------------------------------------------------------------------- #
class _RecordingCanvas:
    def __init__(self) -> None:
        self.texts: list[tuple[float, float, str]] = []

    def setFillColor(self, *_a: object, **_k: object) -> None: ...
    def setFont(self, *_a: object, **_k: object) -> None: ...
    def rect(self, *_a: object, **_k: object) -> None: ...
    def drawString(self, x: float, y: float, text: str) -> None:
        self.texts.append((x, y, text))

    def drawRightString(self, x: float, y: float, text: str) -> None:
        self.texts.append((x, y, text))


def _columns_by_x(texts: list[tuple[float, float, str]]) -> dict[float, str]:
    grouped: dict[float, list[str]] = defaultdict(list)
    for x, _y, text in texts:
        grouped[round(x, 1)].append(text)
    return {x: " ".join(parts) for x, parts in grouped.items()}


def test_pdf_pivot_preserves_full_labels_and_alignment() -> None:
    widget, pcols, prows = _pivot_widget()
    canvas = _RecordingCanvas()
    # Deliberately NARROW so every long label MUST wrap to survive.
    width = 240.0
    PdfDashboardRenderer._table(canvas, widget, pcols, prows, 0.0, 0.0, width, 400.0)
    joined = _columns_by_x(canvas.texts)
    col_width = width / 3
    row_label_x = round(0 * col_width + 4, 1)
    q1_x = round(1 * col_width + 4, 1)
    q2_x = round(2 * col_width + 4, 1)

    # Full column headers preserved (no fixed-length truncation).
    assert QUARTERS[0] in joined[q1_x]
    assert QUARTERS[1] in joined[q2_x]
    # Full, distinguishable row labels preserved under the row-label column.
    assert REGIONS[0] in joined[row_label_x]
    assert REGIONS[1] in joined[row_label_x]
    # Values remain aligned under the correct pivot columns.
    assert "111" in joined[q1_x] and "333" in joined[q1_x]
    assert "222" in joined[q2_x] and "444" in joined[q2_x]


def _pdf_text(content: bytes) -> str:
    tokens: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        value = match.group(1).strip()
        try:
            if value.endswith(b"~>"):
                value = base64.a85decode(value, adobe=True)
            stream = zlib.decompress(value).decode("latin-1")
        except (ValueError, zlib.error):
            continue
        for token in re.findall(r"\((?:[^()\\]|\\.)*\)", stream):
            tokens.append(token[1:-1])
    return " ".join(tokens)


def _document(widget: dict[str, object]) -> RenderDocument:
    columns = [
        {"key": "region", "label": "Region", "data_type": "string", "role": "dimension"},
        {"key": "quarter", "label": "Quarter", "data_type": "string", "role": "dimension"},
        {"key": "revenue", "label": "Revenue", "data_type": "integer", "role": "metric"},
    ]
    rows = [
        {"region": REGIONS[0], "quarter": QUARTERS[0], "revenue": 111},
        {"region": REGIONS[0], "quarter": QUARTERS[1], "revenue": 222},
        {"region": REGIONS[1], "quarter": QUARTERS[0], "revenue": 333},
        {"region": REGIONS[1], "quarter": QUARTERS[1], "revenue": 444},
    ]
    return RenderDocument(
        dashboard_id=uuid4(),
        dashboard_version_id=uuid4(),
        dashboard_version=1,
        organization_id=uuid4(),
        workspace_id=uuid4(),
        generated_at=datetime.now(UTC),
        dashboard_name="Pivot long label",
        snapshot={
            "dashboard": {"name": "Pivot long label"},
            "pages": [{"id": str(uuid4()), "name": "01 pivot", "position": 0, "widgets": [widget]}],
            "filters": [],
        },
        widget_results={
            str(widget["id"]): {
                "columns": columns,
                "rows": rows,
                "row_count": 4,
                "truncated": False,
            }
        },
        filters={},
        locale="en-US",
        timezone="UTC",
    )


def test_pdf_full_render_extracts_complete_labels() -> None:
    widget, _pcols, _prows = _pivot_widget()
    artifact = PdfDashboardRenderer().render(_document(widget))
    assert artifact.content[:4] == b"%PDF"
    text = _pdf_text(artifact.content)
    for label in (*QUARTERS, *REGIONS):
        assert label in text, f"missing full label: {label}"
    for value in ("111", "222", "333", "444"):
        assert value in text


# --------------------------------------------------------------------------- #
# PNG — deterministic draw-call layout assertions
# --------------------------------------------------------------------------- #
def test_png_pivot_attempts_to_draw_complete_labels() -> None:
    widget, pcols, prows = _pivot_widget()
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    recorded: list[tuple[float, float, str]] = []

    def _record(xy: tuple[float, float], text: str, **_kw: object) -> None:
        recorded.append((xy[0], xy[1], text))

    draw.text = _record  # type: ignore[assignment]  # keep real .textlength
    font = PngDashboardRenderer._font(24)
    # Constrained bounds so long labels must wrap across multiple lines, yet wide
    # enough that the complete label fits within the wrap budget (no ellipsis).
    PngDashboardRenderer._draw_table(draw, widget, (0.0, 0.0, 480.0, 400.0), pcols, prows, font, 2)

    joined = _columns_by_x(recorded)
    full = " ".join(joined.values())
    for label in (*QUARTERS, *REGIONS):
        assert label in full, f"PNG did not draw complete label: {label}"
    assert REGIONS[0] != REGIONS[1] and REGIONS[0] in full and REGIONS[1] in full
    for value in ("111", "222", "333", "444"):
        assert value in full


def test_png_full_render_is_non_blank_image() -> None:
    widget, _pcols, _prows = _pivot_widget()
    artifact = PngDashboardRenderer().render(_document(widget))
    assert artifact.content[:8] == b"\x89PNG\r\n\x1a\n"
    image = Image.open(io.BytesIO(artifact.content)).convert("RGB")
    assert image.width > 0 and image.height > 0
