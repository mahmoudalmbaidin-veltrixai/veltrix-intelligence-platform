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

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4, landscape, portrait  # type: ignore[import-untyped]
from reportlab.pdfbase.pdfmetrics import stringWidth  # type: ignore[import-untyped]
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


@dataclass(frozen=True, slots=True)
class RenderDocument:
    dashboard_id: UUID
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
            "dashboard": {"name": document.dashboard_name},
            "widgets": [
                {
                    "title": widget.get("title", "Widget"),
                    "type": widget.get("type"),
                    "data": safe_results.get(str(widget.get("id")), {}),
                }
                for widget in _visible_widgets(document)
            ],
        }
        return RenderedArtifact(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
            "application/json",
            "json",
        )


class CsvDashboardRenderer:
    """Merged, Excel-compatible UTF-8 CSV with one ordered section per table."""

    format = "csv"

    def render(self, document: RenderDocument) -> RenderedArtifact:
        widgets = [
            item
            for item in _visible_widgets(document)
            if item.get("type") in {"table", "pivot"} and _result(document, item)[1]
        ]
        if not widgets:
            widgets = [item for item in _visible_widgets(document) if _result(document, item)[1]]
        if not widgets:
            raise ApplicationError(
                code="DASHBOARD_CSV_NO_DATA",
                message="The dashboard does not contain exportable tabular data.",
                status_code=422,
            )

        binary = io.BytesIO()
        binary.write(b"\xef\xbb\xbf")
        output = io.TextIOWrapper(binary, encoding="utf-8", newline="", write_through=True)
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(["VIP Dashboard Export"])
        writer.writerow(["Dashboard", document.dashboard_name])
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

        for index, widget in enumerate(widgets):
            columns, rows = _result(document, widget)
            keys = [_column_key(column) for column in columns if _column_key(column)]
            if not keys:
                keys = list(rows[0]) if rows else []
            labels = {
                _column_key(column): _column_label(column)
                for column in columns
                if _column_key(column)
            }
            writer.writerow([f"Table {index + 1}", _text(widget.get("title", "Table"), 200)])
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
        page_number = 0

        def start_page(title: str) -> float:
            nonlocal page_number
            page_number += 1
            canvas.setFillColor(HexColor(BRAND_DARK))
            canvas.rect(0, height - 70, width, 70, stroke=0, fill=1)
            canvas.setFillColor(HexColor(WHITE))
            canvas.setFont("Helvetica-Bold", 18)
            canvas.drawString(34, height - 32, document.dashboard_name[:85])
            canvas.setFont("Helvetica", 8)
            canvas.drawString(34, height - 49, title[:95])
            canvas.drawRightString(
                width - 34,
                height - 49,
                f"Generated {document.generated_at:%d %b %Y %H:%M} · {document.timezone}",
            )
            canvas.setFillColor(HexColor(MUTED))
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(34, height - 84, _filter_summary(document.filters)[:160])
            return float(height - 102)

        def finish_page() -> None:
            canvas.setStrokeColor(HexColor(BORDER))
            canvas.line(34, 28, width - 34, 28)
            canvas.setFillColor(HexColor(MUTED))
            canvas.setFont("Helvetica", 7.5)
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
            y = start_page(page_title)
            for widget in widgets:
                columns, rows = _result(document, widget)
                widget_type = str(widget.get("type") or "table")
                required = 230 if widget_type in {"table", "pivot"} else 155
                if y - required < 42:
                    finish_page()
                    canvas.showPage()
                    y = start_page(f"{page_title} · continued")
                card_height = min(required, y - 42)
                self._card(
                    canvas,
                    widget,
                    columns,
                    rows,
                    34,
                    y - card_height,
                    width - 68,
                    card_height,
                )
                y -= card_height + 12
            if not widgets:
                canvas.setFillColor(HexColor(MUTED))
                canvas.setFont("Helvetica", 11)
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
        canvas.setFillColor(HexColor(WHITE))
        canvas.setStrokeColor(HexColor(BORDER))
        canvas.roundRect(x, y, width, height, 7, stroke=1, fill=1)
        canvas.setFillColor(HexColor(INK))
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(x + 15, y + height - 21, _text(widget.get("title", "Widget"), 80))
        inner_y = y + 14
        inner_h = height - 48
        widget_type = str(widget.get("type") or "table")
        if widget_type in {"kpi", "gauge"}:
            self._kpi(canvas, columns, rows, x + 15, inner_y, width - 30, inner_h)
        elif widget_type in {"table", "pivot"}:
            self._table(canvas, columns, rows, x + 15, inner_y, width - 30, inner_h)
        else:
            self._chart(canvas, widget_type, columns, rows, x + 15, inner_y, width - 30, inner_h)

    @staticmethod
    def _kpi(
        canvas: Canvas,
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
        canvas.setFillColor(HexColor(BRAND))
        canvas.setFont("Helvetica-Bold", 28)
        canvas.drawString(x, y + height / 2 - 4, _text(value))
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont("Helvetica", 9)
        label = next((_column_label(item) for item in columns if _column_key(item) == key), key)
        canvas.drawString(x, y + height / 2 - 21, label)

    @staticmethod
    def _table(
        canvas: Canvas,
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
        canvas.setFont("Helvetica-Bold", 7)
        labels = {_column_key(column): _column_label(column) for column in columns}
        for index, key in enumerate(keys):
            canvas.drawString(
                x + index * col_width + 4,
                y + height - 12,
                _text(labels.get(key, key), 20),
            )
        canvas.setFont("Helvetica", 7)
        for row_index, row in enumerate(rows[:visible]):
            bottom = y + height - row_height * (row_index + 2)
            canvas.setFillColor(HexColor(SURFACE if row_index % 2 else WHITE))
            canvas.rect(x, bottom, width, row_height, stroke=0, fill=1)
            canvas.setFillColor(HexColor(INK))
            for index, key in enumerate(keys):
                canvas.drawString(
                    x + index * col_width + 4,
                    bottom + 6,
                    _text(row.get(key), 22),
                )
        if len(rows) > visible:
            canvas.setFillColor(HexColor(MUTED))
            canvas.drawRightString(x + width, y + 2, f"{len(rows) - visible:,} more rows")

    @staticmethod
    def _chart(
        canvas: Canvas,
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
            canvas.setFont("Helvetica", 9)
            canvas.drawString(x, y + height / 2, "No chart data")
            return
        values = [
            abs(value)
            for row in data
            for key in numeric_keys
            if (value := _numeric(row.get(key))) is not None
        ]
        maximum = max(values, default=1) or 1
        plot_y = y + 18
        plot_h = height - 30
        canvas.setStrokeColor(HexColor(BORDER))
        canvas.line(x, plot_y, x + width, plot_y)
        if widget_type in {"line", "area"}:
            for series_index, key in enumerate(numeric_keys):
                canvas.setStrokeColor(HexColor(PALETTE[series_index]))
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
        else:
            group = width / max(1, len(data))
            bar_width = max(3, group * 0.72 / len(numeric_keys))
            for row_index, row in enumerate(data):
                for series_index, key in enumerate(numeric_keys):
                    value = max(0, _numeric(row.get(key)) or 0)
                    bar_h = value / maximum * plot_h
                    bx = x + row_index * group + group * 0.14 + series_index * bar_width
                    canvas.setFillColor(HexColor(PALETTE[series_index]))
                    canvas.rect(bx, plot_y, bar_width - 1, bar_h, stroke=0, fill=1)
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont("Helvetica", 6.5)
        for index, row in enumerate(data):
            label = _text(row.get(category_key), 9) if category_key else str(index + 1)
            label_width = stringWidth(label, "Helvetica", 6.5)
            px = x + (index + 0.5) * (width / len(data))
            canvas.drawString(px - label_width / 2, y + 3, label)


class PngDashboardRenderer:
    format = "png"

    def render(self, document: RenderDocument) -> RenderedArtifact:
        widgets = _visible_widgets(document)
        scale = 2
        width = 1440
        header = 150
        card_width = (width - 120) // 2
        card_height = 300
        rows = max(1, math.ceil(len(widgets) / 2))
        height = header + rows * (card_height + 24) + 70
        image = Image.new("RGB", (width * scale, height * scale), SURFACE)
        draw = ImageDraw.Draw(image)
        font = self._font(22 * scale)
        title_font = self._font(34 * scale, bold=True)
        card_title = self._font(17 * scale, bold=True)
        small = self._font(12 * scale)

        def box(
            coords: tuple[int, int, int, int],
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
            (40 * scale, 26 * scale), document.dashboard_name[:70], font=title_font, fill=WHITE
        )
        generated = (
            f"Version {document.dashboard_version} · "
            f"{document.generated_at:%d %b %Y %H:%M} · {document.timezone}"
        )
        draw.text((40 * scale, 112 * scale), generated, font=small, fill=MUTED)
        filter_text = _filter_summary(document.filters)
        draw.text(
            (width * scale - 40 * scale, 112 * scale),
            filter_text[:90],
            font=small,
            fill=MUTED,
            anchor="ra",
        )

        for index, widget in enumerate(widgets):
            column = index % 2
            row = index // 2
            x = 40 + column * (card_width + 40)
            y = header + row * (card_height + 24)
            box((x, y, x + card_width, y + card_height), fill=WHITE, outline=BORDER, width=scale)
            draw.text(
                ((x + 20) * scale, (y + 17) * scale),
                _text(widget.get("title", "Widget"), 58),
                font=card_title,
                fill=INK,
            )
            columns, result_rows = _result(document, widget)
            kind = str(widget.get("type") or "table")
            bounds = (x + 20, y + 58, x + card_width - 20, y + card_height - 20)
            if kind in {"kpi", "gauge"}:
                self._draw_kpi(draw, bounds, columns, result_rows, title_font, small, scale)
            elif kind in {"table", "pivot"}:
                self._draw_table(draw, bounds, columns, result_rows, small, scale)
            else:
                self._draw_chart(draw, bounds, columns, result_rows, font, small, scale)
        draw.text(
            (40 * scale, (height - 38) * scale),
            "Veltrix Intelligence Platform · Confidential",
            font=small,
            fill=MUTED,
        )
        image = image.resize((width * scale, height * scale), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, "PNG", optimize=True, dpi=(192, 192))
        return RenderedArtifact(output.getvalue(), "image/png", "png")

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> Any:
        filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        candidates = (
            Path("/usr/share/fonts/truetype/dejavu") / filename,
            Path("/usr/local/share/fonts") / filename,
            Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
            Path(filename),
        )
        for candidate in candidates:
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _draw_kpi(
        draw: ImageDraw.ImageDraw,
        bounds: tuple[int, int, int, int],
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
            _text(rows[0].get(key) if rows and key else None),
            font=title_font,
            fill=BRAND,
        )
        label = next((_column_label(item) for item in columns if _column_key(item) == key), key)
        draw.text((x * scale, (y + 75) * scale), label, font=small, fill=MUTED)

    @staticmethod
    def _draw_table(
        draw: ImageDraw.ImageDraw,
        bounds: tuple[int, int, int, int],
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
                _text(labels.get(key, key), 14),
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
                draw.text(
                    ((x1 + index * col_width + 7) * scale, (top + 7) * scale),
                    _text(row.get(key), 15),
                    font=font,
                    fill=INK,
                )

    @staticmethod
    def _draw_chart(
        draw: ImageDraw.ImageDraw,
        bounds: tuple[int, int, int, int],
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
        plot_bottom = y2 - 30
        group = (x2 - x1) / len(data)
        bar_width = max(3, group * 0.7 / len(numeric_keys))
        draw.line(
            (x1 * scale, plot_bottom * scale, x2 * scale, plot_bottom * scale),
            fill=BORDER,
            width=scale,
        )
        for row_index, row in enumerate(data):
            for series_index, key in enumerate(numeric_keys):
                value = max(0, _numeric(row.get(key)) or 0)
                height = value / maximum * (plot_bottom - y1 - 12)
                left = x1 + row_index * group + group * 0.15 + series_index * bar_width
                draw.rounded_rectangle(
                    (
                        left * scale,
                        (plot_bottom - height) * scale,
                        (left + bar_width - 2) * scale,
                        plot_bottom * scale,
                    ),
                    radius=2 * scale,
                    fill=PALETTE[series_index],
                )
            draw.text(
                ((x1 + row_index * group + group / 2) * scale, (plot_bottom + 7) * scale),
                _text(row.get(category), 8) if category else str(row_index + 1),
                font=small,
                fill=MUTED,
                anchor="ma",
            )


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
