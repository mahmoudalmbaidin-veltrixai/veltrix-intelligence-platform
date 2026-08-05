"""Redact test credentials from Playwright evidence and fail if any remain."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

SECRET_MARKERS = ("PASSWORD", "TOKEN", "SECRET")
REDACTED = "[REDACTED]"
SENSITIVE_NAME = (
    r"(?:authorization|proxy-authorization|cookie|set-cookie|"
    r"vip_access_session|vip_refresh_session|vip_csrf_token|"
    r"access[_-]?token|refresh[_-]?token|csrf[_-]?token|session[_-]?(?:id|token)|"
    r"password|client[_-]?secret|api[_-]?key)"
)

# Playwright traces contain JSONL, embedded request/response headers, storage
# state and HTML/Markdown context. These patterns deliberately key on sensitive
# names rather than token shape, so a newly issued opaque cookie is covered even
# though its value was never present in the process environment.
STRUCTURAL_PATTERNS = (
    re.compile(rf'(?i)(["\']?{SENSITIVE_NAME}["\']?\s*:\s*["\'])(.*?)(["\'])'),
    re.compile(rf"(?im)^(\s*{SENSITIVE_NAME}\s*:\s*)([^\r\n]+)()"),
    re.compile(rf"(?i)({SENSITIVE_NAME}\s*=\s*)([^;\s\"\']+)()"),
    re.compile(rf'(?i)([?&]{SENSITIVE_NAME}=)([^&#\s"\']+)()'),
    re.compile(
        rf'(?is)(["\']name["\']\s*:\s*["\']{SENSITIVE_NAME}["\']\s*,\s*'
        rf'["\']value["\']\s*:\s*["\'])(.*?)(["\'])'
    ),
    re.compile(
        rf'(?is)(["\']value["\']\s*:\s*["\'])(.*?)(["\']\s*,\s*'
        rf'["\']name["\']\s*:\s*["\']{SENSITIVE_NAME}["\'])'
    ),
)


def _secrets() -> tuple[bytes, ...]:
    values = {
        value.encode("utf-8")
        for key, value in os.environ.items()
        if any(marker in key.upper() for marker in SECRET_MARKERS) and len(value) >= 8
    }
    return tuple(sorted(values, key=len, reverse=True))


def _redact_exact(data: bytes, secrets: tuple[bytes, ...]) -> tuple[bytes, int]:
    replacements = 0
    for secret in secrets:
        count = data.count(secret)
        if count:
            data = data.replace(secret, REDACTED.encode())
            replacements += count
    return data, replacements


def _redact_structural(data: bytes) -> tuple[bytes, int]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, 0
    replacements = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replacements
        if match.group(2) == REDACTED:
            return match.group(0)
        replacements += 1
        return f"{match.group(1)}{REDACTED}{match.group(3)}"

    for pattern in STRUCTURAL_PATTERNS:
        text = pattern.sub(replace, text)
    return text.encode("utf-8"), replacements


def _redact(data: bytes, secrets: tuple[bytes, ...]) -> tuple[bytes, int, int]:
    data, exact = _redact_exact(data, secrets)
    data, structural = _redact_structural(data)
    return data, exact, structural


def _sanitize_zip(path: Path, secrets: tuple[bytes, ...]) -> tuple[int, int]:
    exact_replacements = 0
    structural_replacements = 0
    with (
        zipfile.ZipFile(path, "r") as source,
        tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=path.parent) as temporary,
    ):
        temporary_path = Path(temporary.name)
        with zipfile.ZipFile(temporary, "w") as target:
            for info in source.infolist():
                data, exact, structural = _redact(source.read(info.filename), secrets)
                exact_replacements += exact
                structural_replacements += structural
                target.writestr(info, data)
    temporary_path.replace(path)
    return exact_replacements, structural_replacements


def _sanitize_file(path: Path, secrets: tuple[bytes, ...]) -> tuple[int, int]:
    if path.suffix.lower() == ".zip":
        return _sanitize_zip(path, secrets)
    data = path.read_bytes()
    sanitized, exact, structural = _redact(data, secrets)
    if exact or structural:
        path.write_bytes(sanitized)
    return exact, structural


def _findings(path: Path, secrets: tuple[bytes, ...]) -> bool:
    def contains(data: bytes) -> bool:
        if any(secret in data for secret in secrets):
            return True
        _, structural = _redact_structural(data)
        return structural > 0

    if path.suffix.lower() != ".zip":
        return contains(path.read_bytes())
    with zipfile.ZipFile(path, "r") as archive:
        return any(contains(archive.read(item.filename)) for item in archive.infolist())


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

    counts = [_sanitize_file(path, secrets) for path in files]
    exact_replacements = sum(item[0] for item in counts)
    structural_replacements = sum(item[1] for item in counts)
    findings = [str(path) for path in files if _findings(path, secrets)]

    report = {
        "schema_version": 1,
        "files_scanned": len(files),
        "secret_values_checked": len(secrets),
        "redactions": exact_replacements + structural_replacements,
        "exact_redactions": exact_replacements,
        "structural_redactions": structural_replacements,
        "findings": findings,
        "passed": not findings,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "files_scanned": len(files),
                "redactions": exact_replacements + structural_replacements,
                "findings": len(findings),
            }
        )
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
