"""Response and request contracts for the platform super-admin console."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlatformOverview(BaseModel):
    organizations_total: int
    organizations_active: int
    organizations_suspended: int
    workspaces_total: int
    users_total: int
    users_active: int
    users_suspended: int
    platform_admins: int


class PlatformOrganizationRow(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    member_count: int
    workspace_count: int
    created_at: datetime


class PlatformOrganizationList(BaseModel):
    items: list[PlatformOrganizationRow]
    page: int
    page_size: int
    total: int


class PlatformMemberRow(BaseModel):
    user_id: UUID
    username: str = ""
    email: str | None = None
    display_name: str
    role: str
    status: str


class PlatformWorkspaceRow(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    is_default: bool


class PlatformOrganizationDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime
    members: list[PlatformMemberRow]
    workspaces: list[PlatformWorkspaceRow]


class PlatformUserRow(BaseModel):
    id: UUID
    username: str
    email: str | None = None
    display_name: str
    status: str
    is_platform_admin: bool
    organization_count: int
    created_at: datetime
    last_login_at: datetime | None


class PlatformUserList(BaseModel):
    items: list[PlatformUserRow]
    page: int
    page_size: int
    total: int


class CreateOrganizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    owner_email: str | None = Field(default=None, max_length=320)


class CreatePlatformUserRequest(BaseModel):
    """Admin-provisioned user (operator sets the initial password).

    'username' maps to display_name; the login identifier is the email. No
    schema/migration change is required — all fields already exist on ``User``.
    Optionally assign the new user into an organization + role in one step so
    they immediately have the right modules and workspace access.
    """

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=150)
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    is_platform_admin: bool = False
    organization_id: UUID | None = None
    organization_role: str | None = Field(default=None, max_length=100)


class AddOrgMemberRequest(BaseModel):
    """Add an existing user to an organization with a role (platform-admin).

    Identify the user by username (primary) or email; at least one is required.
    """

    model_config = ConfigDict(extra="forbid")
    username: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)
    organization_role: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _require_identifier(self) -> AddOrgMemberRequest:
        if not (self.username or self.email):
            raise ValueError("A username or email is required.")
        return self
