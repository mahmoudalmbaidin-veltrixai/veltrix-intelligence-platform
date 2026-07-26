"""Governance catalog, bootstrap, audit, and tenant-state APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import get_authorization_context, require_permission
from vip_api.governance.models import (
    AuditEvent,
    Entitlement,
    OrganizationEntitlement,
    Permission,
    Role,
    RolePermission,
)
from vip_api.schemas.governance import (
    AuditEventPage,
    AuditEventResponse,
    AuthorizationContextResponse,
    EntitlementResponse,
    FeatureFlagResponse,
    PermissionResponse,
    QuotaResponse,
    RoleResponse,
)

router = APIRouter(tags=["governance"])


@router.get("/authorization/context", response_model=AuthorizationContextResponse)
async def authorization_context(
    context: Annotated[AuthorizationContext, Depends(get_authorization_context)],
) -> AuthorizationContextResponse:
    return AuthorizationContextResponse(
        user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        organization_role=context.organization_role_key,
        workspace_role=context.workspace_role_key,
        permissions=sorted(context.permissions),
        features=dict(context.feature_flags),
        entitlements=sorted(context.entitlements),
        quotas={
            key: QuotaResponse(
                key=key,
                limit=value.limit,
                used=value.used,
                remaining=value.remaining,
                hard=value.hard,
            )
            for key, value in context.quotas.items()
        },
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    _context: Annotated[AuthorizationContext, Depends(require_permission("governance.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RoleResponse]:
    roles = list((await db.scalars(select(Role).order_by(Role.scope, Role.priority.desc()))).all())
    result: list[RoleResponse] = []
    for role in roles:
        permissions = list(
            (
                await db.scalars(
                    select(Permission.key)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == role.id)
                    .order_by(Permission.key)
                )
            ).all()
        )
        result.append(
            RoleResponse(
                id=role.id,
                key=role.key,
                name=role.name,
                scope=role.scope,
                is_assignable=role.is_assignable,
                priority=role.priority,
                permissions=permissions,
            )
        )
    return result


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    _context: Annotated[AuthorizationContext, Depends(require_permission("governance.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PermissionResponse]:
    values = list((await db.scalars(select(Permission).order_by(Permission.key))).all())
    return [
        PermissionResponse(
            id=value.id, key=value.key, name=value.name, scope=value.scope, category=value.category
        )
        for value in values
    ]


@router.get(
    "/organizations/{organization_id}/entitlements", response_model=list[EntitlementResponse]
)
async def list_entitlements(
    organization_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("governance.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[EntitlementResponse]:
    if organization_id != context.organization_id:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    rows = (
        (
            await db.execute(
                select(Entitlement, OrganizationEntitlement)
                .join(
                    OrganizationEntitlement,
                    OrganizationEntitlement.entitlement_id == Entitlement.id,
                )
                .where(OrganizationEntitlement.organization_id == organization_id)
            )
        )
        .tuples()
        .all()
    )
    return [
        EntitlementResponse(
            key=item.key, status=grant.status, starts_at=grant.starts_at, ends_at=grant.ends_at
        )
        for item, grant in rows
    ]


@router.get(
    "/organizations/{organization_id}/feature-flags", response_model=list[FeatureFlagResponse]
)
async def list_feature_flags(
    organization_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("governance.read"))],
) -> list[FeatureFlagResponse]:
    if organization_id != context.organization_id:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    return [
        FeatureFlagResponse(key=key, enabled=value)
        for key, value in sorted(context.feature_flags.items())
    ]


@router.get("/organizations/{organization_id}/quotas", response_model=list[QuotaResponse])
async def list_quotas(
    organization_id: UUID,
    context: Annotated[AuthorizationContext, Depends(require_permission("governance.read"))],
) -> list[QuotaResponse]:
    if organization_id != context.organization_id:
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    return [
        QuotaResponse(
            key=key, limit=value.limit, used=value.used, remaining=value.remaining, hard=value.hard
        )
        for key, value in sorted(context.quotas.items())
    ]


@router.get("/audit-events", response_model=AuditEventPage)
async def list_audit_events(
    context: Annotated[AuthorizationContext, Depends(require_permission("audit.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    workspace_id: UUID | None = None,
    event_type: str | None = None,
    outcome: str | None = None,
    actor_user_id: UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditEventPage:
    statement = select(AuditEvent).where(AuditEvent.organization_id == context.organization_id)
    if workspace_id is not None:
        statement = statement.where(AuditEvent.workspace_id == workspace_id)
    if event_type is not None:
        statement = statement.where(AuditEvent.event_type == event_type)
    if outcome is not None:
        statement = statement.where(AuditEvent.outcome == outcome)
    if actor_user_id is not None:
        statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
    if occurred_from is not None:
        statement = statement.where(AuditEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        statement = statement.where(AuditEvent.occurred_at <= occurred_to)
    values = list(
        (
            await db.scalars(
                statement.order_by(AuditEvent.occurred_at.desc()).offset(offset).limit(limit)
            )
        ).all()
    )
    await record_audit(
        db,
        "audit.read",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
    )
    await db.commit()
    return AuditEventPage(
        items=[
            AuditEventResponse(
                id=value.id,
                occurred_at=value.occurred_at,
                actor_user_id=value.actor_user_id,
                organization_id=value.organization_id,
                workspace_id=value.workspace_id,
                correlation_id=value.correlation_id,
                event_type=value.event_type,
                action=value.action,
                outcome=value.outcome,
                reason_code=value.reason_code,
                resource_type=value.resource_type,
                resource_id=value.resource_id,
                metadata=value.event_metadata,
            )
            for value in values
        ],
        limit=limit,
        offset=offset,
    )
