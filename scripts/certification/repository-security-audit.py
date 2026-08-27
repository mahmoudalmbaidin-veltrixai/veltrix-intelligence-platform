"""Scan the VIP worktree and Git object history without printing secret values.

The scanner intentionally reports only detector names and locations. It is a
repository hygiene gate, not a substitute for a managed secret-scanning service.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import zipfile
from collections.abc import Iterable
from pathlib import Path
from xml.etree import ElementTree


MAX_FILE_BYTES = 8 * 1024 * 1024
TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".css",
    ".csv",
    ".env",
    ".example",
    ".hcl",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".lock",
    ".md",
    ".mjs",
    ".py",
    ".ps1",
    ".scss",
    ".sh",
    ".sql",
    ".tf",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {"Dockerfile", "Makefile"}
SENSITIVE_NAME_PATTERN = re.compile(
    r"(?i)(credential|password|passwd|secret|token|private[-_ ]?key|"
    r"access[-_ ]?register|database[-_ ]?(?:dump|backup))"
)
PLACEHOLDER_PATTERN = re.compile(
    r"(?i)^(?:$|change[-_ ]?me|replace[-_ ]?me|example|placeholder|your[-_ ].*|"
    r"<.*>|\$\{.*\}|\$\(.*\)|\$\{\{.*\}\}|none|null|false|true|"
    r"test(?:[-_ ].*)?|dev(?:elopment)?(?:[-_ ].*)?|\*+|\[redacted\])$"
)


DETECTORS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "private_key_block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
        "high",
    ),
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "high"),
    (
        "github_token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        "high",
    ),
    (
        "vendor_token",
        re.compile(
            r"\b(?:re_[A-Za-z0-9_-]{16,}|rk_live_[A-Za-z0-9]{16,}|"
            r"sk_live_[A-Za-z0-9]{16,}|xox[baprs]-[A-Za-z0-9-]{10,})\b"
        ),
        "high",
    ),
    (
        "jwt_token",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
            r"[A-Za-z0-9_-]{10,}\b"
        ),
        "high",
    ),
    (
        "credential_uri",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|redis|rediss|mysql|amqp|amqps|smtp)://"
            r"[^\s/:]+:[^\s/@]+@"
        ),
        "review",
    ),
)
GENERIC_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key)\b\s*[:=]\s*['\"]?([^'\"\s,;#}\)]+)"
)


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def looks_like_text(path: str, data: bytes) -> bool:
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    return (name in TEXT_NAMES or suffix in TEXT_SUFFIXES or name.startswith(".env")) and b"\0" not in data


def xlsx_text(data: bytes) -> str:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return ""
    values: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if not name.endswith(".xml") or not (
                name == "xl/sharedStrings.xml" or name.startswith("xl/worksheets/")
            ):
                continue
            try:
                root = ElementTree.fromstring(archive.read(name))
            except ElementTree.ParseError:
                continue
            values.extend(node.text or "" for node in root.findall(".//{*}t"))
            for cell in root.findall(".//{*}c[@t='str']"):
                value = cell.find("{*}v")
                if value is not None and value.text:
                    values.append(value.text)
    return "\n".join(values)


def scan_text(text: str, path: str, source: str, object_id: str | None = None) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    lines = text.splitlines() or [text]
    for line_number, line in enumerate(lines, start=1):
        for detector, pattern, severity in DETECTORS:
            if not pattern.search(line):
                continue
            effective_severity = severity
            if detector == "credential_uri" and re.search(
                r"(?i)@(localhost|127\.0\.0\.1|postgres|mysql)(?::|/)", line
            ):
                effective_severity = "development_fixture"
            finding: dict[str, object] = {
                "source": source,
                "path": path,
                "line": line_number,
                "detector": detector,
                "severity": effective_severity,
            }
            if object_id:
                finding["object_id"] = object_id
            findings.append(finding)
        for match in GENERIC_ASSIGNMENT.finditer(line):
            value = match.group(2).strip()
            if PLACEHOLDER_PATTERN.match(value):
                continue
            finding = {
                "source": source,
                "path": path,
                "line": line_number,
                "detector": "literal_secret_assignment",
                "severity": "review",
            }
            if object_id:
                finding["object_id"] = object_id
            findings.append(finding)
    return findings


def worktree_files() -> list[str]:
    output = git("ls-files", "--cached", "--others", "--exclude-standard").decode()
    return sorted(set(line for line in output.splitlines() if line))


def scan_worktree() -> tuple[list[dict[str, object]], list[str], int]:
    findings: list[dict[str, object]] = []
    sensitive_names: list[str] = []
    scanned = 0
    for relative in worktree_files():
        path = Path(relative)
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            continue
        if SENSITIVE_NAME_PATTERN.search(relative):
            sensitive_names.append(relative)
        data = path.read_bytes()
        text = xlsx_text(data) if path.suffix.lower() == ".xlsx" else ""
        if not text and looks_like_text(relative, data):
            text = data.decode("utf-8", errors="ignore")
        if not text:
            continue
        scanned += 1
        findings.extend(scan_text(text, relative, "worktree"))
    return findings, sorted(set(sensitive_names)), scanned


def history_objects() -> tuple[dict[str, str], list[str]]:
    object_paths: dict[str, str] = {}
    for line in git("rev-list", "--objects", "--all").decode(errors="replace").splitlines():
        object_id, _, path = line.partition(" ")
        if path and object_id not in object_paths:
            object_paths[object_id] = path
    request = "".join(f"{object_id}\n" for object_id in object_paths).encode()
    checked = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", input_bytes=request)
    blob_ids: list[str] = []
    for line in checked.decode().splitlines():
        object_id, object_type, size = line.split()
        if object_type == "blob" and int(size) <= MAX_FILE_BYTES:
            blob_ids.append(object_id)
    return object_paths, blob_ids


def iter_blob_data(blob_ids: Iterable[str]) -> Iterable[tuple[str, bytes]]:
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None and process.stdout is not None
    for expected_id in blob_ids:
        process.stdin.write(f"{expected_id}\n".encode())
        process.stdin.flush()
        header = process.stdout.readline().decode().strip().split()
        if len(header) != 3 or header[0] != expected_id or header[1] != "blob":
            raise RuntimeError(f"Unexpected git cat-file response for {expected_id}")
        size = int(header[2])
        data = process.stdout.read(size)
        process.stdout.read(1)
        yield expected_id, data
    process.stdin.close()
    if process.wait() != 0:
        stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
        raise RuntimeError(f"git cat-file failed: {stderr}")


def scan_history() -> tuple[list[dict[str, object]], list[str], int]:
    object_paths, blob_ids = history_objects()
    findings: list[dict[str, object]] = []
    sensitive_names: list[str] = []
    scanned = 0
    for object_id, data in iter_blob_data(blob_ids):
        path = object_paths[object_id]
        if SENSITIVE_NAME_PATTERN.search(path):
            sensitive_names.append(path)
        text = xlsx_text(data) if Path(path).suffix.lower() == ".xlsx" else ""
        if not text and looks_like_text(path, data):
            text = data.decode("utf-8", errors="ignore")
        if not text:
            continue
        scanned += 1
        findings.extend(scan_text(text, path, "history", object_id))
    return findings, sorted(set(sensitive_names)), scanned


def summarize(findings: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        key = str(finding["severity"])
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("worktree", "history", "all"), default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report: dict[str, object] = {
        "schema_version": 1,
        "scanner": "vip-redacted-repository-security-audit",
        "limitations": [
            "Pattern-based scanner; validate findings manually and use GitHub secret scanning when available.",
            "The report never stores matched values.",
        ],
    }
    combined: list[dict[str, object]] = []
    if args.scope in {"worktree", "all"}:
        findings, names, scanned = scan_worktree()
        report["worktree"] = {
            "files_scanned": scanned,
            "sensitive_filename_candidates": names,
            "findings": findings,
            "severity_counts": summarize(findings),
        }
        combined.extend(findings)
    if args.scope in {"history", "all"}:
        findings, names, scanned = scan_history()
        report["history"] = {
            "unique_blobs_scanned": scanned,
            "sensitive_filename_candidates": names,
            "findings": findings,
            "severity_counts": summarize(findings),
        }
        combined.extend(findings)
    report["high_risk_findings"] = sum(f["severity"] == "high" for f in combined)
    report["passed_high_confidence_gate"] = report["high_risk_findings"] == 0

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if report["passed_high_confidence_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
