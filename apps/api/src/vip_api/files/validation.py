"""Upload validation and filename hardening."""

from __future__ import annotations

import re
import zipfile
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
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}
# Executables and generic archives. OOXML (.xlsx) is ZIP-based and validated
# separately via inspect_ooxml_workbook — it must not be blanket-rejected here.
_DISALLOWED_SIGNATURES = (
    b"MZ",  # Windows portable executable
    b"\x7fELF",  # Linux executable
    b"\xca\xfe\xba\xbe",  # Java class / Mach-O universal binary
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit, reverse byte order
)
_ZIP_SIGNATURE = b"PK\x03\x04"
_OOXML_REQUIRED_MEMBERS = ("[Content_Types].xml", "xl/workbook.xml")
_OOXML_ENCRYPTION_MARKERS = ("EncryptionInfo", "EncryptedPackage")


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


def inspect_ooxml_workbook(path: Path) -> None:
    """Validate that a ZIP container is an unencrypted XLSX workbook."""
    try:
        if not zipfile.is_zipfile(path):
            raise ApplicationError(
                code="FILE_CONTENT_MISMATCH",
                message="The file content does not match its declared type.",
                status_code=422,
            )
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if any(marker in names for marker in _OOXML_ENCRYPTION_MARKERS):
                raise ApplicationError(
                    code="XLSX_ENCRYPTED",
                    message="Password-protected Excel workbooks are not supported.",
                    status_code=422,
                )
            missing = [member for member in _OOXML_REQUIRED_MEMBERS if member not in names]
            if missing:
                raise ApplicationError(
                    code="XLSX_INVALID",
                    message="The Excel workbook is missing required package parts.",
                    status_code=422,
                )
            # Reject macros-enabled packages advertised as .xlsx.
            if any(name.startswith("xl/vbaProject") for name in names):
                raise ApplicationError(
                    code="XLSX_MACROS_FORBIDDEN",
                    message="Macro-enabled Excel workbooks are not supported.",
                    status_code=422,
                )
            bad = archive.testzip()
            if bad is not None:
                raise ApplicationError(
                    code="XLSX_CORRUPT",
                    message="The Excel workbook archive is corrupt.",
                    status_code=422,
                )
    except ApplicationError:
        raise
    except zipfile.BadZipFile as exc:
        raise ApplicationError(
            code="XLSX_CORRUPT",
            message="The Excel workbook archive is corrupt.",
            status_code=422,
        ) from exc


def inspect_signature(path: Path, mime_type: str) -> None:
    prefix = path.read_bytes()[:8]
    normalized_mime = mime_type.split(";", 1)[0].strip().lower()
    is_xlsx = normalized_mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    if any(prefix.startswith(signature) for signature in _DISALLOWED_SIGNATURES):
        raise ApplicationError(
            code="FILE_CONTENT_MISMATCH",
            message="The file content does not match its declared type.",
            status_code=422,
        )

    if prefix.startswith(_ZIP_SIGNATURE):
        if is_xlsx:
            inspect_ooxml_workbook(path)
            return
        raise ApplicationError(
            code="FILE_CONTENT_MISMATCH",
            message="The file content does not match its declared type.",
            status_code=422,
        )

    if is_xlsx:
        raise ApplicationError(
            code="FILE_CONTENT_MISMATCH",
            message="The file content does not match its declared type.",
            status_code=422,
        )

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
