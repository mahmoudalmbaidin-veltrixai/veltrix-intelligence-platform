"""Public file platform schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FileResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str | None
    kind: str
    status: str
    tags: list[str]
    current_version: int
    created_at: datetime
    updated_at: datetime


class FileList(BaseModel):
    items: list[FileResponse]
    next_cursor: datetime | None = None


class DownloadLink(BaseModel):
    url: str
    expires_at: datetime
    single_use: bool = True


class FileVersionResponse(BaseModel):
    version: int
    size_bytes: int
    sha256: str
    mime_type: str
    scan_status: str
    created_at: datetime


class FileTagsUpdate(BaseModel):
    tags: list[str] = Field(max_length=50)
