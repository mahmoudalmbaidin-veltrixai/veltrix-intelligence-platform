"""Upload validation and filename hardening."""

from __future__ import annotations

import re
from pathlib import Path

from vip_api.core.errors import ApplicationError

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")
_MIME_BY_EXTENSION = {
    ".csv": {"text/csv"},
    ".json": {"application/json"},
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".txt": {"text/plain"},
}
_DISALLOWED_SIGNATURES = (
    b"MZ",  # Windows portable executable
    b"\x7fELF",  # Linux executable
    b"PK\x03\x04",  # ZIP/JAR/Office archive
    b"\xca\xfe\xba\xbe",  # Java class / Mach-O universal binary
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit, reverse byte order
)


def sanitize_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name.strip()
    name = _SAFE_NAME.sub("_", name)[:255]
    if not name or name in {".", ".."}:
        raise ApplicationError(
            code="INVALID_FILE_NAME", message="The file name is invalid.", status_code=422
        )
    return name


def validate_file_type(
    filename: str,
    mime_type: str,
    allowed_extensions: list[str],
    allowed_mime_types: list[str],
) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in {item.lower() for item in allowed_extensions}:
        raise ApplicationError(
            code="FILE_TYPE_NOT_ALLOWED",
            message="The file extension is not allowed.",
            status_code=415,
        )
    normalized_mime = mime_type.split(";", 1)[0].strip().lower()
    if normalized_mime not in {item.lower() for item in allowed_mime_types}:
        raise ApplicationError(
            code="FILE_TYPE_NOT_ALLOWED", message="The file type is not allowed.", status_code=415
        )
    expected_mimes = _MIME_BY_EXTENSION.get(extension)
    if expected_mimes is None or normalized_mime not in expected_mimes:
        raise ApplicationError(
            code="FILE_CONTENT_TYPE_MISMATCH",
            message="The file extension does not match its declared type.",
            status_code=415,
        )
    return extension


def inspect_signature(path: Path, mime_type: str) -> None:
    prefix = path.read_bytes()[:8]
    if any(prefix.startswith(signature) for signature in _DISALLOWED_SIGNATURES):
        raise ApplicationError(
            code="FILE_CONTENT_MISMATCH",
            message="The file content does not match its declared type.",
            status_code=422,
        )
    normalized_mime = mime_type.split(";", 1)[0].strip().lower()
    expected: dict[str, tuple[bytes, ...]] = {
        "application/pdf": (b"%PDF-",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/jpeg": (b"\xff\xd8\xff",),
    }
    signatures = expected.get(normalized_mime)
    if signatures and not any(prefix.startswith(signature) for signature in signatures):
        raise ApplicationError(
            code="FILE_CONTENT_MISMATCH",
            message="The file content does not match its declared type.",
            status_code=422,
        )
