"""Immutable, request-scoped validated tenant context."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    organization_membership_id: UUID
    workspace_membership_id: UUID | None
    organization_role: str
    workspace_role: str | None
    correlation_id: str
