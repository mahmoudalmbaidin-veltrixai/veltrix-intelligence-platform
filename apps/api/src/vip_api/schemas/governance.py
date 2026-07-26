"""Safe public governance response contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PermissionResponse(BaseModel):
    id: UUID
    key: str
    name: str
    scope: str
    category: str


class RoleResponse(BaseModel):
    id: UUID
    key: str
    name: str
    scope: str
    is_assignable: bool
    priority: int
    permissions: list[str] = Field(default_factory=list)


class QuotaResponse(BaseModel):
    key: str
    limit: int
    used: int
    remaining: int
    hard: bool


class AuthorizationContextResponse(BaseModel):
    user_id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    organization_role: str
    workspace_role: str | None
    permissions: list[str]
    features: dict[str, bool]
    entitlements: list[str]
    quotas: dict[str, QuotaResponse]


class AuditEventResponse(BaseModel):
    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    organization_id: UUID | None
    workspace_id: UUID | None
    correlation_id: str
    event_type: str
    action: str
    outcome: str
    reason_code: str | None
    resource_type: str | None
    resource_id: UUID | None
    metadata: dict[str, object]


class AuditEventPage(BaseModel):
    items: list[AuditEventResponse]
    limit: int
    offset: int


class EntitlementResponse(BaseModel):
    key: str
    status: str
    starts_at: datetime | None
    ends_at: datetime | None


class FeatureFlagResponse(BaseModel):
    key: str
    enabled: bool
