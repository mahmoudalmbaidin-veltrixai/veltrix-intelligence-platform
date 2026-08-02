"""Public contracts for groups, resource permissions, sharing, and principals."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GroupResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    workspace_id: UUID | None
    archived_at: datetime | None
    row_version: int
    member_count: int
    created_at: datetime
    updated_at: datetime


class GroupCreate(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)
    workspace_id: UUID | None = None


class GroupUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)


class GroupArchiveRequest(StrictModel):
    expected_version: int = Field(ge=1)
    archived: bool


class GroupMemberResponse(BaseModel):
    user_id: UUID
    display_name: str
    email: str | None
    username: str
    added_at: datetime


class GroupMemberAdd(StrictModel):
    user_id: UUID


class PrincipalResponse(BaseModel):
    principal_type: str
    id: UUID
    label: str
    detail: str | None
    in_workspace: bool


class ResourceEntryResponse(BaseModel):
    id: UUID
    subject_type: str
    subject_id: UUID
    subject_label: str
    subject_detail: str | None
    access_level: str
    effect: str
    expires_at: datetime | None
    granted_by_user_id: UUID | None
    created_at: datetime


class ResourceGrantRequest(StrictModel):
    subject_type: str = Field(pattern="^(user|group)$")
    subject_id: UUID
    access_level: str = Field(min_length=1, max_length=32)
    effect: str = Field(default="allow", pattern="^(allow|deny)$")
    expires_at: datetime | None = None


class ResourceTypeInfo(BaseModel):
    resource_type: str
    levels: list[str]


class EffectiveAccessResponse(BaseModel):
    resource_type: str
    resource_id: UUID
    user_id: UUID
    level: str | None
    allowed_levels: list[str]
    source: str
    reason: str


class SimulateRequest(StrictModel):
    user_id: UUID


# --------------------------------------------------------------------------- roles


class PermissionCatalogItem(BaseModel):
    key: str
    name: str
    description: str
    scope: str
    category: str


class RoleResponse(BaseModel):
    id: UUID
    name: str
    slug: str | None
    description: str
    scope: str
    status: str
    is_system: bool
    is_editable: bool
    organization_id: UUID | None
    workspace_id: UUID | None
    priority: int
    permission_keys: list[str]
    assignment_count: int
    row_version: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RoleCreate(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=500)
    scope: str = Field(pattern="^(organization|workspace)$")
    permission_keys: list[str] = Field(default_factory=list)


class RoleUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    permission_keys: list[str] | None = None


class RoleCloneRequest(StrictModel):
    name: str = Field(min_length=2, max_length=160)


class RoleArchiveRequest(StrictModel):
    expected_version: int = Field(ge=1)
    archived: bool


class RoleAssignmentResponse(BaseModel):
    id: UUID
    subject_type: str
    subject_id: UUID
    subject_label: str
    role_id: UUID
    role_name: str
    scope: str
    workspace_id: UUID | None
    created_at: datetime


class RoleAssignRequest(StrictModel):
    subject_type: str = Field(pattern="^(user|group)$")
    subject_id: UUID


class BulkRoleAssignRequest(StrictModel):
    user_ids: list[UUID] = Field(default_factory=list)
    group_ids: list[UUID] = Field(default_factory=list)


class BulkResultItem(BaseModel):
    subject_id: UUID
    ok: bool
    detail: str


class ResourceSearchItem(BaseModel):
    id: UUID
    name: str
    resource_type: str
    status: str | None
    owner_user_id: UUID | None
    workspace_id: UUID | None
    updated_at: datetime | None
