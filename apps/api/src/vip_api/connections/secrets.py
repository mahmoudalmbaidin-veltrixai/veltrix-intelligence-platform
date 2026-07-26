"""Tenant-validating secret-provider abstraction and encrypted database provider."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import utc_now
from vip_api.connections.crypto import (
    EncryptionKeyProvider,
    associated_data,
    decrypt_json,
    encrypt_json,
)
from vip_api.connections.models import ConnectionSecret


class SecretProviderError(RuntimeError):
    pass


class SecretProvider(Protocol):
    async def store_secret(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        workspace_id: UUID,
        connection_id: UUID,
        credential_version: int,
        credentials: dict[str, str],
        actor_user_id: UUID,
    ) -> ConnectionSecret: ...

    async def read_secret(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        workspace_id: UUID,
        connection_id: UUID,
        secret_id: UUID,
    ) -> dict[str, str]: ...

    async def revoke_secret(
        self, db: AsyncSession, *, organization_id: UUID, workspace_id: UUID, secret_id: UUID
    ) -> None: ...

    async def health_check(self) -> bool: ...


class DatabaseEncryptedSecretProvider:
    provider_name = "database_encrypted"

    def __init__(self, key_provider: EncryptionKeyProvider) -> None:
        self.key_provider = key_provider

    async def store_secret(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        workspace_id: UUID,
        connection_id: UUID,
        credential_version: int,
        credentials: dict[str, str],
        actor_user_id: UUID,
    ) -> ConnectionSecret:
        secret_id = uuid4()
        aad = associated_data(
            organization_id, workspace_id, secret_id, self.provider_name, credential_version
        )
        ciphertext, nonce, key_version = await encrypt_json(credentials, aad, self.key_provider)
        secret = ConnectionSecret(
            id=secret_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            provider=self.provider_name,
            provider_reference=f"database-encrypted://{secret_id}",
            ciphertext=ciphertext,
            nonce=nonce,
            encryption_algorithm="AES-256-GCM",
            key_version=key_version,
            credential_version=credential_version,
            secret_fields=sorted(credentials),
            created_by_user_id=actor_user_id,
        )
        db.add(secret)
        await db.flush()
        return secret

    async def _get_scoped(
        self,
        db: AsyncSession,
        organization_id: UUID,
        workspace_id: UUID,
        connection_id: UUID | None,
        secret_id: UUID,
    ) -> ConnectionSecret:
        conditions = [
            ConnectionSecret.id == secret_id,
            ConnectionSecret.organization_id == organization_id,
            ConnectionSecret.workspace_id == workspace_id,
            ConnectionSecret.revoked_at.is_(None),
        ]
        if connection_id is not None:
            conditions.append(ConnectionSecret.connection_id == connection_id)
        secret = await db.scalar(select(ConnectionSecret).where(*conditions))
        if secret is None:
            raise SecretProviderError("Secret is unavailable")
        return secret

    async def read_secret(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        workspace_id: UUID,
        connection_id: UUID,
        secret_id: UUID,
    ) -> dict[str, str]:
        secret = await self._get_scoped(db, organization_id, workspace_id, connection_id, secret_id)
        aad = associated_data(
            organization_id,
            workspace_id,
            secret.id,
            secret.provider,
            secret.credential_version,
        )
        return await decrypt_json(
            secret.ciphertext, secret.nonce, aad, secret.key_version, self.key_provider
        )

    async def revoke_secret(
        self, db: AsyncSession, *, organization_id: UUID, workspace_id: UUID, secret_id: UUID
    ) -> None:
        secret = await self._get_scoped(db, organization_id, workspace_id, None, secret_id)
        secret.revoked_at = utc_now()
        await db.flush()

    async def health_check(self) -> bool:
        await self.key_provider.get_active_key()
        return True
