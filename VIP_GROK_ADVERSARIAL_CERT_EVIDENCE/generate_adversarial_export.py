"""Independent adversarial pivot PDF/PNG generation against the frozen SHA renderer."""

from __future__ import annotations

import base64
import json
import re
import zlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vip_api.dashboard_delivery.rendering import PdfDashboardRenderer, PngDashboardRenderer, RenderDocument

EV = Path(__file__).resolve().parent / "exports"
OLD = Path(r"C:\Users\MahmoudAlmbaidin\Downloads\VIP\VIP_FINAL_RECERTIFICATION_V2_EVIDENCE\exports")
EV.mkdir(parents=True, exist_ok=True)

ALPHA = "Quarter — Enterprise Strategic Revenue Forecast Scenario Alpha"
BETA = "Quarter — Enterprise Strategic Revenue Forecast Scenario Beta"
ROW = "Enterprise Strategic Revenue Forecast Scenario Omega — very long row label"


def inspect_bytes(data: bytes, name: str) -> dict[str, object]:
    return {
        "name": name,
        "bytes": len(data),
        "magic": data[:8].decode("latin-1", "replace"),
        "lang": b"/Lang" in data,
        "markinfo": b"/MarkInfo" in data,
        "struct": b"/StructTreeRoot" in data,
        "th": b"/TH" in data,
        "td": b"/TD" in data,
    }


def pdf_text(content: bytes) -> str:
    tokens: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        value = match.group(1).strip()
        try:
            if value.endswith(b"~>"):
                value = base64.a85decode(value, adobe=True)
            stream = zlib.decompress(value).decode("latin-1")
        except (ValueError, zlib.error):
            continue
        tokens.extend(re.findall(r"\((?:[^()\\]|\\.)*\)", stream))
    return " ".join(token[1:-1] for token in tokens)


def document_for(widget: dict[str, object], columns: list[dict[str, object]], rows: list[dict[str, object]]) -> RenderDocument:
    return RenderDocument(
        dashboard_id=uuid4(),
        dashboard_version_id=uuid4(),
        dashboard_version=1,
        organization_id=uuid4(),
        workspace_id=uuid4(),
        generated_at=datetime.now(UTC),
        dashboard_name="Grok adversarial pivot",
        snapshot={
            "dashboard": {"name": "Grok adversarial pivot"},
            "pages": [{"id": str(uuid4()), "name": "01 pivot", "position": 0, "widgets": [widget]}],
            "filters": [],
        },
        widget_results={
            str(widget["id"]): {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": False,
            }
        },
        filters={},
        locale="en-US",
        timezone="Asia/Riyadh",
    )


def main() -> None:
    reports: list[dict[str, object]] = []
    for path in (
        OLD / "all-20-widgets.pdf",
        OLD / "pivot-long-label" / "pivot-long-label.pdf",
        OLD / "semantic-parity" / "all-widget-direct-renderer.pdf",
    ):
        if path.exists():
            reports.append(inspect_bytes(path.read_bytes(), path.name))

    widget: dict[str, object] = {
        "id": str(uuid4()),
        "type": "pivot",
        "title": "Adversarial pivot",
        "description": "",
        "semantic_model_id": str(uuid4()),
        "hidden": False,
        "layout": {"x": 0, "y": 0, "w": 12, "h": 8},
        "query": {"dimensions": ["region", "quarter"], "metrics": ["revenue"]},
        "config": {"number_style": "plain", "decimals": 0},
        "content": None,
    }
    columns = [
        {"key": "region", "label": "Region", "data_type": "string", "role": "dimension"},
        {"key": "quarter", "label": "Quarter", "data_type": "string", "role": "dimension"},
        {"key": "revenue", "label": "Revenue", "data_type": "integer", "role": "metric"},
    ]
    rows = [
        {"region": ROW, "quarter": ALPHA, "revenue": 111},
        {"region": ROW, "quarter": BETA, "revenue": 222},
        {"region": ROW + " B", "quarter": ALPHA, "revenue": None},
        {"region": ROW + " B", "quarter": BETA, "revenue": 444},
    ]
    doc = document_for(widget, columns, rows)
    pdf = PdfDashboardRenderer().render(doc)
    png = PngDashboardRenderer().render(doc)
    (EV / "grok-adversarial-pivot.pdf").write_bytes(pdf.content)
    (EV / "grok-adversarial-pivot.png").write_bytes(png.content)
    reports.append(inspect_bytes(pdf.content, "grok-adversarial-pivot.pdf"))
    reports.append(
        {
            "name": "grok-adversarial-pivot.png",
            "bytes": len(png.content),
            "magic": png.content[:8].hex(),
            "png_sig": png.content[:8] == b"\x89PNG\r\n\x1a\n",
        }
    )
    text = pdf_text(pdf.content)
    sem = {
        "alpha_in_pdf": "Alpha" in text,
        "beta_in_pdf": "Beta" in text,
        "omega_in_pdf": "Omega" in text,
        "111_in_pdf": "111" in text,
        "222_in_pdf": "222" in text,
        "444_in_pdf": "444" in text,
        "alpha_and_beta_distinct": ("Alpha" in text and "Beta" in text),
        "text_sample": text[:1200],
    }
    payload = {"files": reports, "adversarial_semantics": sem}
    (EV / "pdf-inspection.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2)[:5000])


if __name__ == "__main__":
    main()
