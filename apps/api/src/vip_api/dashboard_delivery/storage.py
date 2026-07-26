"""Tenant-safe artifact storage provider abstraction."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError

_KEY = re.compile(r"^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.[a-z0-9]{2,8}$")


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    key: str
    size_bytes: int


class ArtifactStorage(Protocol):
    async def put(self, key: str, content: bytes) -> StoredArtifact: ...
    async def read(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class FileArtifactStorage:
    """Atomic local storage for development and single-node deployments."""

    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.DASHBOARD_ARTIFACT_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def key(self, organization_id: UUID, workspace_id: UUID, export_id: UUID, ext: str) -> str:
        return f"{organization_id}/{workspace_id}/{export_id}.{ext}"

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise ApplicationError(
                code="DASHBOARD_ARTIFACT_NOT_FOUND",
                message="The requested artifact is unavailable.",
                status_code=404,
            )
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ApplicationError(
                code="DASHBOARD_ARTIFACT_NOT_FOUND",
                message="The requested artifact is unavailable.",
                status_code=404,
            )
        return path

    async def put(self, key: str, content: bytes) -> StoredArtifact:
        path = self._path(key)
        await asyncio.to_thread(self._write_atomic, path, content)
        return StoredArtifact(key=key, size_bytes=len(content))

    @staticmethod
    def _write_atomic(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, path)

    async def read(self, key: str) -> bytes:
        try:
            return await asyncio.to_thread(self._path(key).read_bytes)
        except FileNotFoundError as exc:
            raise ApplicationError(
                code="DASHBOARD_ARTIFACT_NOT_FOUND",
                message="The requested artifact is unavailable.",
                status_code=404,
            ) from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, missing_ok=True)
