"""Credential-redaction regression coverage for Playwright artifacts."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from uuid import uuid4

from pytest import MonkeyPatch


def test_artifact_sanitizer_redacts_plain_files_and_trace_archives(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    secret = f"ephemeral-{uuid4().hex}"
    artifact_dir = tmp_path / "test-results"
    artifact_dir.mkdir()
    context = artifact_dir / "error-context.md"
    context.write_text(f"password={secret}\n", encoding="utf-8")
    trace = artifact_dir / "trace.zip"
    with zipfile.ZipFile(trace, "w") as archive:
        archive.writestr("trace.network", f'{{"entered":"{secret}"}}')

    report = tmp_path / "artifact-secret-scan.json"
    script = Path(__file__).parents[2] / "scripts" / "sanitize-playwright-artifacts.py"
    spec = importlib.util.spec_from_file_location("artifact_sanitizer_under_test", script)
    assert spec is not None and spec.loader is not None
    sanitizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sanitizer)
    monkeypatch.setenv("VIP_E2E_PASSWORD", secret)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--path",
            str(artifact_dir),
            "--report",
            str(report),
        ],
    )

    assert sanitizer.main() == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["redactions"] == 2
    assert payload["findings"] == []
    assert secret not in context.read_text(encoding="utf-8")
    with zipfile.ZipFile(trace) as archive:
        assert secret.encode() not in archive.read("trace.network")
    assert secret not in report.read_text(encoding="utf-8")
