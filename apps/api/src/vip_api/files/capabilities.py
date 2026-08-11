"""Server-authoritative file format capability contract.

Frontend upload controls, connector catalog copy, validation, and ingestion
adapters must derive support claims from this module — never from independent
guesses.
"""

from __future__ import annotations

from typing import Literal, TypedDict

FormatKey = Literal["csv", "tsv", "json", "xlsx", "xls", "parquet", "pdf", "png", "jpeg", "txt"]
IngestRole = Literal["upload_only", "tabular_ingest", "unsupported"]


class FormatCapability(TypedDict):
    supported: bool
    extensions: list[str]
    mime_types: list[str]
    role: IngestRole
    notes: str


# Upload allowlist + ingestion truth. Keep in sync with validation/_MIME_BY_EXTENSION
# and dataset ingestion adapters.
FORMAT_CAPABILITIES: dict[FormatKey, FormatCapability] = {
    "csv": {
        "supported": True,
        "extensions": [".csv"],
        "mime_types": ["text/csv"],
        "role": "tabular_ingest",
        "notes": ("UTF-8 CSV with header row; interactive ingest capped at 50,000 rows / 5 MB."),
    },
    "tsv": {
        "supported": True,
        "extensions": [".tsv"],
        "mime_types": ["text/tab-separated-values", "text/plain"],
        "role": "tabular_ingest",
        "notes": (
            "TSV is accepted by converting to CSV in the browser before ingest-csv, "
            "or by saving as CSV. Direct .tsv file upload is not on the binary allowlist."
        ),
    },
    "json": {
        "supported": True,
        "extensions": [".json"],
        "mime_types": ["application/json"],
        "role": "upload_only",
        "notes": "Governed file storage only; not registered as a tabular dataset via ingest-file.",
    },
    "xlsx": {
        "supported": True,
        "extensions": [".xlsx"],
        "mime_types": [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ],
        "role": "tabular_ingest",
        "notes": (
            "First worksheet is imported. Formula cells use cached calculated values "
            "(data_only); macros are never executed. Password-protected workbooks are rejected."
        ),
    },
    "xls": {
        "supported": False,
        "extensions": [".xls"],
        "mime_types": ["application/vnd.ms-excel"],
        "role": "unsupported",
        "notes": "Legacy BIFF .xls is not supported. Save as .xlsx or CSV UTF-8.",
    },
    "parquet": {
        "supported": False,
        "extensions": [".parquet"],
        "mime_types": ["application/vnd.apache.parquet", "application/octet-stream"],
        "role": "unsupported",
        "notes": "Parquet ingestion is a future enhancement and is not advertised.",
    },
    "pdf": {
        "supported": True,
        "extensions": [".pdf"],
        "mime_types": ["application/pdf"],
        "role": "upload_only",
        "notes": "Governed file storage only.",
    },
    "png": {
        "supported": True,
        "extensions": [".png"],
        "mime_types": ["image/png"],
        "role": "upload_only",
        "notes": "Governed file storage only.",
    },
    "jpeg": {
        "supported": True,
        "extensions": [".jpg", ".jpeg"],
        "mime_types": ["image/jpeg"],
        "role": "upload_only",
        "notes": "Governed file storage only.",
    },
    "txt": {
        "supported": True,
        "extensions": [".txt"],
        "mime_types": ["text/plain"],
        "role": "upload_only",
        "notes": "Governed file storage; Dataset UI may treat delimited .txt as CSV content.",
    },
}


def upload_allowed_extensions() -> list[str]:
    """Extensions accepted by POST /files (binary upload allowlist)."""
    extensions: list[str] = []
    for key, item in FORMAT_CAPABILITIES.items():
        if not item["supported"]:
            continue
        if key == "tsv":
            # TSV is browser-converted; not a direct binary upload type.
            continue
        extensions.extend(item["extensions"])
    return sorted(set(extensions))


def upload_allowed_mime_types() -> list[str]:
    mimes: list[str] = []
    for key, item in FORMAT_CAPABILITIES.items():
        if not item["supported"]:
            continue
        if key == "tsv":
            continue
        mimes.extend(item["mime_types"])
    return sorted(set(mimes))


def tabular_ingest_extensions() -> frozenset[str]:
    return frozenset(
        ext
        for key, item in FORMAT_CAPABILITIES.items()
        if item["supported"] and item["role"] == "tabular_ingest"
        for ext in item["extensions"]
        if key != "tsv"
    )


def local_file_catalog_description() -> str:
    tabular = [
        key.upper()
        for key, item in FORMAT_CAPABILITIES.items()
        if item["supported"] and item["role"] == "tabular_ingest" and key != "tsv"
    ]
    upload_only = [
        key.upper()
        for key, item in FORMAT_CAPABILITIES.items()
        if item["supported"] and item["role"] == "upload_only" and key in {"json"}
    ]
    parts = [*tabular, *upload_only]
    joined = "/".join(parts) if parts else "supported"
    return (
        f"Upload {joined} files directly from your device. "
        "Validated and malware-scanned server-side. "
        "Dataset registration supports CSV and XLSX (first sheet)."
    )


def capability_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "formats": FORMAT_CAPABILITIES,
        "upload_extensions": upload_allowed_extensions(),
        "upload_mime_types": upload_allowed_mime_types(),
        "tabular_ingest_extensions": sorted(tabular_ingest_extensions()),
        "local_file_description": local_file_catalog_description(),
    }
