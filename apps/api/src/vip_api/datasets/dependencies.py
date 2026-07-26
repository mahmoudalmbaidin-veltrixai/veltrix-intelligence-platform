"""B5 governance dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.database.session import get_db_session
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import get_authorization_context
from vip_api.governance.services import GovernanceRequirement, authorize


class RequireB5Governance:
    def __init__(
        self,
        permission: str,
        *,
        feature: str,
        entitlement: str | None = None,
        quota: str | None = None,
    ) -> None:
        self.requirement = GovernanceRequirement(
            permission,
            feature=feature,
            entitlement=entitlement or feature,
            quota=quota,
        )
        self.governance_policy: object = self.requirement

    async def __call__(
        self,
        context: Annotated[AuthorizationContext, Depends(get_authorization_context)],
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> AuthorizationContext:
        await authorize(db, context, self.requirement)
        if context.workspace_id is None:
            raise RuntimeError("A validated workspace is required for B5 resources")
        return context
