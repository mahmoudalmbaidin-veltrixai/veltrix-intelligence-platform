"""Deterministic, presentation-grade rendering of immutable dashboard versions."""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import arabic_reshaper  # type: ignore[import-untyped]
from bidi.algorithm import get_display  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from reportlab.lib.colors import HexColor  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4, landscape, portrait  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.pdfmetrics import stringWidth  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]

from vip_api.core.errors import ApplicationError

INK = "#172033"
MUTED = "#64748B"
BRAND = "#2563EB"
BRAND_DARK = "#163A70"
ACCENT = "#14B8A6"
SURFACE = "#F5F7FB"
BORDER = "#DCE3EE"
WHITE = "#FFFFFF"
PALETTE = (BRAND, ACCENT, "#7C3AED", "#F59E0B", "#EF4444", "#0891B2")
COLOR_SCHEMES: dict[str, tuple[str, ...]] = {
    "default": PALETTE,
    "ocean": ("#0369A1", "#0EA5E9", "#06B6D4", "#14B8A6", "#22C55E"),
    "sunset": ("#7C2D12", "#EA580C", "#F59E0B", "#FACC15", "#EF4444"),
    "monochrome": ("#172033", "#334155", "#64748B", "#94A3B8", "#CBD5E1"),
}
ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF))


def _font_path(*, bold: bool = False) -> Path | None:
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = (
        Path("/usr/share/fonts/TTF") / filename,
        Path("/usr/share/fonts/truetype/dejavu") / filename,
        Path("/usr/local/share/fonts") / filename,
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
        Path(filename),
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _display_text(value: object) -> str:
    """Shape bidirectional Arabic for renderers without a native layout engine."""
    text = str(value)
    has_arabic = any(
        start <= ord(character) <= end for character in text for start, end in ARABIC_RANGES
    )
    if not has_arabic:
        return text
    return str(get_display(arabic_reshaper.reshape(text)))


def _wrap_text(value: object, max_width: float, measure: Any) -> list[str]:
    """Wrap logical text before bidi shaping, preserving complete words."""
    logical_lines = str(value).replace("\r", "").split("\n")
    lines: list[str] = []
    for logical_line in logical_lines:
        words = logical_line.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if not current or measure(_display_text(candidate)) <= max_width:
                current = candidate
                continue
            lines.append(_display_text(current))
            current = word
        lines.append(_display_text(current))
    return lines or [""]


def _register_pdf_fonts() -> tuple[str, str]:
    regular = _font_path()
    bold = _font_path(bold=True)
    if regular is None or bold is None:
        return "Helvetica", "Helvetica-Bold"
    if "VIPSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("VIPSans", str(regular)))
        pdfmetrics.registerFont(TTFont("VIPSans-Bold", str(bold)))
    return "VIPSans", "VIPSans-Bold"


PDF_FONT, PDF_FONT_BOLD = _register_pdf_fonts()


@dataclass(frozen=True, slots=True)
class RenderDocument:
    dashboard_id: UUID
    dashboard_version_id: UUID
    dashboard_version: int
    organization_id: UUID
    workspace_id: UUID
    generated_at: datetime
    dashboard_name: str
    snapshot: dict[str, object]
    widget_results: dict[str, object]
    filters: dict[str, object]
    locale: str
    timezone: str


@dataclass(frozen=True, slots=True)
class RenderedArtifact:
    content: bytes
    content_type: str
    extension: str


class DashboardRenderer(Protocol):
    format: str

    def render(self, document: RenderDocument) -> RenderedArtifact: ...


def _metadata(document: RenderDocument) -> dict[str, object]:
    return {
        "dashboard_id": str(document.dashboard_id),
        "dashboard_version_id": str(document.dashboard_version_id),
        "dashboard_version": document.dashboard_version,
        "tenant_id": str(document.organization_id),
        "generated_at": document.generated_at.isoformat(),
        "filters": document.filters,
        "locale": document.locale,
        "timezone": document.timezone,
    }


def _pages(document: RenderDocument) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], document.snapshot.get("pages", []))


def _visible_widgets(document: RenderDocument) -> list[dict[str, object]]:
    return [
        widget
        for page in _pages(document)
        for widget in cast(list[dict[str, object]], page.get("widgets", []))
        if not widget.get("hidden", False)
    ]


def _layout(widget: dict[str, object]) -> dict[str, int]:
    value = cast(dict[str, object], widget.get("layout", {}))
    return {
        "x": int(cast(Any, value.get("x", 0))),
        "y": int(cast(Any, value.get("y", 0))),
        "w": int(cast(Any, value.get("w", 12))),
        "h": int(cast(Any, value.get("h", 4))),
    }


def _config(widget: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], widget.get("config", {}))


def _palette(widget: dict[str, object]) -> tuple[str, ...]:
    return COLOR_SCHEMES.get(str(_config(widget).get("color_scheme", "default")), PALETTE)


def _formatted_value(value: object, widget: dict[str, object]) -> str:
    number = _numeric(value)
    if number is None:
        return _text(value)
    config = _config(widget)
    decimals = max(0, min(8, int(cast(Any, config.get("decimals", 0)))))
    style = str(config.get("number_style", "plain"))
    if style == "percent":
        return f"{number * 100:,.{decimals}f}%"
    if style == "currency":
        currency = str(config.get("currency") or "USD")
        return f"{currency} {number:,.{decimals}f}"
    if style == "compact":
        for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
            if abs(number) >= divisor:
                return f"{number / divisor:,.{decimals}f}{suffix}"
    return f"{number:,.{decimals}f}"


def _conditional_color(value: object, widget: dict[str, object], fallback: str) -> str:
    number = _numeric(value)
    if number is None:
        return fallback
    rules = cast(list[dict[str, object]], _config(widget).get("conditional", []))
    for rule in rules:
        threshold = _numeric(rule.get("value"))
        upper = _numeric(rule.get("value2"))
        when = str(rule.get("when", ""))
        matched = (
            (when == "gt" and threshold is not None and number > threshold)
            or (when == "lt" and threshold is not None and number < threshold)
            or (when == "eq" and threshold is not None and number == threshold)
            or (
                when == "between"
                and threshold is not None
                and upper is not None
                and threshold <= number <= upper
            )
        )
        if matched:
            color = str(rule.get("color", ""))
            if color.startswith("#") and len(color) in {4, 7}:
                return color
    return fallback


def _parity_manifest(document: RenderDocument) -> dict[str, object]:
    """Lossless immutable definition shared by viewer, exports, and delivery.

    The snapshot is copied instead of rebuilt from a selected field list. This is
    deliberate: newly introduced definition metadata must survive every export
    without waiting for each renderer to learn about the new field.
    """
    manifest = dict(document.snapshot)
    manifest.setdefault("schema_version", 1)
    manifest.setdefault("dashboard", {"name": document.dashboard_name})
    manifest.setdefault("pages", [])
    manifest.setdefault("filters", [])
    manifest["dashboard_id"] = str(document.dashboard_id)
    manifest["dashboard_version_id"] = str(document.dashboard_version_id)
    manifest["dashboard_version"] = document.dashboard_version
    manifest["applied_filters"] = document.filters
    return manifest


def _safe_results(document: RenderDocument) -> dict[str, object]:
    allowed = {"columns", "rows", "row_count", "truncated", "render_hint", "shaped"}
    return {
        widget_id: {
            key: value for key, value in cast(dict[str, object], result).items() if key in allowed
        }
        for widget_id, result in document.widget_results.items()
    }


