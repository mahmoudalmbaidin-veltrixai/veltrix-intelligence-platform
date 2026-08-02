"""Write-only credential requests and secret-safe connection responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from vip_api.governance.access_view import ResourceEffectiveAccess


class ConnectionTypeSummary(BaseModel):
    key: str
    name: str


class ConnectionTypeResponse(ConnectionTypeSummary):
    description: str
    category: str
    subcategory: str = ""
    vendor: str = ""
    implementation_status: str = "planned"
    deployment: str = "cloud"
    auth_methods: list[str] = []
    documentation_reference: str | None = None
    requirements: list[str] = []
    feature_flag: str | None = None
    beta: bool = False
    configuration_schema: dict[str, object]
    secret_schema: dict[str, object]
    capabilities: list[str]
    test_strategy: str
    is_enabled: bool
    version: int


class SecretFieldState(BaseModel):
    configured: bool


class ConnectionResponse(BaseModel):
    id: UUID
    name: str
    description: str
    type: ConnectionTypeSummary
    status: str
    health_status: str
    configuration: dict[str, object] | None = None
    credentials_configured: bool
    secret_fields: dict[str, SecretFieldState]
    credential_version: int
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_error_code: str | None
    last_test_latency_ms: int | None
    last_healthy_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    # Populated on single-connection reads with the caller's effective access so
    # the Studio renders use/test/edit/rotate/manager states. Never carries secrets.
    access: ResourceEffectiveAccess | None = None


class ConnectionListResponse(BaseModel):
    items: list[ConnectionResponse]
    page: int
    page_size: int
    total: int


class ConnectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    connection_type: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    configuration: dict[str, object]
    credentials: dict[str, SecretStr]


class ConnectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    configuration: dict[str, object] | None = None
    status: Literal["active", "inactive"] | None = None
    version: int = Field(ge=1)


class CredentialReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credentials: dict[str, SecretStr]
    expected_version: int = Field(ge=1)
    rotation_reason: str | None = Field(default=None, max_length=300)


class CredentialReplaceResponse(BaseModel):
    connection_id: UUID
    credential_version: int
    credentials_configured: Literal[True] = True
    health_status: Literal["unknown"] = "unknown"


class ConnectionTestError(BaseModel):
    code: str
    message: str


class ConnectionTestResponse(BaseModel):
    connection_id: UUID
    status: Literal["success", "failed"]
    health_status: str
    tested_at: datetime
    latency_ms: int
    message: str | None = None
    error: ConnectionTestError | None = None
    correlation_id: str
