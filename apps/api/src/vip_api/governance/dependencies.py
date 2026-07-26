"""Reusable FastAPI governance dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.database.session import get_db_session
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import (
    GovernanceRequirement,
    authorize,
    authorize_any,
    authorize_capability,
    resolve_authorization_context,
)
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.dependencies import get_tenant_context


async def get_authorization_context(
    request: Request,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthorizationContext:
    cached = getattr(request.state, "authorization_context", None)
    if isinstance(cached, AuthorizationContext):
        return cached
    context = await resolve_authorization_context(db, tenant)
    request.state.authorization_context = context
    return context


class RequireGovernance:
    def __init__(
        self,
        permission: str,
        *,
        feature: str | None = None,
        entitlement: str | None = None,
        quota: str | None = None,
        amount: int = 1,
    ) -> None:
        self.requirement = GovernanceRequirement(permission, feature, entitlement, quota, amount)
        self.governance_policy: object = self.requirement

    async def __call__(
        self,
        context: Annotated[AuthorizationContext, Depends(get_authorization_context)],
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> AuthorizationContext:
        await authorize(db, context, self.requirement)
        return context


class RequireCapability:
    """Require feature and entitlement gates without imposing an RBAC permission."""

    def __init__(self, feature: str, entitlement: str) -> None:
        self.feature = feature
        self.entitlement = entitlement

    async def __call__(
        self,
        context: Annotated[AuthorizationContext, Depends(get_authorization_context)],
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> AuthorizationContext:
        await authorize_capability(db, context, feature=self.feature, entitlement=self.entitlement)
        return context


def require_permission(permission: str) -> RequireGovernance:
    return RequireGovernance(permission)


def require_capability(feature: str, entitlement: str) -> RequireCapability:
    return RequireCapability(feature, entitlement)


def require_governance(
    permission: str,
    *,
    feature: str | None = None,
    entitlement: str | None = None,
    quota: str | None = None,
    amount: int = 1,
) -> RequireGovernance:
    return RequireGovernance(
        permission, feature=feature, entitlement=entitlement, quota=quota, amount=amount
    )


def require_any_permission(*permissions: str) -> RequireGovernance:
    if not permissions:
        raise ValueError("At least one permission is required")
    return RequireAnyGovernance(frozenset(permissions))


class RequireAnyGovernance(RequireGovernance):
    def __init__(self, permissions: frozenset[str]) -> None:
        super().__init__(sorted(permissions)[0])
        self.permissions = permissions
        self.governance_policy = permissions

    async def __call__(
        self,
        context: Annotated[AuthorizationContext, Depends(get_authorization_context)],
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> AuthorizationContext:
        await authorize_any(db, context, self.permissions)
        return context


def require_all_permissions(*permissions: str) -> list[RequireGovernance]:
    if not permissions:
        raise ValueError("At least one permission is required")
    return [RequireGovernance(permission) for permission in permissions]
