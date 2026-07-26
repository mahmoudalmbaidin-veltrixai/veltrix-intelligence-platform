"""Storage provider contract and path-safe local implementation."""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Protocol


class StorageProvider(Protocol):
    name: str

    async def put(self, source: Path, key: str) -> None: ...
    def stream(self, key: str, chunk_size: int) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...


class StorageProviderError(Exception):
    pass


class LocalStorageProvider:
    name = "local"

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self._root / key).resolve()
        if self._root not in candidate.parents:
            raise StorageProviderError("Invalid storage key")
        return candidate

    async def put(self, source: Path, key: str) -> None:
        destination = self._path(key)
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.part")

        def copy_atomically() -> None:
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
            source.unlink()

        await asyncio.to_thread(copy_atomically)

    async def _stream(self, key: str, chunk_size: int) -> AsyncIterator[bytes]:
        path = self._path(key)
        if not await asyncio.to_thread(path.is_file):
            raise StorageProviderError("Stored object is unavailable")
        handle = await asyncio.to_thread(path.open, "rb")
        try:
            while chunk := await asyncio.to_thread(handle.read, chunk_size):
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

    def stream(self, key: str, chunk_size: int) -> AsyncIterator[bytes]:
        return self._stream(key, chunk_size)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).is_file)


StorageFactory = Callable[[str], StorageProvider]
_PROVIDER_FACTORIES: dict[str, StorageFactory] = {"local": LocalStorageProvider}


def register_storage_provider(name: str, factory: StorageFactory) -> None:
    """Register S3, Azure Blob, GCS, or MinIO adapters at application composition time."""
    if name in _PROVIDER_FACTORIES:
        raise StorageProviderError(f"Storage provider is already registered: {name}")
    _PROVIDER_FACTORIES[name] = factory


def storage_provider(name: str, root: str) -> StorageProvider:
    try:
        return _PROVIDER_FACTORIES[name](root)
    except KeyError as exc:
        raise StorageProviderError("The configured storage provider is unavailable") from exc
