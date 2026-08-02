"""Public request and response contracts for tenant management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vip_api.auth.authentication import normalize_email
from vip_api.tenancy.models import (
    InvitationStatus,
    MembershipStatus,
    OrganizationStatus,
    WorkspaceStatus,
)


class MembershipSummary(BaseModel):
    role: str
    status: MembershipStatus


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
    membership: MembershipSummary


class OrganizationList(BaseModel):
    items: list[OrganizationSummary]


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    status: OrganizationStatus | None = None


class WorkspaceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: WorkspaceStatus
    is_default: bool


class WorkspaceList(BaseModel):
    items: list[WorkspaceSummary]


class OrganizationCreated(BaseModel):
    organization: OrganizationSummary
    default_workspace: WorkspaceSummary


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    status: WorkspaceStatus | None = None
    is_default: bool | None = None


class MemberSummary(BaseModel):
    id: UUID
    user_id: UUID
    username: str = ""
    email: str | None = None
    display_name: str
    role: str
    status: MembershipStatus
    joined_at: datetime | None


class MemberList(BaseModel):
    items: list[MemberSummary]


class MemberUpdate(BaseModel):
    role: str | None = Field(default=None, min_length=2, max_length=100)
    status: MembershipStatus | None = None


class WorkspaceMemberCreate(BaseModel):
    user_id: UUID
    role: str = Field(default="viewer", min_length=2, max_length=100)


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    organization_role: str = Field(default="organization_member", min_length=2, max_length=100)
    workspace_role: str = Field(default="viewer", min_length=2, max_length=100)
    workspace_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("A valid email address is required")
        return value.strip()

    @field_validator("workspace_ids")
    @classmethod
    def unique_workspaces(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("workspace_ids must not contain duplicates")
        return value


class InvitationSummary(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    organization_role: str
    workspace_role: str
    workspace_ids: list[UUID]
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class InvitationCreated(InvitationSummary):
    token: str | None = Field(
        default=None,
        description="Development/test delivery value; always omitted in staging and production.",
    )


class InvitationList(BaseModel):
    items: list[InvitationSummary]


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class InvitationAccepted(BaseModel):
    organization_id: UUID
    workspace_ids: list[UUID]
    status: InvitationStatus


class TenantContextResponse(BaseModel):
    user_id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    organization_membership_id: UUID
    workspace_membership_id: UUID | None
    organization_role: str
    workspace_role: str | None
    correlation_id: str