def _result(
    document: RenderDocument, widget: dict[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    value = cast(dict[str, object], document.widget_results.get(str(widget.get("id", "")), {}))
    rows = cast(list[dict[str, object]], value.get("rows", []))
    columns = cast(list[dict[str, object]], value.get("columns", []))
    if not columns and rows:
        columns = [{"key": key, "label": key.replace("_", " ").title()} for key in rows[0]]
    return columns, rows


def _column_key(column: dict[str, object]) -> str:
    return str(column.get("key") or column.get("name") or column.get("field") or "")


def _column_label(column: dict[str, object]) -> str:
    key = _column_key(column)
    return str(column.get("label") or key.replace("_", " ").title())


def _text(value: object, limit: int = 120) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (float, Decimal)):
        number = float(value)
        if abs(number) >= 1_000_000:
            return f"{number / 1_000_000:.1f}M"
        if abs(number) >= 1_000:
            return f"{number / 1_000:.1f}K"
        return f"{number:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    result = str(value).replace("\r", " ").replace("\n", " ")
    return result[:limit]


def _numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)) and math.isfinite(float(value)):
        return float(value)
    return None


def _filter_summary(filters: dict[str, object]) -> str:
    if not filters:
        return "All data"
    return "  •  ".join(
        f"{str(key).replace('_', ' ').title()}: {_text(value, 48)}"
        for key, value in sorted(filters.items())
    )


class JsonDashboardRenderer:
    format = "json"

    def render(self, document: RenderDocument) -> RenderedArtifact:
        safe_results = _safe_results(document)
        payload = {
            "metadata": _metadata(document),
            "definition": _parity_manifest(document),
            "widget_data": safe_results,
        }
        return RenderedArtifact(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
            "application/json",
            "json",
        )


