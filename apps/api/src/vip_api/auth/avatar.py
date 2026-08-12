"""Self-service user avatar storage.

Reuses the governed file validators (extension + declared-MIME allowlist +
magic-byte signature inspection) and the configured storage provider, scoped to
a single user key so avatars can never collide across users or tenants. Only
PNG and JPEG are accepted — the formats the platform's signature inspector can
actually verify — so no unvalidated image type is ever written.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from vip_api.auth.models import User
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.files.storage import StorageProviderError, storage_provider
from vip_api.files.validation import inspect_signature, sanitize_filename, validate_file_type

AVATAR_MAX_BYTES = 5 * 1024 * 1024
_ALLOWED_EXTENSIONS = [".png", ".jpg", ".jpeg"]
_ALLOWED_MIME_TYPES = ["image/png", "image/jpeg"]
_CHUNK = 64 * 1024
_AVATAR_URL = "/api/v1/auth/me/avatar"


def _key(user_id: UUID) -> str:
    return f"avatars/{user_id}"


def _provider(settings: Settings) -> object:
    return storage_provider(settings.FILE_STORAGE_PROVIDER, settings.FILE_STORAGE_ROOT)


async def store_avatar(
    stream: AsyncIterator[bytes],
    filename: str,
    content_type: str,
    user: User,
    settings: Settings,
) -> str:
    """Validate and persist an uploaded avatar; return the served avatar URL.

    ``stream`` is the raw request body (the platform parses uploads by streaming,
    not multipart), ``filename``/``content_type`` come from the X-File-Name and
    Content-Type headers.
    """
    safe_name = sanitize_filename(filename or "avatar.png")
    declared_mime = (content_type or "").split(";", 1)[0].strip().lower()
    validate_file_type(safe_name, declared_mime, _ALLOWED_EXTENSIONS, _ALLOWED_MIME_TYPES)

    limit = min(AVATAR_MAX_BYTES, settings.FILE_MAX_UPLOAD_BYTES)
    handle_fd, temp_name = tempfile.mkstemp(prefix="vip-avatar-")
    temp_path = Path(temp_name)
    written = 0
    try:
        with os.fdopen(handle_fd, "wb") as sink:
            async for chunk in stream:
                written += len(chunk)
                if written > limit:
                    raise ApplicationError(
                        code="FILE_TOO_LARGE",
                        message="The image exceeds the maximum avatar size.",
                        status_code=413,
                    )
                sink.write(chunk)
        if written == 0:
            raise ApplicationError(
                code="EMPTY_FILE", message="The uploaded image is empty.", status_code=422
            )
        # Magic-byte inspection defeats a mislabeled or disguised payload whose
        # declared MIME passed the allowlist above.
        inspect_signature(temp_path, declared_mime)
        provider = _provider(settings)
        await provider.put(temp_path, _key(user.id))  # type: ignore[attr-defined]
    finally:
        await asyncio.to_thread(_remove_if_exists, temp_path)
    user.avatar_url = _AVATAR_URL
    return _AVATAR_URL


def _remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


async def read_avatar(user: User, settings: Settings) -> tuple[AsyncIterator[bytes], str] | None:
    """Return (byte stream, content-type) for the user's avatar, or None."""
    if not user.avatar_url:
        return None
    provider = _provider(settings)
    try:
        exists = await provider.exists(_key(user.id))  # type: ignore[attr-defined]
    except StorageProviderError:
        return None
    if not exists:
        return None
    stream = provider.stream(_key(user.id), _CHUNK)  # type: ignore[attr-defined]
    content_type, chained = await _detect_and_chain(stream)
    return chained, content_type


async def _detect_and_chain(stream: AsyncIterator[bytes]) -> tuple[str, AsyncIterator[bytes]]:
    iterator = stream.__aiter__()
    first = b""
    try:
        first = await iterator.__anext__()
    except StopAsyncIteration:
        first = b""
    content_type = "image/png" if first.startswith(b"\x89PNG") else "image/jpeg"

    async def chained() -> AsyncIterator[bytes]:
        if first:
            yield first
        async for part in iterator:
            yield part

    return content_type, chained()


async def delete_avatar(user: User, settings: Settings) -> bool:
    """Remove the user's stored avatar and clear the reference. Idempotent."""
    had = bool(user.avatar_url)
    provider = _provider(settings)
    with contextlib.suppress(StorageProviderError):
        await provider.delete(_key(user.id))  # type: ignore[attr-defined]
    user.avatar_url = None
    return had
