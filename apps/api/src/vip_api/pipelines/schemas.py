"""Strict B7 REST contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class FormulaValidationRequest(StrictModel):
    expression: str = Field(min_length=1, max_length=4096)
    available_fields: list[str] = Field(default_factory=list, max_length=500)


class FormulaValidationResponse(StrictModel):
    valid: bool
    errors: list[str]
    used_functions: list[str]
    used_fields: list[str]


class NodeInput(StrictModel):
    id: UUID | None = None
    key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")
    type: str = Field(max_length=64)
    title: str = Field(min_length=1, max_length=200)
    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)
    config: dict[str, object] = Field(default_factory=dict)


class EdgeInput(StrictModel):
    id: UUID | None = None
    key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")
    source: str = Field(max_length=100)
    target: str = Field(max_length=100)
    source_port: str | None = Field(default=None, max_length=100)
    target_port: str | None = Field(default=None, max_length=100)


class PipelineCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=30)


class PipelineEditorSave(PipelineCreate):
    expected_version: int = Field(ge=1)
    canvas: dict[str, object] = Field(default_factory=dict)
    nodes: list[NodeInput] = Field(max_length=250)
    edges: list[EdgeInput] = Field(max_length=1000)


class PipelineSummary(StrictModel):
    id: UUID
    name: str
    description: str
    slug: str
    status: str
    tags: list[str]
    row_version: int
    published_version: int | None
    node_count: int
    last_run_at: datetime | None
    last_run_status: str | None
    updated_at: datetime


class PipelineAccess(StrictModel):
    """The caller's effective access to a pipeline, resolved by the centralized
    authorization engine. Lets the client render viewer/operator/developer/owner
    (and denied) UI states from the same decision the backend enforces —
    frontend visibility is a convenience, never the security boundary."""

    level: str | None
    allowed_levels: list[str]
    can_view: bool
    can_run: bool
    can_edit: bool
    can_manage: bool
    source: str
    reason: str


class PipelineEditor(StrictModel):
    pipeline: PipelineSummary
    canvas: dict[str, object]
    nodes: list[NodeInput]
    edges: list[EdgeInput]
    access: PipelineAccess | None = None


class ValidationIssue(StrictModel):
    code: str
    message: str
    node_key: str | None = None
    field: str | None = None


class ValidationResponse(StrictModel):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    topological_order: list[str]


class PublishRequest(StrictModel):
    expected_version: int = Field(ge=1)
    change_summary: str = Field(default="", max_length=500)


class VersionResponse(StrictModel):
    id: UUID
    pipeline_id: UUID
    version_number: int
    content_sha256: str
    change_summary: str
    created_by_user_id: UUID | None
    created_at: datetime


class RunCreate(StrictModel):
    pipeline_version_id: UUID | None = None


class RunResponse(StrictModel):
    id: UUID
    pipeline_id: UUID
    pipeline_version_id: UUID
    status: str
    progress: int
    trigger: str
    correlation_id: str
    current_attempt: int
    max_attempts: int
    cancellation_requested: bool
    rows_processed: int
    result_summary: dict[str, object]
    safe_error_code: str | None
    safe_error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class NodeRunResponse(StrictModel):
    node_key: str
    node_type: str
    status: str
    rows_in: int
    rows_out: int
    started_at: datetime | None
    completed_at: datetime | None
    safe_error_code: str | None


class LogResponse(StrictModel):
    sequence: int
    attempt_number: int
    node_key: str | None
    level: str
    message: str
    created_at: datetime


class RunDetail(RunResponse):
    nodes: list[NodeRunResponse]
    logs: list[LogResponse]


class ArtifactResponse(StrictModel):
    id: UUID
    node_key: str
    content_type: str
    size_bytes: int
    sha256: str
    expires_at: datetime
    created_at: datetime


class DownloadLink(StrictModel):
    url: str
    expires_in_seconds: int


class RestoreRequest(StrictModel):
    expected_version: int = Field(ge=1)


class ListPage(StrictModel):
    items: list[PipelineSummary]
    next_cursor: str | None = None


class RunListPage(StrictModel):
    items: list[RunResponse]
    next_cursor: str | None = None
