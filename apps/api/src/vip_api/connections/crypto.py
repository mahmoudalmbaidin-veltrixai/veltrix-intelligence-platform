"""Authenticated encryption and externally supplied key abstractions."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vip_api.core.config import Settings


class SecretDecryptionError(RuntimeError):
    """Safe internal signal for authentication-tag or key failures."""


@dataclass(frozen=True, slots=True)
class EncryptionKey:
    version: str
    material: bytes


class EncryptionKeyProvider(Protocol):
    async def get_active_key(self) -> EncryptionKey: ...
    async def get_key(self, key_version: str) -> EncryptionKey: ...


class EnvironmentEncryptionKeyProvider:
    def __init__(self, settings: Settings) -> None:
        encoded = settings.connection_encryption_key
        if not encoded:
            raise RuntimeError("Connection encryption key is not configured")
        try:
            material = base64.urlsafe_b64decode(encoded.encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("Connection encryption key is invalid") from exc
        if len(material) != 32:
            raise RuntimeError("Connection encryption key must decode to 32 bytes")
        self._key = EncryptionKey(settings.CONNECTION_ENCRYPTION_KEY_VERSION, material)

    async def get_active_key(self) -> EncryptionKey:
        return self._key

    async def get_key(self, key_version: str) -> EncryptionKey:
        if key_version != self._key.version:
            raise SecretDecryptionError("Encryption key version is unavailable")
        return self._key


class TestEncryptionKeyProvider:
    """Deterministic provider intended only for isolated tests."""

    __test__ = False

    def __init__(self, material: bytes = b"T" * 32, version: str = "test-v1") -> None:
        if len(material) != 32:
            raise ValueError("Test key must be 32 bytes")
        self._key = EncryptionKey(version, material)

    async def get_active_key(self) -> EncryptionKey:
        return self._key

    async def get_key(self, key_version: str) -> EncryptionKey:
        if key_version != self._key.version:
            raise SecretDecryptionError("Encryption key version is unavailable")
        return self._key


def associated_data(
    organization_id: object,
    workspace_id: object,
    secret_id: object,
    provider: str,
    credential_version: int,
) -> bytes:
    return "|".join(
        (str(organization_id), str(workspace_id), str(secret_id), provider, str(credential_version))
    ).encode()


async def encrypt_json(
    value: dict[str, str], aad: bytes, key_provider: EncryptionKeyProvider
) -> tuple[bytes, bytes, str]:
    key = await key_provider.get_active_key()
    nonce = os.urandom(12)
    plaintext = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return AESGCM(key.material).encrypt(nonce, plaintext, aad), nonce, key.version


async def decrypt_json(
    ciphertext: bytes,
    nonce: bytes,
    aad: bytes,
    key_version: str,
    key_provider: EncryptionKeyProvider,
) -> dict[str, str]:
    try:
        key = await key_provider.get_key(key_version)
        plaintext = AESGCM(key.material).decrypt(nonce, ciphertext, aad)
        decoded = json.loads(plaintext)
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in decoded.items()
        ):
            raise SecretDecryptionError("Secret payload is invalid")
        return decoded
    except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SecretDecryptionError("Secret could not be decrypted") from exc
