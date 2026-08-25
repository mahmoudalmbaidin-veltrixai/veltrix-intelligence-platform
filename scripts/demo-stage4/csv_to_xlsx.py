"""Convert a UTF-8 CSV file to a deterministic single-sheet XLSX workbook.

The converter uses only Python's standard library so demo reset does not depend
on Excel, LibreOffice, or an unpinned workbook package.
"""

from __future__ import annotations

import csv
import re
import sys
import zipfile
from html import escape
from pathlib import Path

NUMERIC_COLUMNS = {"quantity", "metric_value", "metric_cost", "score", "cycle_hours"}
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def inline_cell(reference: str, value: str) -> str:
    preserve = ' xml:space="preserve"' if value != value.strip() else ""
    return f'<c r="{reference}" t="inlineStr"><is><t{preserve}>{escape(value)}</t></is></c>'


def numeric_cell(reference: str, value: str) -> str:
    if not re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", value):
        return inline_cell(reference, value)
    return f'<c r="{reference}"><v>{value}</v></c>'


def write_entry(archive: zipfile.ZipFile, name: str, content: str) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, content.encode("utf-8"))


def convert(source: Path, destination: Path) -> None:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise ValueError("The source CSV must include headers and at least one row.")

    headers = rows[0]
    sheet_rows: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells: list[str] = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{column_name(column_index)}{row_number}"
            header = headers[column_index - 1]
            if row_number > 1 and header in NUMERIC_COLUMNS and value:
                cells.append(numeric_cell(reference, value))
            elif value:
                cells.append(inline_cell(reference, value))
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    dimension = f"A1:{column_name(len(headers))}{len(rows)}"
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/><sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w") as archive:
        write_entry(archive, "[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        write_entry(archive, "_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        write_entry(archive, "xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Synthetic Data" sheetId="1" r:id="rId1"/></sheets></workbook>')
        write_entry(archive, "xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        write_entry(archive, "xl/styles.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>')
        write_entry(archive, "xl/worksheets/sheet1.xml", sheet_xml)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: csv_to_xlsx.py INPUT.csv OUTPUT.xlsx")
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
