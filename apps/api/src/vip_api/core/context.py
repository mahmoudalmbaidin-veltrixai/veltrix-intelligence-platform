"""Request-scoped identifiers used by logging and error responses."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vip_api.tenancy.context import TenantContext

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="unavailable")
request_id_var: ContextVar[str] = ContextVar("request_id", default="unavailable")
actor_user_id_var: ContextVar[str | None] = ContextVar("actor_user_id", default=None)
organization_id_var: ContextVar[str | None] = ContextVar("organization_id", default=None)
workspace_id_var: ContextVar[str | None] = ContextVar("workspace_id", default=None)
organization_membership_id_var: ContextVar[str | None] = ContextVar(
    "organization_membership_id", default=None
)
workspace_membership_id_var: ContextVar[str | None] = ContextVar(
    "workspace_membership_id", default=None
)


def bind_request_context(
    correlation_id: str, request_id: str
) -> tuple[
    Token[str],
    Token[str],
    Token[str | None],
    Token[str | None],
    Token[str | None],
    Token[str | None],
    Token[str | None],
]:
    return (
        correlation_id_var.set(correlation_id),
        request_id_var.set(request_id),
        actor_user_id_var.set(None),
        organization_id_var.set(None),
        workspace_id_var.set(None),
        organization_membership_id_var.set(None),
        workspace_membership_id_var.set(None),
    )


def reset_request_context(
    tokens: tuple[
        Token[str],
        Token[str],
        Token[str | None],
        Token[str | None],
        Token[str | None],
        Token[str | None],
        Token[str | None],
    ],
) -> None:
    correlation_id_var.reset(tokens[0])
    request_id_var.reset(tokens[1])
    actor_user_id_var.reset(tokens[2])
    organization_id_var.reset(tokens[3])
    workspace_id_var.reset(tokens[4])
    organization_membership_id_var.reset(tokens[5])
    workspace_membership_id_var.reset(tokens[6])


def get_correlation_id() -> str:
    return correlation_id_var.get()


def bind_tenant_context(context: TenantContext) -> None:
    """Bind only server-validated tenant identifiers for logs and audit events."""
    actor_user_id_var.set(str(context.user_id))
    organization_id_var.set(str(context.organization_id))
    workspace_id_var.set(str(context.workspace_id) if context.workspace_id else None)
    organization_membership_id_var.set(str(context.organization_membership_id))
    workspace_membership_id_var.set(
        str(context.workspace_membership_id) if context.workspace_membership_id else None
    )