class CsvDashboardRenderer:
    """Lossless UTF-8 CSV package with canonical JSON and per-widget data.

    CSV cannot visually represent dashboard layout or non-tabular widgets. The
    canonical JSON record therefore provides a deterministic, round-trippable
    representation while subsequent sections remain convenient in spreadsheets.
    """

    format = "csv"

    def render(self, document: RenderDocument) -> RenderedArtifact:
        binary = io.BytesIO()
        binary.write(b"\xef\xbb\xbf")
        output = io.TextIOWrapper(binary, encoding="utf-8", newline="", write_through=True)
        writer = csv.writer(output, lineterminator="\r\n")
        manifest = _parity_manifest(document)
        writer.writerow(["VIP Dashboard Export", "2"])
        writer.writerow(
            [
                "Canonical Definition",
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ]
        )
        writer.writerow(["Dashboard", document.dashboard_name])
        writer.writerow(["Dashboard ID", str(document.dashboard_id)])
        writer.writerow(["Dashboard Version ID", str(document.dashboard_version_id)])
        writer.writerow(["Version", document.dashboard_version])
        writer.writerow(
            [
                "Generated",
                document.generated_at.isoformat(),
                "Timezone",
                document.timezone,
                "Locale",
                document.locale,
            ]
        )
        writer.writerow(["Filters", _filter_summary(document.filters)])
        writer.writerow([])

        widgets = [
            (page, widget)
            for page in _pages(document)
            for widget in cast(list[dict[str, object]], page.get("widgets", []))
        ]
        for index, (page, widget) in enumerate(widgets):
            columns, rows = _result(document, widget)
            layout = _layout(widget)
            keys = [_column_key(column) for column in columns if _column_key(column)]
            if not keys:
                keys = list(rows[0]) if rows else []
            labels = {
                _column_key(column): _column_label(column)
                for column in columns
                if _column_key(column)
            }
            writer.writerow([f"Widget {index + 1}", _text(widget.get("title", "Widget"), 200)])
            writer.writerow(
                [
                    "Page Definition",
                    json.dumps(
                        {key: value for key, value in page.items() if key != "widgets"},
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ]
            )
            writer.writerow(
                [
                    "Widget Definition",
                    json.dumps(
                        widget,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ]
            )
            writer.writerow(
                [
                    "Widget Result",
                    json.dumps(
                        _safe_results(document).get(str(widget.get("id", "")), {}),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ]
            )
            writer.writerow(
                ["Widget ID", str(widget.get("id", "")), "Type", str(widget.get("type", ""))]
            )
            writer.writerow(
                [
                    "Grid Layout",
                    f"x={layout['x']}",
                    f"y={layout['y']}",
                    f"w={layout['w']}",
                    f"h={layout['h']}",
                ]
            )
            if keys:
                writer.writerow(["Data"])
                writer.writerow([labels.get(key, key.replace("_", " ").title()) for key in keys])
                for row in rows:
                    writer.writerow([row.get(key) for key in keys])
            if index + 1 < len(widgets):
                writer.writerow([])
                writer.writerow([])
        output.flush()
        output.detach()
        return RenderedArtifact(binary.getvalue(), "text/csv; charset=utf-8", "csv")


class PdfDashboardRenderer:
    format = "pdf"

    def render(self, document: RenderDocument) -> RenderedArtifact:
        output = io.BytesIO()
        snapshot_dashboard = cast(dict[str, object], document.snapshot.get("dashboard", {}))
        requested = str(
            snapshot_dashboard.get("orientation")
            or snapshot_dashboard.get("export_orientation")
            or "landscape"
        ).lower()
        pagesize = portrait(A4) if requested == "portrait" else landscape(A4)
        width, height = pagesize
        canvas = Canvas(output, pagesize=pagesize, pageCompression=1)
        canvas.setTitle(document.dashboard_name)
        canvas.setAuthor("Veltrix Intelligence Platform")
        canvas.setSubject("Executive dashboard export")
        canvas.setKeywords(
            json.dumps(_parity_manifest(document), ensure_ascii=False, separators=(",", ":"))
        )
        page_number = 0

        def start_page(title: str) -> float:
            nonlocal page_number
            page_number += 1
            canvas.setFillColor(HexColor(BRAND_DARK))
            canvas.rect(0, height - 70, width, 70, stroke=0, fill=1)
            canvas.setFillColor(HexColor(WHITE))
            canvas.setFont(PDF_FONT_BOLD, 18)
            canvas.drawString(34, height - 32, _display_text(document.dashboard_name[:85]))
            canvas.setFont(PDF_FONT, 8)
            canvas.drawString(34, height - 49, _display_text(title[:95]))
            canvas.drawRightString(
                width - 34,
                height - 49,
                _display_text(
                    f"Generated {document.generated_at:%d %b %Y %H:%M} · {document.timezone}"
                ),
            )
            canvas.setFillColor(HexColor(MUTED))
            canvas.setFont(PDF_FONT, 7.5)
            canvas.drawString(
                34, height - 84, _display_text(_filter_summary(document.filters)[:160])
            )
            return float(height - 102)

        def finish_page() -> None:
            canvas.setStrokeColor(HexColor(BORDER))
            canvas.line(34, 28, width - 34, 28)
            canvas.setFillColor(HexColor(MUTED))
            canvas.setFont(PDF_FONT, 7.5)
            canvas.drawString(34, 16, "Veltrix Intelligence Platform · Confidential")
            canvas.drawRightString(
                width - 34,
                16,
                f"Version {document.dashboard_version} · Page {page_number}",
            )

        dashboard_pages = _pages(document) or [{"name": "Dashboard", "widgets": []}]
        for dashboard_page in dashboard_pages:
            widgets = [
                item
                for item in cast(list[dict[str, object]], dashboard_page.get("widgets", []))
                if not item.get("hidden", False)
            ]
            page_title = str(dashboard_page.get("name") or "Dashboard")
            start_page(page_title)
            left, right, bottom, top = 34.0, width - 34.0, 42.0, height - 102.0
            max_row = max(
                (_layout(widget)["y"] + _layout(widget)["h"] for widget in widgets),
                default=8,
            )
            max_row = max(8, max_row)
            gap_x = 5.0
            gap_y = min(5.0, (top - bottom) / max_row * 0.08)
            cell_w = (right - left - gap_x * 11) / 12
            cell_h = (top - bottom - gap_y * (max_row - 1)) / max_row
            for widget in widgets:
                columns, rows = _result(document, widget)
                layout = _layout(widget)
                card_x = left + layout["x"] * (cell_w + gap_x)
                card_y = (
                    top
                    - (layout["y"] + layout["h"]) * cell_h
                    - (layout["y"] + layout["h"] - 1) * gap_y
                )
                card_width = layout["w"] * cell_w + (layout["w"] - 1) * gap_x
                card_height = layout["h"] * cell_h + (layout["h"] - 1) * gap_y
                self._card(
                    canvas,
                    widget,
                    columns,
                    rows,
                    card_x,
                    card_y,
                    card_width,
                    card_height,
                )
            if not widgets:
                canvas.setFillColor(HexColor(MUTED))
                canvas.setFont(PDF_FONT, 11)
                canvas.drawCentredString(width / 2, height / 2, "No visible widgets")
            finish_page()
            canvas.showPage()
        canvas.save()
        return RenderedArtifact(output.getvalue(), "application/pdf", "pdf")

    def _card(
        self,
        canvas: Canvas,
        widget: dict[str, object],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        config = _config(widget)
        background = str(config.get("background") or WHITE)
        canvas.setFillColor(HexColor(background))
        canvas.setStrokeColor(HexColor(BORDER))
        canvas.roundRect(
            x,
            y,
            width,
            height,
            7,
            stroke=1 if bool(config.get("border", True)) else 0,
            fill=1,
        )
        canvas.setFillColor(HexColor(INK))
        canvas.setFont(PDF_FONT_BOLD, 11)
        canvas.drawString(
            x + 15,
            y + height - 21,
            _display_text(_text(widget.get("title", "Widget"), 80)),
        )
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont(PDF_FONT, 6.5)
        canvas.drawRightString(x + width - 12, y + height - 20, str(widget.get("type", "widget")))
        inner_y = y + 14
        inner_h = max(1.0, height - 48)
        widget_type = str(widget.get("type") or "table")
        if widget_type == "kpi":
            self._kpi(canvas, widget, columns, rows, x + 15, inner_y, width - 30, inner_h)
        elif widget_type == "metric-comparison":
            self._metric_comparison(
                canvas, widget, columns, rows, x + 15, inner_y, width - 30, inner_h
            )
        elif widget_type == "gauge":
            self._gauge(canvas, widget, columns, rows, x + 15, inner_y, width - 30, inner_h)
        elif widget_type == "progress":
            self._progress(canvas, widget, columns, rows, x + 15, inner_y, width - 30, inner_h)
        elif widget_type in {"table", "pivot"}:
            self._table(canvas, widget, columns, rows, x + 15, inner_y, width - 30, inner_h)
        elif widget_type in {"text", "rich-text", "image", "filter", "date-filter"}:
            self._content(canvas, widget, x + 15, inner_y, width - 30, inner_h)
        elif widget_type in {"pie", "donut"}:
            self._pie(
                canvas, widget, widget_type, columns, rows, x + 15, inner_y, width - 30, inner_h
            )
        elif widget_type == "map":
            self._map(canvas, columns, rows, x + 15, inner_y, width - 30, inner_h)
        else:
            self._chart(
                canvas, widget, widget_type, columns, rows, x + 15, inner_y, width - 30, inner_h
            )

    @staticmethod
    def _content(
        canvas: Canvas,
        widget: dict[str, object],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        content = _text(widget.get("content") or widget.get("description") or "", 500)
        canvas.setFillColor(HexColor(INK))
        canvas.setFont(PDF_FONT, 8)
        lines = _wrap_text(
            content,
            width,
            lambda line: stringWidth(line, PDF_FONT, 8),
        )
        for index, line in enumerate(lines[: max(1, int(height / 11))]):
            canvas.drawString(x, y + height - 10 - index * 11, line)

    @staticmethod
    def _pie(
        canvas: Canvas,
        widget: dict[str, object],
        widget_type: str,
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        numeric_key = next(
            (
                _column_key(column)
                for column in columns
                if any(_numeric(row.get(_column_key(column))) is not None for row in rows)
            ),
            "",
        )
        values = [max(0.0, _numeric(row.get(numeric_key)) or 0.0) for row in rows[:12]]
        total = sum(values)
        if not numeric_key or total <= 0:
            canvas.setFillColor(HexColor(MUTED))
            canvas.drawString(x, y + height / 2, "No chart data")
            return
        show_legend = bool(_config(widget).get("show_legend", True))
        legend_position = str(_config(widget).get("legend_position") or "right")
        horizontal_legend = show_legend and legend_position in {"top", "bottom"}
        legend_width = (
            min(width * 0.32, 110) if show_legend and legend_position in {"left", "right"} else 0
        )
        legend_height = 13 if horizontal_legend else 0
        size = max(4.0, min(width - legend_width, height - legend_height) - 8)
        chart_x = x + legend_width if show_legend and legend_position == "left" else x
        chart_y = y + legend_height if show_legend and legend_position == "bottom" else y
        left = chart_x + (width - legend_width - size) / 2
        bottom = chart_y + (height - legend_height - size) / 2
        start = 90.0
        colors = _palette(widget)
        for index, value in enumerate(values):
            extent = 360.0 * value / total
            canvas.setFillColor(HexColor(colors[index % len(colors)]))
            canvas.wedge(left, bottom, left + size, bottom + size, start, extent, stroke=0, fill=1)
            start += extent
        if widget_type == "donut":
            inset = size * 0.28
            canvas.setFillColor(HexColor(WHITE))
            canvas.circle(left + size / 2, bottom + size / 2, inset, stroke=0, fill=1)
        if show_legend:
            category_key = next(
                (_column_key(item) for item in columns if _column_key(item) != numeric_key), ""
            )
            canvas.setFont(PDF_FONT, 6.5)
            cursor = x
            for index, row in enumerate(rows[: min(8, len(values))]):
                if horizontal_legend:
                    legend_x = cursor
                    legend_y = y + 2 if legend_position == "bottom" else y + height - 9
                else:
                    legend_x = x + 2 if legend_position == "left" else x + width - legend_width + 2
                    legend_y = y + height - 10 - index * 11
                canvas.setFillColor(HexColor(colors[index % len(colors)]))
                canvas.rect(legend_x, legend_y - 2, 6, 6, stroke=0, fill=1)
                canvas.setFillColor(HexColor(INK))
                label = _display_text(_text(row.get(category_key), 22))
                canvas.drawString(
                    legend_x + 9,
                    legend_y - 2,
                    label,
                )
                if horizontal_legend:
                    cursor += min(120.0, stringWidth(label, PDF_FONT, 6.5) + 24)

    @staticmethod
    def _map(
        canvas: Canvas,
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        numeric_keys = [
            _column_key(column)
            for column in columns
            if any(_numeric(row.get(_column_key(column))) is not None for row in rows)
        ]
        if len(numeric_keys) < 2:
            canvas.setFillColor(HexColor(MUTED))
            canvas.drawString(x, y + height / 2, "Map requires longitude and latitude values")
            return
        longitude_key, latitude_key = numeric_keys[:2]
        canvas.setFillColor(HexColor("#EFF6FF"))
        canvas.setStrokeColor(HexColor(BORDER))
        canvas.roundRect(x, y, width, height, 5, stroke=1, fill=1)
        canvas.setStrokeColor(HexColor("#CBD5E1"))
        canvas.setDash(2, 3)
        for fraction in (0.25, 0.5, 0.75):
            canvas.line(x + width * fraction, y, x + width * fraction, y + height)
            canvas.line(x, y + height * fraction, x + width, y + height * fraction)
        canvas.setDash()
        canvas.setFillColor(HexColor(BRAND))
        for row in rows[:100]:
            longitude = max(-180.0, min(180.0, _numeric(row.get(longitude_key)) or 0.0))
            latitude = max(-90.0, min(90.0, _numeric(row.get(latitude_key)) or 0.0))
            px = x + (longitude + 180.0) / 360.0 * width
            py = y + (latitude + 90.0) / 180.0 * height
            canvas.circle(px, py, 4, stroke=0, fill=1)

    @staticmethod
    def _kpi(
        canvas: Canvas,
        widget: dict[str, object],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        key = next(
            (
                _column_key(column)
                for column in reversed(columns)
                if rows and _numeric(rows[0].get(_column_key(column))) is not None
            ),
            "",
        )
        value = rows[0].get(key) if rows and key else None
        canvas.setFillColor(HexColor(_conditional_color(value, widget, BRAND)))
        canvas.setFont(PDF_FONT_BOLD, 28)
        canvas.drawString(x, y + height / 2 - 4, _display_text(_formatted_value(value, widget)))
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont(PDF_FONT, 9)
        label = next((_column_label(item) for item in columns if _column_key(item) == key), key)
        canvas.drawString(x, y + height / 2 - 21, _display_text(label))

    @staticmethod
    def _metric_comparison(
        canvas: Canvas,
        widget: dict[str, object],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        numeric_keys = [
            _column_key(column)
            for column in columns
            if rows and _numeric(rows[0].get(_column_key(column))) is not None
        ]
        actual = _numeric(rows[0].get(numeric_keys[-1])) if rows and numeric_keys else None
        target = _numeric(rows[1].get(numeric_keys[-1])) if len(rows) > 1 and numeric_keys else None
        delta = ((actual - target) / target * 100) if actual is not None and target else 0.0
        center_y = y + height / 2
        canvas.setFont(PDF_FONT_BOLD, 21)
        canvas.setFillColor(HexColor(_conditional_color(actual, widget, BRAND)))
        canvas.drawString(x, center_y, _display_text(_formatted_value(actual, widget)))
        canvas.setFillColor(HexColor(ACCENT if delta >= 0 else "#DC2626"))
        canvas.setFont(PDF_FONT_BOLD, 12)
        canvas.drawCentredString(x + width / 2, center_y + 4, f"{delta:+.1f}%")
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont(PDF_FONT_BOLD, 21)
        canvas.drawRightString(x + width, center_y, _display_text(_formatted_value(target, widget)))
        canvas.setFont(PDF_FONT, 8)
        canvas.drawString(x, center_y - 17, "Actual")
        canvas.drawRightString(x + width, center_y - 17, "Target")

    @staticmethod
    def _gauge(
        canvas: Canvas,
        widget: dict[str, object],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        key = next(
            (
                _column_key(column)
                for column in reversed(columns)
                if rows and _numeric(rows[0].get(_column_key(column))) is not None
            ),
            "",
        )
        value = (_numeric(rows[0].get(key)) or 0.0) % 100 if rows and key else 0.0
        radius = min(width * 0.28, height * 0.72)
        cx, cy = x + width / 2, y + height * 0.34
        canvas.setLineWidth(12)
        canvas.setStrokeColor(HexColor(BORDER))
        canvas.arc(cx - radius, cy - radius, cx + radius, cy + radius, 0, 180)
        canvas.setStrokeColor(HexColor(_conditional_color(value, widget, BRAND)))
        canvas.arc(cx - radius, cy - radius, cx + radius, cy + radius, 0, 180 * value / 100)
        canvas.setFillColor(HexColor(INK))
        canvas.setFont(PDF_FONT_BOLD, 19)
        canvas.drawCentredString(cx, cy - 3, f"{value:.0f}%")
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont(PDF_FONT, 8)
        canvas.drawCentredString(
            cx,
            cy - 18,
            _display_text(
                _column_label(next((c for c in columns if _column_key(c) == key), {"key": key}))
            ),
        )

    @staticmethod
    def _progress(
        canvas: Canvas,
        widget: dict[str, object],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        key = next(
            (
                _column_key(column)
                for column in reversed(columns)
                if rows and _numeric(rows[0].get(_column_key(column))) is not None
            ),
            "",
        )
        value = (_numeric(rows[0].get(key)) or 0.0) % 100 if rows and key else 0.0
        bar_y = y + height / 2
        canvas.setFillColor(HexColor(BORDER))
        canvas.roundRect(x, bar_y, width, 14, 7, stroke=0, fill=1)
        canvas.setFillColor(HexColor(_conditional_color(value, widget, BRAND)))
        canvas.roundRect(x, bar_y, width * value / 100, 14, 7, stroke=0, fill=1)
        canvas.setFillColor(HexColor(INK))
        canvas.setFont(PDF_FONT_BOLD, 15)
        canvas.drawRightString(x + width, bar_y + 23, f"{value:.0f}%")

    @staticmethod
    def _table(
        canvas: Canvas,
        widget: dict[str, object],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        keys = [_column_key(column) for column in columns if _column_key(column)][:8]
        if not keys and rows:
            keys = list(rows[0])[:8]
        if not keys:
            canvas.setFillColor(HexColor(MUTED))
            canvas.drawString(x, y + height / 2, "No rows")
            return
        row_height = 18
        visible = min(len(rows), max(1, int((height - row_height) // row_height)))
        col_width = width / len(keys)
        canvas.setFillColor(HexColor(BRAND_DARK))
        canvas.rect(x, y + height - row_height, width, row_height, stroke=0, fill=1)
        canvas.setFillColor(HexColor(WHITE))
        canvas.setFont(PDF_FONT_BOLD, 7)
        labels = {_column_key(column): _column_label(column) for column in columns}
        for index, key in enumerate(keys):
            canvas.drawString(
                x + index * col_width + 4,
                y + height - 12,
                _display_text(_text(labels.get(key, key), 20)),
            )
        canvas.setFont(PDF_FONT, 7)
        for row_index, row in enumerate(rows[:visible]):
            bottom = y + height - row_height * (row_index + 2)
            canvas.setFillColor(HexColor(SURFACE if row_index % 2 else WHITE))
            canvas.rect(x, bottom, width, row_height, stroke=0, fill=1)
            canvas.setFillColor(HexColor(INK))
            for index, key in enumerate(keys):
                value = row.get(key)
                canvas.setFillColor(HexColor(_conditional_color(value, widget, INK)))
                canvas.drawString(
                    x + index * col_width + 4,
                    bottom + 6,
                    _display_text(_formatted_value(value, widget)),
                )
        if len(rows) > visible:
            canvas.setFillColor(HexColor(MUTED))
            canvas.drawRightString(x + width, y + 2, f"{len(rows) - visible:,} more rows")

    @staticmethod
    def _chart(
        canvas: Canvas,
        widget: dict[str, object],
        widget_type: str,
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        numeric_keys = [
            _column_key(column)
            for column in columns
            if any(_numeric(row.get(_column_key(column))) is not None for row in rows)
        ][:4]
        category_key = next(
            (_column_key(column) for column in columns if _column_key(column) not in numeric_keys),
            "",
        )
        data = rows[:12]
        if not data or not numeric_keys:
            canvas.setFillColor(HexColor(MUTED))
            canvas.setFont(PDF_FONT, 9)
            canvas.drawString(x, y + height / 2, "No chart data")
            return
        values = [
            abs(value)
            for row in data
            for key in numeric_keys
            if (value := _numeric(row.get(key))) is not None
        ]
        config = _config(widget)
        axis = cast(dict[str, object], config.get("axis", {}))
        x_axis = cast(dict[str, object], axis.get("x", {}))
        y_axis = cast(dict[str, object], axis.get("y", {}))
        supports_axes = widget_type not in {"pie", "donut"}
        x_axis_title = str(x_axis.get("title") or "") if supports_axes else ""
        y_axis_title = str(y_axis.get("title") or "") if supports_axes else ""
        legend_position = str(config.get("legend_position") or "top")
        show_legend = bool(config.get("show_legend", True)) and len(numeric_keys) > 1
        bottom_legend = 12.0 if show_legend and legend_position == "bottom" else 0.0
        top_legend = 12.0 if show_legend and legend_position == "top" else 0.0
        axis_title_height = 10.0 if x_axis_title else 0.0
        maximum = max(values, default=1) or 1
        plot_y = y + 18 + bottom_legend + axis_title_height
        plot_h = max(12.0, height - 30 - bottom_legend - top_legend - axis_title_height)
        colors = _palette(widget)
        if x_axis_title:
            canvas.setFillColor(HexColor(MUTED))
            canvas.setFont(PDF_FONT_BOLD, 6.5)
            canvas.drawCentredString(
                x + width / 2,
                y + bottom_legend + 1,
                _display_text(_text(x_axis_title, 48)),
            )
        if y_axis_title:
            canvas.setFillColor(HexColor(MUTED))
            canvas.setFont(PDF_FONT_BOLD, 6.5)
            canvas.drawString(
                x,
                y + height - top_legend - 17,
                _display_text(f"Y: {_text(y_axis_title, 36)}"),
            )
        if bool(config.get("show_gridlines", True)):
            canvas.setStrokeColor(HexColor(BORDER))
            for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
                grid_y = plot_y + fraction * plot_h
                canvas.line(x, grid_y, x + width, grid_y)
        if widget_type == "scatter" and len(numeric_keys) >= 2:
            x_key, y_key = numeric_keys[:2]
            x_values = [(_numeric(row.get(x_key)) or 0.0) for row in data]
            y_values = [(_numeric(row.get(y_key)) or 0.0) for row in data]
            max_x = max((abs(value) for value in x_values), default=1) or 1
            max_y = max((abs(value) for value in y_values), default=1) or 1
            canvas.setFillColor(HexColor(colors[0]))
            for x_value, y_value in zip(x_values, y_values, strict=True):
                px = x + max(0.0, x_value) / max_x * width
                py = plot_y + max(0.0, y_value) / max_y * plot_h
                canvas.circle(px, py, 4, stroke=0, fill=1)
        elif widget_type in {"line", "area"}:
            for series_index, key in enumerate(numeric_keys):
                canvas.setStrokeColor(HexColor(colors[series_index % len(colors)]))
                canvas.setLineWidth(2)
                points: list[tuple[float, float]] = []
                for index, row in enumerate(data):
                    value = _numeric(row.get(key)) or 0
                    px = x + (index / max(1, len(data) - 1)) * width
                    py = plot_y + max(0, value) / maximum * plot_h
                    points.append((px, py))
                for first, second in pairwise(points):
                    canvas.line(*first, *second)
                for px, py in points:
                    canvas.circle(px, py, 2, stroke=0, fill=1)
        elif widget_type == "stacked-bar":
            group = width / max(1, len(data))
            bar_width = max(3, group * 0.7)
            stacked_maximum = (
                max(
                    (
                        sum(max(0.0, _numeric(row.get(key)) or 0.0) for key in numeric_keys)
                        for row in data
                    ),
                    default=1.0,
                )
                or 1.0
            )
            for row_index, row in enumerate(data):
                bottom = plot_y
                bx = x + row_index * group + group * 0.15
                for series_index, key in enumerate(numeric_keys):
                    value = max(0.0, _numeric(row.get(key)) or 0.0)
                    bar_h = value / stacked_maximum * plot_h
                    canvas.setFillColor(HexColor(colors[series_index % len(colors)]))
                    canvas.rect(bx, bottom, bar_width, bar_h, stroke=0, fill=1)
                    bottom += bar_h
        else:
            group = width / max(1, len(data))
            bar_width = max(3, group * 0.72 / len(numeric_keys))
            for row_index, row in enumerate(data):
                for series_index, key in enumerate(numeric_keys):
                    value = max(0, _numeric(row.get(key)) or 0)
                    bar_h = value / maximum * plot_h
                    bx = x + row_index * group + group * 0.14 + series_index * bar_width
                    canvas.setFillColor(HexColor(colors[series_index % len(colors)]))
                    canvas.rect(bx, plot_y, bar_width - 1, bar_h, stroke=0, fill=1)
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont(PDF_FONT, 6.5)
        for index, row in enumerate(data):
            label = str(row.get(category_key, "")) if category_key else str(index + 1)
            px = x + (index + 0.5) * (width / len(data))
            available = max(20.0, width / len(data) - 3)
            lines = _wrap_text(label, available, lambda line: stringWidth(line, PDF_FONT, 6.5))
            for line_index, display_label in enumerate(lines[:2]):
                label_width = stringWidth(display_label, PDF_FONT, 6.5)
                canvas.drawString(
                    px - label_width / 2,
                    y + bottom_legend + axis_title_height + 8 - line_index * 7,
                    display_label,
                )
        if show_legend:
            canvas.setFont(PDF_FONT, 6.5)
            vertical_legend = legend_position in {"left", "right"}
            cursor = x + width - 105 if legend_position == "right" else x
            legend_y = y + 2 if legend_position == "bottom" else y + height - 7
            for series_index, key in enumerate(numeric_keys):
                item_y = legend_y - series_index * 11 if vertical_legend else legend_y
                canvas.setFillColor(HexColor(colors[series_index % len(colors)]))
                canvas.rect(cursor, item_y, 6, 6, stroke=0, fill=1)
                canvas.setFillColor(HexColor(INK))
                label = next(
                    (_column_label(item) for item in columns if _column_key(item) == key), key
                )
                display = _display_text(_text(label, 24))
                canvas.drawString(cursor + 9, item_y, display)
                if not vertical_legend:
                    cursor += min(100.0, stringWidth(display, PDF_FONT, 6.5) + 22)


class PngDashboardRenderer:
    format = "png"

    def render(self, document: RenderDocument) -> RenderedArtifact:
        scale = 2
        width = 1440
        header = 150
        gap = 10
        row_height = 76
        cell_width = (width - 80 - gap * 11) / 12
        cursor = header
        page_headers: list[tuple[str, int]] = []
        entries: list[tuple[dict[str, object], int]] = []
        for page in _pages(document) or [{"name": "Dashboard", "widgets": []}]:
            page_widgets = [
                item
                for item in cast(list[dict[str, object]], page.get("widgets", []))
                if not item.get("hidden", False)
            ]
            page_headers.append((str(page.get("name") or "Dashboard"), cursor))
            grid_top = cursor + 38
            entries.extend((widget, grid_top) for widget in page_widgets)
            max_row = max(
                (_layout(widget)["y"] + _layout(widget)["h"] for widget in page_widgets),
                default=8,
            )
            cursor = grid_top + max(8, max_row) * (row_height + gap) + 36
        height = cursor + 70
        image = Image.new("RGB", (width * scale, height * scale), SURFACE)
        draw = ImageDraw.Draw(image)
        font = self._font(22 * scale)
        title_font = self._font(34 * scale, bold=True)
        card_title = self._font(17 * scale, bold=True)
        small = self._font(12 * scale)

        def box(
            coords: tuple[float, float, float, float],
            *,
            fill: str,
            outline: str,
            width: int,
        ) -> None:
            draw.rounded_rectangle(
                tuple(value * scale for value in coords),
                radius=12 * scale,
                fill=fill,
                outline=outline,
                width=width,
            )

        draw.rectangle((0, 0, width * scale, 104 * scale), fill=BRAND_DARK)
        draw.text(
            (40 * scale, 26 * scale),
            _display_text(document.dashboard_name[:70]),
            font=title_font,
            fill=WHITE,
        )
        generated = (
            f"Version {document.dashboard_version} · "
            f"{document.generated_at:%d %b %Y %H:%M} · {document.timezone}"
        )
        draw.text((40 * scale, 112 * scale), _display_text(generated), font=small, fill=MUTED)
        filter_text = _filter_summary(document.filters)
        draw.text(
            (width * scale - 40 * scale, 112 * scale),
            _display_text(filter_text[:90]),
            font=small,
            fill=MUTED,
            anchor="ra",
        )

        for page_name, page_top in page_headers:
            draw.text(
                (40 * scale, page_top * scale),
                _display_text(page_name),
                font=font,
                fill=INK,
            )

        for widget, grid_top in entries:
            layout = _layout(widget)
            config = _config(widget)
            x = 40 + layout["x"] * (cell_width + gap)
            y = grid_top + layout["y"] * (row_height + gap)
            card_width = layout["w"] * cell_width + (layout["w"] - 1) * gap
            card_height = layout["h"] * row_height + (layout["h"] - 1) * gap
            box(
                (x, y, x + card_width, y + card_height),
                fill=str(config.get("background") or WHITE),
                outline=(
                    BORDER
                    if bool(config.get("border", True))
                    else str(config.get("background") or WHITE)
                ),
                width=scale,
            )
            draw.text(
                ((x + 20) * scale, (y + 17) * scale),
                _display_text(_text(widget.get("title", "Widget"), 58)),
                font=card_title,
                fill=INK,
            )
            draw.text(
                ((x + card_width - 16) * scale, (y + 20) * scale),
                str(widget.get("type", "widget")),
                font=small,
                fill=MUTED,
                anchor="ra",
            )
            columns, result_rows = _result(document, widget)
            kind = str(widget.get("type") or "table")
            bounds = (x + 20, y + 58, x + card_width - 20, y + card_height - 20)
            if kind == "kpi":
                self._draw_kpi(draw, widget, bounds, columns, result_rows, title_font, small, scale)
            elif kind == "metric-comparison":
                self._draw_metric_comparison(
                    draw, widget, bounds, columns, result_rows, title_font, small, scale
                )
            elif kind == "gauge":
                self._draw_gauge(
                    draw, widget, bounds, columns, result_rows, title_font, small, scale
                )
            elif kind == "progress":
                self._draw_progress(draw, widget, bounds, columns, result_rows, title_font, scale)
            elif kind in {"table", "pivot"}:
                self._draw_table(draw, widget, bounds, columns, result_rows, small, scale)
            elif kind in {"text", "rich-text", "image", "filter", "date-filter"}:
                content = str(widget.get("content") or widget.get("description") or "")
                lines = _wrap_text(
                    content,
                    (bounds[2] - bounds[0]) * scale,
                    lambda line: draw.textlength(line, font=small),
                )
                visible_lines = lines[: max(1, int((bounds[3] - bounds[1]) / 18))]
                for line_index, line in enumerate(visible_lines):
                    draw.text(
                        (bounds[0] * scale, (bounds[1] + line_index * 18) * scale),
                        line,
                        font=small,
                        fill=INK,
                    )
            elif kind == "map":
                self._draw_map(draw, bounds, columns, result_rows, small, scale)
            else:
                self._draw_chart(
                    draw, widget, kind, bounds, columns, result_rows, font, small, scale
                )
        draw.text(
            (40 * scale, (height - 38) * scale),
            "Veltrix Intelligence Platform · Confidential",
            font=small,
            fill=MUTED,
        )
        image = image.resize((width * scale, height * scale), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        png_info = PngImagePlugin.PngInfo()
        png_info.add_text(
            "vip.dashboard.definition",
            json.dumps(_parity_manifest(document), ensure_ascii=False, separators=(",", ":")),
        )
        image.save(output, "PNG", optimize=True, dpi=(192, 192), pnginfo=png_info)
        return RenderedArtifact(output.getvalue(), "image/png", "png")

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> Any:
        candidate = _font_path(bold=bold)
        if candidate is not None:
            return ImageFont.truetype(str(candidate), size)
        return ImageFont.load_default()

    @staticmethod
    def _draw_kpi(
        draw: ImageDraw.ImageDraw,
        widget: dict[str, object],
        bounds: tuple[float, float, float, float],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        title_font: ImageFont.ImageFont,
        small: ImageFont.ImageFont,
        scale: int,
    ) -> None:
        key = next(
            (
                _column_key(column)
                for column in reversed(columns)
                if rows and _numeric(rows[0].get(_column_key(column))) is not None
            ),
            "",
        )
        x, y, _, _ = bounds
        draw.text(
            (x * scale, (y + 24) * scale),
            _display_text(_formatted_value(rows[0].get(key) if rows and key else None, widget)),
            font=title_font,
            fill=_conditional_color(rows[0].get(key) if rows and key else None, widget, BRAND),
        )
        label = next((_column_label(item) for item in columns if _column_key(item) == key), key)
        draw.text(
            (x * scale, (y + 75) * scale),
            _display_text(label),
            font=small,
            fill=MUTED,
        )

    @staticmethod
    def _draw_metric_comparison(
        draw: ImageDraw.ImageDraw,
        widget: dict[str, object],
        bounds: tuple[float, float, float, float],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        title_font: ImageFont.ImageFont,
        small: ImageFont.ImageFont,
        scale: int,
    ) -> None:
        x1, y1, x2, _ = bounds
        numeric_keys = [
            _column_key(column)
            for column in columns
            if rows and _numeric(rows[0].get(_column_key(column))) is not None
        ]
        actual = _numeric(rows[0].get(numeric_keys[-1])) if rows and numeric_keys else None
        target = _numeric(rows[1].get(numeric_keys[-1])) if len(rows) > 1 and numeric_keys else None
        delta = ((actual - target) / target * 100) if actual is not None and target else 0.0
        draw.text(
            (x1 * scale, (y1 + 24) * scale),
            _display_text(_formatted_value(actual, widget)),
            font=title_font,
            fill=_conditional_color(actual, widget, BRAND),
        )
        draw.text((x1 * scale, (y1 + 72) * scale), "Actual", font=small, fill=MUTED)
        draw.text(
            (((x1 + x2) / 2) * scale, (y1 + 39) * scale),
            f"{delta:+.1f}%",
            font=small,
            fill=ACCENT if delta >= 0 else "#DC2626",
            anchor="ma",
        )
        draw.text(
            (x2 * scale, (y1 + 24) * scale),
            _display_text(_formatted_value(target, widget)),
            font=title_font,
            fill=MUTED,
            anchor="ra",
        )
        draw.text((x2 * scale, (y1 + 72) * scale), "Target", font=small, fill=MUTED, anchor="ra")

    @staticmethod
    def _draw_gauge(
        draw: ImageDraw.ImageDraw,
        widget: dict[str, object],
        bounds: tuple[float, float, float, float],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        title_font: ImageFont.ImageFont,
        small: ImageFont.ImageFont,
        scale: int,
    ) -> None:
        x1, y1, x2, y2 = bounds
        key = next(
            (
                _column_key(column)
                for column in reversed(columns)
                if rows and _numeric(rows[0].get(_column_key(column))) is not None
            ),
            "",
        )
        value = (_numeric(rows[0].get(key)) or 0.0) % 100 if rows and key else 0.0
        diameter = min((x2 - x1) * 0.55, (y2 - y1) * 1.5)
        left = (x1 + x2 - diameter) / 2
        top = y1 + 8
        box = (left * scale, top * scale, (left + diameter) * scale, (top + diameter) * scale)
        stroke = 12 * scale
        draw.arc(box, 180, 360, fill=BORDER, width=stroke)
        draw.arc(
            box,
            180,
            180 + 180 * value / 100,
            fill=_conditional_color(value, widget, BRAND),
            width=stroke,
        )
        draw.text(
            (((x1 + x2) / 2) * scale, (top + diameter * 0.48) * scale),
            f"{value:.0f}%",
            font=title_font,
            fill=INK,
            anchor="mm",
        )
        draw.text(
            (((x1 + x2) / 2) * scale, (top + diameter * 0.67) * scale),
            _display_text(key),
            font=small,
            fill=MUTED,
            anchor="ma",
        )

    @staticmethod
    def _draw_progress(
        draw: ImageDraw.ImageDraw,
        widget: dict[str, object],
        bounds: tuple[float, float, float, float],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        title_font: ImageFont.ImageFont,
        scale: int,
    ) -> None:
        x1, y1, x2, _ = bounds
        key = next(
            (
                _column_key(column)
                for column in reversed(columns)
                if rows and _numeric(rows[0].get(_column_key(column))) is not None
            ),
            "",
        )
        value = (_numeric(rows[0].get(key)) or 0.0) % 100 if rows and key else 0.0
        top = y1 + 56
        draw.rounded_rectangle(
            (x1 * scale, top * scale, x2 * scale, (top + 18) * scale),
            radius=9 * scale,
            fill=BORDER,
        )
        draw.rounded_rectangle(
            (x1 * scale, top * scale, (x1 + (x2 - x1) * value / 100) * scale, (top + 18) * scale),
            radius=9 * scale,
            fill=_conditional_color(value, widget, BRAND),
        )
        draw.text(
            (x2 * scale, (y1 + 10) * scale),
            f"{value:.0f}%",
            font=title_font,
            fill=INK,
            anchor="ra",
        )

    @staticmethod
    def _draw_table(
        draw: ImageDraw.ImageDraw,
        widget: dict[str, object],
        bounds: tuple[float, float, float, float],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        font: ImageFont.ImageFont,
        scale: int,
    ) -> None:
        x1, y1, x2, y2 = bounds
        keys = [_column_key(column) for column in columns if _column_key(column)][:5]
        if not keys and rows:
            keys = list(rows[0])[:5]
        if not keys:
            draw.text((x1 * scale, (y1 + 30) * scale), "No rows", font=font, fill=MUTED)
            return
        col_width = (x2 - x1) / len(keys)
        row_height = 30
        draw.rectangle(
            (x1 * scale, y1 * scale, x2 * scale, (y1 + row_height) * scale), fill=BRAND_DARK
        )
        labels = {_column_key(column): _column_label(column) for column in columns}
        for index, key in enumerate(keys):
            draw.text(
                ((x1 + index * col_width + 7) * scale, (y1 + 7) * scale),
                _display_text(_text(labels.get(key, key), 14)),
                font=font,
                fill=WHITE,
            )
        visible = max(1, int((y2 - y1 - row_height) / row_height))
        for row_index, row in enumerate(rows[:visible]):
            top = y1 + row_height * (row_index + 1)
            if row_index % 2:
                draw.rectangle(
                    (x1 * scale, top * scale, x2 * scale, (top + row_height) * scale), fill=SURFACE
                )
            for index, key in enumerate(keys):
                value = row.get(key)
                draw.text(
                    ((x1 + index * col_width + 7) * scale, (top + 7) * scale),
                    _display_text(_formatted_value(value, widget)),
                    font=font,
                    fill=_conditional_color(value, widget, INK),
                )

    @staticmethod
    def _draw_map(
        draw: ImageDraw.ImageDraw,
        bounds: tuple[float, float, float, float],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        font: ImageFont.ImageFont,
        scale: int,
    ) -> None:
        x1, y1, x2, y2 = bounds
        numeric_keys = [
            _column_key(column)
            for column in columns
            if any(_numeric(row.get(_column_key(column))) is not None for row in rows)
        ]
        if len(numeric_keys) < 2:
            draw.text(
                (x1 * scale, (y1 + 30) * scale),
                "Map requires longitude and latitude values",
                font=font,
                fill=MUTED,
            )
            return
        longitude_key, latitude_key = numeric_keys[:2]
        draw.rounded_rectangle(
            (x1 * scale, y1 * scale, x2 * scale, y2 * scale),
            radius=6 * scale,
            fill="#EFF6FF",
            outline=BORDER,
            width=scale,
        )
        for fraction in (0.25, 0.5, 0.75):
            px = (x1 + (x2 - x1) * fraction) * scale
            py = (y1 + (y2 - y1) * fraction) * scale
            draw.line((px, y1 * scale, px, y2 * scale), fill="#CBD5E1", width=scale)
            draw.line((x1 * scale, py, x2 * scale, py), fill="#CBD5E1", width=scale)
        for row in rows[:100]:
            longitude = max(-180.0, min(180.0, _numeric(row.get(longitude_key)) or 0.0))
            latitude = max(-90.0, min(90.0, _numeric(row.get(latitude_key)) or 0.0))
            px = (x1 + (longitude + 180.0) / 360.0 * (x2 - x1)) * scale
            py = (y2 - (latitude + 90.0) / 180.0 * (y2 - y1)) * scale
            radius = 5 * scale
            draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=BRAND)

    @staticmethod
    def _draw_chart(
        draw: ImageDraw.ImageDraw,
        widget: dict[str, object],
        widget_type: str,
        bounds: tuple[float, float, float, float],
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        font: ImageFont.ImageFont,
        small: ImageFont.ImageFont,
        scale: int,
    ) -> None:
        x1, y1, x2, y2 = bounds
        numeric_keys = [
            _column_key(column)
            for column in columns
            if any(_numeric(row.get(_column_key(column))) is not None for row in rows)
        ][:3]
        category = next(
            (_column_key(column) for column in columns if _column_key(column) not in numeric_keys),
            "",
        )
        data = rows[:10]
        if not data or not numeric_keys:
            draw.text((x1 * scale, (y1 + 30) * scale), "No chart data", font=font, fill=MUTED)
            return
        config = _config(widget)
        colors = _palette(widget)
        axis = cast(dict[str, object], config.get("axis", {}))
        x_axis = cast(dict[str, object], axis.get("x", {}))
        y_axis = cast(dict[str, object], axis.get("y", {}))
        supports_axes = widget_type not in {"pie", "donut"}
        x_axis_title = str(x_axis.get("title") or "") if supports_axes else ""
        y_axis_title = str(y_axis.get("title") or "") if supports_axes else ""
        legend_position = str(config.get("legend_position") or "top")
        show_legend = bool(config.get("show_legend", True)) and (
            len(numeric_keys) > 1 or widget_type in {"pie", "donut"}
        )

        def draw_legend(labels: list[str]) -> None:
            if not show_legend:
                return
            if legend_position == "bottom":
                cursor_x, cursor_y = x1, y2 - 25
            elif legend_position == "right":
                cursor_x, cursor_y = x2 - 150, y1 + 3
            elif legend_position == "left":
                cursor_x, cursor_y = x1, y1 + 3
            else:
                cursor_x, cursor_y = x1, y1 + 3
            for index, label in enumerate(labels[:8]):
                if legend_position in {"left", "right"}:
                    item_x = cursor_x
                    item_y = cursor_y + index * 18
                else:
                    item_x = cursor_x + index * 145
                    item_y = cursor_y
                draw.rectangle(
                    (
                        item_x * scale,
                        item_y * scale,
                        (item_x + 8) * scale,
                        (item_y + 8) * scale,
                    ),
                    fill=colors[index % len(colors)],
                )
                draw.text(
                    ((item_x + 12) * scale, (item_y - 2) * scale),
                    _display_text(_text(label, 22)),
                    font=small,
                    fill=INK,
                )

        bottom_reserve = 28 if show_legend and legend_position == "bottom" else 0
        top_reserve = 22 if show_legend and legend_position == "top" else 0
        axis_reserve = 18 if x_axis_title else 0
        plot_top = y1 + top_reserve + (16 if y_axis_title else 0)
        plot_bottom = y2 - 30 - bottom_reserve - axis_reserve
        if y_axis_title:
            draw.text(
                (x1 * scale, (y1 + top_reserve) * scale),
                _display_text(f"Y: {_text(y_axis_title, 40)}"),
                font=small,
                fill=MUTED,
            )
        if x_axis_title:
            draw.text(
                (((x1 + x2) / 2) * scale, (y2 - bottom_reserve - 4) * scale),
                _display_text(_text(x_axis_title, 48)),
                font=small,
                fill=MUTED,
                anchor="ms",
            )
        maximum = (
            max(
                (
                    abs(value)
                    for row in data
                    for key in numeric_keys
                    if (value := _numeric(row.get(key))) is not None
                ),
                default=1,
            )
            or 1
        )
        group = (x2 - x1) / len(data)
        bar_width = max(3, group * 0.7 / len(numeric_keys))
        if widget_type in {"pie", "donut"}:
            values = [max(0.0, _numeric(row.get(numeric_keys[0])) or 0.0) for row in data]
            total = sum(values)
            if total <= 0:
                draw.text((x1 * scale, (y1 + 30) * scale), "No chart data", font=font, fill=MUTED)
                return
            diameter = max(8.0, min(x2 - x1, plot_bottom - plot_top) - 8)
            left = x1 + ((x2 - x1) - diameter) / 2
            top = plot_top + ((plot_bottom - plot_top) - diameter) / 2
            start = -90.0
            for index, value in enumerate(values):
                end = start + 360.0 * value / total
                draw.pieslice(
                    (
                        left * scale,
                        top * scale,
                        (left + diameter) * scale,
                        (top + diameter) * scale,
                    ),
                    start=start,
                    end=end,
                    fill=colors[index % len(colors)],
                )
                start = end
            if widget_type == "donut":
                inset = diameter * 0.3
                draw.ellipse(
                    (
                        (left + inset) * scale,
                        (top + inset) * scale,
                        (left + diameter - inset) * scale,
                        (top + diameter - inset) * scale,
                    ),
                    fill=WHITE,
                )
            category_labels = [str(row.get(category, index + 1)) for index, row in enumerate(data)]
            draw_legend(category_labels)
            return
        if bool(config.get("show_gridlines", True)):
            for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
                grid_y = plot_top + fraction * (plot_bottom - plot_top)
                draw.line(
                    (x1 * scale, grid_y * scale, x2 * scale, grid_y * scale),
                    fill=BORDER,
                    width=scale,
                )
        if widget_type == "scatter" and len(numeric_keys) >= 2:
            x_key, y_key = numeric_keys[:2]
            x_values = [(_numeric(row.get(x_key)) or 0.0) for row in data]
            y_values = [(_numeric(row.get(y_key)) or 0.0) for row in data]
            max_x = max((abs(value) for value in x_values), default=1) or 1
            max_y = max((abs(value) for value in y_values), default=1) or 1
            for x_value, y_value in zip(x_values, y_values, strict=True):
                px = x1 + max(0.0, x_value) / max_x * (x2 - x1)
                py = plot_bottom - max(0.0, y_value) / max_y * (plot_bottom - plot_top - 12)
                radius = 4 * scale
                draw.ellipse(
                    (
                        px * scale - radius,
                        py * scale - radius,
                        px * scale + radius,
                        py * scale + radius,
                    ),
                    fill=BRAND,
                )
        elif widget_type in {"line", "area"}:
            for series_index, key in enumerate(numeric_keys):
                points = [
                    (
                        (x1 + (index + 0.5) * group) * scale,
                        (
                            plot_bottom
                            - max(0.0, _numeric(row.get(key)) or 0.0)
                            / maximum
                            * (plot_bottom - plot_top - 12)
                        )
                        * scale,
                    )
                    for index, row in enumerate(data)
                ]
                if widget_type == "area" and len(points) > 1:
                    draw.polygon(
                        [
                            (points[0][0], plot_bottom * scale),
                            *points,
                            (points[-1][0], plot_bottom * scale),
                        ],
                        fill=colors[series_index % len(colors)] + "55",
                    )
                if len(points) > 1:
                    draw.line(points, fill=colors[series_index % len(colors)], width=2 * scale)
                for px, py in points:
                    radius = 2 * scale
                    draw.ellipse(
                        (px - radius, py - radius, px + radius, py + radius),
                        fill=colors[series_index % len(colors)],
                    )
        elif widget_type == "stacked-bar":
            stacked_maximum = (
                max(
                    (
                        sum(max(0.0, _numeric(row.get(key)) or 0.0) for key in numeric_keys)
                        for row in data
                    ),
                    default=1.0,
                )
                or 1.0
            )
            stacked_width = max(3, group * 0.7)
            for row_index, row in enumerate(data):
                bottom = plot_bottom
                left = x1 + row_index * group + group * 0.15
                for series_index, key in enumerate(numeric_keys):
                    value = max(0.0, _numeric(row.get(key)) or 0.0)
                    height = value / stacked_maximum * (plot_bottom - plot_top - 12)
                    draw.rectangle(
                        (
                            left * scale,
                            (bottom - height) * scale,
                            (left + stacked_width) * scale,
                            bottom * scale,
                        ),
                        fill=colors[series_index % len(colors)],
                    )
                    bottom -= height
        else:
            for row_index, row in enumerate(data):
                for series_index, key in enumerate(numeric_keys):
                    value = max(0, _numeric(row.get(key)) or 0)
                    height = value / maximum * (plot_bottom - plot_top - 12)
                    left = x1 + row_index * group + group * 0.15 + series_index * bar_width
                    draw.rounded_rectangle(
                        (
                            left * scale,
                            (plot_bottom - height) * scale,
                            (left + bar_width - 2) * scale,
                            plot_bottom * scale,
                        ),
                        radius=2 * scale,
                        fill=colors[series_index % len(colors)],
                    )
        for row_index, row in enumerate(data):
            label = str(row.get(category, "")) if category else str(row_index + 1)
            lines = _wrap_text(
                label,
                max(20.0, group * scale - 4),
                lambda line: draw.textlength(line, font=small),
            )
            for line_index, line in enumerate(lines[:2]):
                draw.text(
                    (
                        (x1 + row_index * group + group / 2) * scale,
                        (plot_bottom + 7 + line_index * 14) * scale,
                    ),
                    line,
                    font=small,
                    fill=MUTED,
                    anchor="ma",
                )
        series_labels = [
            next((_column_label(item) for item in columns if _column_key(item) == key), key)
            for key in numeric_keys
        ]
        draw_legend(series_labels)


class RendererRegistry:
    def __init__(self) -> None:
        renderers: tuple[DashboardRenderer, ...] = (
            PdfDashboardRenderer(),
            PngDashboardRenderer(),
            JsonDashboardRenderer(),
            CsvDashboardRenderer(),
        )
        self._renderers = {renderer.format: renderer for renderer in renderers}

    def get(self, format_: str) -> DashboardRenderer:
        renderer = self._renderers.get(format_)
        if renderer is None:
            raise ApplicationError(
                code="DASHBOARD_EXPORT_FORMAT_UNSUPPORTED",
                message="The requested export format is unsupported.",
                status_code=422,
            )
        return renderer
