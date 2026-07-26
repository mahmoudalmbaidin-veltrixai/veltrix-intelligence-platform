"""Dependency construction for secret providers and tester registries."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.crypto import EnvironmentEncryptionKeyProvider
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.connections.testers import ConnectionTesterRegistry
from vip_api.core.config import get_settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import get_authorization_context
from vip_api.governance.services import GovernanceRequirement, authorize


class RequireConnectionGovernance:
    """B3 policy enforcement plus a connection-specific safe denial event."""

    def __init__(self, permission: str, *, quota: str | None = None) -> None:
        self.requirement = GovernanceRequirement(
            permission,
            feature="connection_studio",
            entitlement="connection_studio",
            quota=quota,
        )
        self.governance_policy: object = self.requirement

    async def __call__(
        self,
        context: Annotated[AuthorizationContext, Depends(get_authorization_context)],
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> AuthorizationContext:
        try:
            await authorize(db, context, self.requirement)
        except ApplicationError as exc:
            await record_audit(
                db,
                "connection.access.denied",
                actor_user_id=context.user_id,
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                outcome="denied",
                reason_code=exc.code,
                metadata={"permission": self.requirement.permission},
                commit=True,
            )
            raise
        return context


def get_secret_provider() -> DatabaseEncryptedSecretProvider:
    settings = get_settings()
    if settings.CONNECTION_SECRET_PROVIDER != "database_encrypted":  # noqa: S105
        raise RuntimeError("Unknown connection secret provider")
    return DatabaseEncryptedSecretProvider(EnvironmentEncryptionKeyProvider(settings))


@lru_cache(maxsize=1)
def get_tester_registry() -> ConnectionTesterRegistry:
    return ConnectionTesterRegistry(get_settings())
