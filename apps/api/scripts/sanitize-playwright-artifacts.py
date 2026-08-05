"""Redact test credentials from Playwright evidence and fail if any remain."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path

SECRET_MARKERS = ("PASSWORD", "TOKEN", "SECRET")


def _secrets() -> tuple[bytes, ...]:
    values = {
        value.encode("utf-8")
        for key, value in os.environ.items()
        if any(marker in key.upper() for marker in SECRET_MARKERS) and len(value) >= 8
    }
    return tuple(sorted(values, key=len, reverse=True))


def _redact(data: bytes, secrets: tuple[bytes, ...]) -> tuple[bytes, int]:
    replacements = 0
    for secret in secrets:
        count = data.count(secret)
        if count:
            data = data.replace(secret, b"[REDACTED]")
            replacements += count
    return data, replacements


def _sanitize_zip(path: Path, secrets: tuple[bytes, ...]) -> int:
    replacements = 0
    with (
        zipfile.ZipFile(path, "r") as source,
        tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=path.parent) as temporary,
    ):
        temporary_path = Path(temporary.name)
        with zipfile.ZipFile(temporary, "w") as target:
            for info in source.infolist():
                data, count = _redact(source.read(info.filename), secrets)
                replacements += count
                target.writestr(info, data)
    temporary_path.replace(path)
    return replacements


def _sanitize_file(path: Path, secrets: tuple[bytes, ...]) -> int:
    if path.suffix.lower() == ".zip":
        return _sanitize_zip(path, secrets)
    data = path.read_bytes()
    sanitized, replacements = _redact(data, secrets)
    if replacements:
        path.write_bytes(sanitized)
    return replacements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    secrets = _secrets()
    files: list[Path] = []
    for raw in args.path:
        path = Path(raw)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())

    replacements = sum(_sanitize_file(path, secrets) for path in files)
    findings: list[str] = []
    for path in files:
        data = path.read_bytes()
        if any(secret in data for secret in secrets):
            findings.append(str(path))

    report = {
        "schema_version": 1,
        "files_scanned": len(files),
        "secret_values_checked": len(secrets),
        "redactions": replacements,
        "findings": findings,
        "passed": not findings,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"files_scanned": len(files), "redactions": replacements, "findings": len(findings)}
        )
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
