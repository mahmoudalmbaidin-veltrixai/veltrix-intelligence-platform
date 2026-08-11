"""Unit coverage for governed XLSX validation and parsing (VIP-BUG-007)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from openpyxl import Workbook

from vip_api.core.errors import ApplicationError
from vip_api.files.capabilities import capability_contract, tabular_ingest_extensions
from vip_api.files.validation import inspect_signature, sanitize_filename, validate_file_type
from vip_api.files.xlsx import parse_xlsx
from vip_api.qa.certification_lifecycle import (
    CertificationFixtureRegistry,
    RegisteredResource,
    identify_likely_stale_names,
    new_run_id,
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _write_xlsx(path: Path, rows: list[list[object]], sheet: str = "Sheet1") -> Path:
    workbook = Workbook()
    active = workbook.active
    assert active is not None
    active.title = sheet
    for row in rows:
        active.append(row)
    workbook.save(path)
    return path


def test_capability_contract_advertises_xlsx_not_xls_or_parquet() -> None:
    contract = capability_contract()
    formats = cast(dict[str, dict[str, object]], contract["formats"])
    assert formats["xlsx"]["supported"] is True
    assert formats["xlsx"]["role"] == "tabular_ingest"
    assert formats["xls"]["supported"] is False
    assert formats["parquet"]["supported"] is False
    assert ".xlsx" in tabular_ingest_extensions()
    assert ".xls" not in tabular_ingest_extensions()
    assert "Excel" not in str(contract["local_file_description"]) or "XLSX" in str(
        contract["local_file_description"]
    )
    assert "XLSX" in str(contract["local_file_description"])


def test_xlsx_type_and_ooxml_signature_are_accepted(tmp_path: Path) -> None:
    path = _write_xlsx(tmp_path / "sales.xlsx", [["region", "amount"], ["East", 10]])
    assert (
        validate_file_type(
            "sales.xlsx",
            XLSX_MIME,
            [".xlsx", ".csv"],
            [XLSX_MIME, "text/csv"],
        )
        == ".xlsx"
    )
    inspect_signature(path, XLSX_MIME)


def test_random_zip_renamed_as_xlsx_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "fake.xlsx"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 64)
    with pytest.raises(ApplicationError) as error:
        inspect_signature(path, XLSX_MIME)
    assert error.value.code in {"XLSX_INVALID", "XLSX_CORRUPT", "FILE_CONTENT_MISMATCH"}


def test_non_xlsx_zip_payload_is_still_rejected(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 32)
    with pytest.raises(ApplicationError) as error:
        inspect_signature(path, "text/plain")
    assert error.value.code == "FILE_CONTENT_MISMATCH"


def test_parse_xlsx_handles_arabic_dates_nulls_and_duplicates(tmp_path: Path) -> None:
    path = _write_xlsx(
        tmp_path / "arabic.xlsx",
        [
            ["المنطقة", "amount", "amount", "", "active", "sold_on"],
            ["الرياض", 12.5, -3, None, True, "2024-01-15"],
            ["جدة", 0, None, "x", False, "2024-02-01"],
            [None, None, None, None, None, None],
        ],
    )
    headers, rows, sheet = parse_xlsx(path)
    assert sheet == "Sheet1"
    assert headers[0] == "المنطقة"
    assert "amount" in headers[1]
    assert headers[2].startswith("amount")
    assert headers[3].startswith("column_")
    assert len(rows) == 2
    assert rows[0][0] == "الرياض"
    assert rows[0][4] == "true"


def test_sanitize_filename_blocks_traversal() -> None:
    assert sanitize_filename("..\\evil.xlsx") == "evil.xlsx"


@pytest.mark.asyncio
async def test_certification_registry_cleanup_is_id_scoped(tmp_path: Path) -> None:
    registry = CertificationFixtureRegistry(environment_guard="test")
    assert registry.run_id.startswith("qa-cert-")
    name = registry.namespaced("dataset")
    registry.register("dataset", "11111111-1111-1111-1111-111111111111", name)
    registry.register(
        "file",
        "22222222-2222-2222-2222-222222222222",
        registry.namespaced("file"),
        retain=True,
    )
    deleted: list[str] = []

    async def delete_dataset(item: RegisteredResource) -> None:
        deleted.append(item.id)

    async def delete_file(item: RegisteredResource) -> None:
        deleted.append(item.id)

    report = await registry.cleanup({"dataset": delete_dataset, "file": delete_file})
    assert report.created == 2
    assert deleted == ["11111111-1111-1111-1111-111111111111"]
    assert len(report.retained) == 1
    assert report.failures == []
    registry.save(tmp_path / "registry.json")
    loaded = CertificationFixtureRegistry.load(tmp_path / "registry.json")
    assert loaded.run_id == registry.run_id


def test_stale_name_identifier_is_conservative() -> None:
    run = new_run_id()
    names = [
        f"{run}-sales",
        "B9.1B Disposable 123",
        "Production Revenue",
        "qa-phase1-e2e-pipeline",
    ]
    stale = identify_likely_stale_names(names)
    assert f"{run}-sales" in stale
    assert "B9.1B Disposable 123" in stale
    assert "Production Revenue" not in stale
