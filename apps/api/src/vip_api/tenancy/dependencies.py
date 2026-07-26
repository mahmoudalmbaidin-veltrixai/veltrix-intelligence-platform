"""Authoritative tenant resolution and minimal B2 role enforcement."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import AuthenticatedContext, get_current_session
from vip_api.core.config import Settings
from vip_api.core.context import bind_tenant_context, get_correlation_id
from vip_api.core.errors import ApplicationError
from vip_api.database.session import get_db_session
from vip_api.tenancy.audit import audit_event
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.repositories import OrganizationRepository, WorkspaceRepository


def _required_header(request: Request, name: str) -> UUID:
    value = request.headers.get(name)
    if value is None:
        raise ApplicationError(
            code="TENANT_CONTEXT_REQUIRED",
            message=f"The {name} header is required.",
            status_code=400,
        )
    try:
        return UUID(value)
    except ValueError as exc:
        raise ApplicationError(
            code="INVALID_TENANT_CONTEXT",
            message="The tenant context is invalid.",
            status_code=400,
        ) from exc


async def get_tenant_context(
    request: Request,
    auth: Annotated[AuthenticatedContext, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TenantContext:
    cached = getattr(request.state, "tenant_context", None)
    if isinstance(cached, TenantContext):
        return cached
    settings: Settings = request.app.state.settings
    organization_id = _required_header(request, settings.TENANCY_ORGANIZATION_HEADER)
    organization_result = await OrganizationRepository(db).get_authorized(
        organization_id, auth.user.id
    )
    if organization_result is None:
        audit_event(
            "tenant.organization_access_denied",
            actor_user_id=auth.user.id,
            organization_id=organization_id,
            resource_type="organization",
            resource_id=organization_id,
            outcome="denied",
        )
        raise ApplicationError(
            code="ORGANIZATION_NOT_FOUND",
            message="The organization was not found.",
            status_code=404,
        )
    _organization, organization_membership = organization_result

    workspace_id: UUID | None = None
    workspace_membership_id: UUID | None = None
    workspace_role: str | None = None
    workspace_value = request.headers.get(settings.TENANCY_WORKSPACE_HEADER)
    if workspace_value is not None:
        try:
            workspace_id = UUID(workspace_value)
        except ValueError as exc:
            raise ApplicationError(
                code="INVALID_TENANT_CONTEXT",
                message="The tenant context is invalid.",
                status_code=400,
            ) from exc
        workspace_result = await WorkspaceRepository(db).get_authorized(
            organization_id, workspace_id, auth.user.id
        )
        if workspace_result is None:
            audit_event(
                "tenant.workspace_access_denied",
                actor_user_id=auth.user.id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                resource_type="workspace",
                resource_id=workspace_id,
                outcome="denied",
            )
            raise ApplicationError(
                code="WORKSPACE_NOT_FOUND",
                message="The workspace was not found.",
                status_code=404,
            )
        _workspace, workspace_membership = workspace_result
        workspace_membership_id = workspace_membership.id
        workspace_role = workspace_membership.role.key
    context = TenantContext(
        user_id=auth.user.id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        organization_membership_id=organization_membership.id,
        workspace_membership_id=workspace_membership_id,
        organization_role=organization_membership.role.key,
        workspace_role=workspace_role,
        correlation_id=get_correlation_id(),
    )
    request.state.tenant_context = context
    bind_tenant_context(context)
    return context


async def require_workspace_context(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    if context.workspace_id is None:
        raise ApplicationError(
            code="TENANT_CONTEXT_REQUIRED",
            message="Workspace context is required.",
            status_code=400,
        )
    return context


def require_manager(role: str) -> None:
    if role not in {"organization_owner", "organization_admin"}:
        raise ApplicationError(
            code="ORGANIZATION_ACCESS_DENIED",
            message="You do not have permission to perform this action.",
            status_code=403,
        )
