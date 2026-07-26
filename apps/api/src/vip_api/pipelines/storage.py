"""Tenant-bound filesystem artifact provider and temporary signed tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from pathlib import Path
from time import time
from uuid import UUID

from redis.asyncio import Redis

_KEY = re.compile(r"^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.(csv|json)$")


class ArtifactStorageError(RuntimeError):
    pass


class PipelineArtifactStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise ArtifactStorageError("Invalid artifact key")
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ArtifactStorageError("Invalid artifact location")
        return path

    def write(self, key: str, content: bytes) -> tuple[int, str]:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        return len(content), hashlib.sha256(content).hexdigest()

    def path(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise ArtifactStorageError("Artifact unavailable")
        return path

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


@dataclass(frozen=True, slots=True)
class DownloadClaims:
    artifact_id: UUID
    organization_id: UUID
    workspace_id: UUID
    user_id: UUID


class DownloadTokens:
    def __init__(self, key: str, ttl: int) -> None:
        self.key = key.encode()
        self.ttl = ttl

    def create(self, claims: DownloadClaims) -> str:
        body = {
            "a": str(claims.artifact_id),
            "o": str(claims.organization_id),
            "w": str(claims.workspace_id),
            "u": str(claims.user_id),
            "e": int(time()) + self.ttl,
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        sig = hmac.new(self.key, raw, hashlib.sha256).digest()
        return (
            base64.urlsafe_b64encode(raw).decode().rstrip("=")
            + "."
            + base64.urlsafe_b64encode(sig).decode().rstrip("=")
        )

    def verify(self, token: str) -> DownloadClaims:
        try:
            encoded, signature = token.split(".", 1)
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
            if not hmac.compare_digest(supplied, hmac.new(self.key, raw, hashlib.sha256).digest()):
                raise ValueError
            data = json.loads(raw)
            if int(data["e"]) < int(time()):
                raise ValueError
            return DownloadClaims(
                UUID(data["a"]), UUID(data["o"]), UUID(data["w"]), UUID(data["u"])
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ArtifactStorageError("Invalid or expired download token") from exc

    async def consume(self, token: str, redis: Redis, key_prefix: str) -> DownloadClaims:
        """Verify and atomically claim a tenant-bound token exactly once."""
        claims = self.verify(token)
        digest = hashlib.sha256(token.encode()).hexdigest()
        key = (
            f"{key_prefix}:download:pipeline:"
            f"{claims.organization_id}:{claims.workspace_id}:{digest}"
        )
        if not await redis.set(key, "used", ex=self.ttl + 1, nx=True):
            raise ArtifactStorageError("Invalid or expired download token")
        return claims
