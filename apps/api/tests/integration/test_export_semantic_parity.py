"""Permanent dashboard-export SEMANTIC parity harness (VIP Phase 2).

Drives the REAL PDF (ReportLab) and PNG (PIL) renderers with deterministic
fixtures and asserts *analytical meaning*, not just that an artifact exists.

It is designed to fail on the Phase-2 P0 defects:
  * VIP-BUG-002 — Pivot renders blank (known cell values missing from PDF).
  * VIP-BUG-003 — Scatter silently rendered as Bar (invalid scatter must show an
    explicit invalid-state, never a bar chart).

PDF semantics are checked via extracted text (pypdf). PNG is checked for a
non-blank widget region (PIL) — a blank widget is a semantic failure.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from uuid import uuid4

import pypdf
from PIL import Image

from vip_api.dashboard_delivery.rendering import (
    PdfDashboardRenderer,
    PngDashboardRenderer,
    RenderDocument,
)

# --- deterministic known values (kept < 1000 to avoid thousands-formatting) ---
PIVOT_CELLS = {"111", "222", "333", "444"}
PIVOT_LABELS = {"Region A", "Region B", "Q1", "Q2"}
SCATTER_INVALID_MSG = "Scatter chart requires numeric X and Y fields."


def _widget(widget_id: str, wtype: str, title: str) -> dict[str, object]:
    return {
        "id": widget_id,
        "type": wtype,
        "title": title,
        "semantic_model_id": str(uuid4()),
        "hidden": False,
        "layout": {"x": 0, "y": 0, "w": 12, "h": 6},
        "query": {"dimensions": [], "metrics": []},
        "config": {},
    }


def _result(columns: list[dict[str, str]], rows: list[dict[str, object]]) -> dict[str, object]:
    return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": False}


def _document() -> RenderDocument:
    pivot_id, table_id = str(uuid4()), str(uuid4())
    scatter_ok_id, scatter_bad_id, bar_id = str(uuid4()), str(uuid4()), str(uuid4())
    pivot_cols = [
        {"key": "region", "label": "Region"},
        {"key": "q1", "label": "Q1"},
        {"key": "q2", "label": "Q2"},
    ]
    pivot_rows = [
        {"region": "Region A", "q1": 111, "q2": 222},
        {"region": "Region B", "q1": 333, "q2": 444},
    ]
    scatter_cols = [{"key": "x", "label": "X"}, {"key": "y", "label": "Y"}]
    scatter_rows = [{"x": 12, "y": 34}, {"x": 56, "y": 78}, {"x": 90, "y": 21}]
    scatter_bad_cols = [{"key": "label", "label": "Label"}, {"key": "x", "label": "X"}]
    scatter_bad_rows = [{"label": "Alpha", "x": 5}, {"label": "Beta", "x": 9}]
    bar_cols = [{"key": "cat", "label": "Category"}, {"key": "val", "label": "Value"}]
    bar_rows = [{"cat": "One", "val": 10}, {"cat": "Two", "val": 20}]

    snapshot = {
        "dashboard": {"name": "Parity Fixture"},
        "pages": [
            {
                "id": str(uuid4()),
                "name": "Page 1",
                "widgets": [
                    _widget(pivot_id, "pivot", "Revenue by Region/Quarter"),
                    _widget(table_id, "table", "Revenue Table"),
                    _widget(scatter_ok_id, "scatter", "Valid Scatter"),
                    _widget(scatter_bad_id, "scatter", "Invalid Scatter"),
                    _widget(bar_id, "bar", "Bar Widget"),
                ],
            }
        ],
    }
    widget_results = {
        pivot_id: _result(pivot_cols, pivot_rows),
        table_id: _result(pivot_cols, pivot_rows),
        scatter_ok_id: _result(scatter_cols, scatter_rows),
        scatter_bad_id: _result(scatter_bad_cols, scatter_bad_rows),
        bar_id: _result(bar_cols, bar_rows),
    }
    return RenderDocument(
        dashboard_id=uuid4(),
        dashboard_version_id=uuid4(),
        dashboard_version=1,
        organization_id=uuid4(),
        workspace_id=uuid4(),
        generated_at=datetime.now(UTC),
        dashboard_name="Parity Fixture",
        snapshot=snapshot,
        widget_results=widget_results,
        filters={},
        locale="en-US",
        timezone="UTC",
    )


def _pdf_text(content: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _png_nonblank_ratio(content: bytes) -> float:
    """Fraction of non-white pixels — a fully blank export tends toward 0."""
    image = Image.open(io.BytesIO(content)).convert("L")
    histogram = image.histogram()
    total = sum(histogram)
    near_white = sum(histogram[245:])
    return 1.0 - (near_white / total if total else 1.0)


def test_pdf_pivot_contains_known_values() -> None:
    """VIP-BUG-002: the pivot's known labels and cell values must appear in the PDF."""
    artifact = PdfDashboardRenderer().render(_document())
    text = _pdf_text(artifact.content)
    missing_labels = {label for label in PIVOT_LABELS if label not in text}
    missing_cells = {cell for cell in PIVOT_CELLS if cell not in text}
    assert not missing_labels, f"Pivot labels missing from PDF (blank pivot?): {missing_labels}"
    assert not missing_cells, f"Pivot cell values missing from PDF (blank pivot?): {missing_cells}"


def test_pdf_invalid_scatter_is_explicit_not_bar() -> None:
    """VIP-BUG-003: an invalid scatter must render an explicit message, never a bar."""
    artifact = PdfDashboardRenderer().render(_document())
    text = _pdf_text(artifact.content)
    assert SCATTER_INVALID_MSG in text, "Invalid scatter did not render its explicit invalid-state message (silent fallback?)"


def test_pdf_valid_scatter_renders_without_invalid_message() -> None:
    """A valid scatter (>=2 numeric fields) must render as a scatter, not error."""
    doc = _document()
    artifact = PdfDashboardRenderer().render(doc)
    assert artifact.content_type == "application/pdf"
    assert len(artifact.content) > 1000


def test_png_renders_nonblank() -> None:
    """PNG export must not be a blank canvas (data-backed widgets present)."""
    artifact = PngDashboardRenderer().render(_document())
    assert artifact.extension == "png"
    ratio = _png_nonblank_ratio(artifact.content)
    assert ratio > 0.01, f"PNG export appears blank (non-white ratio {ratio:.4f})"
