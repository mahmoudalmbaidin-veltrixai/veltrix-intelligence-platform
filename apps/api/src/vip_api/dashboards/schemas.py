"""Strict public contracts for Dashboard Studio."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WidgetType = Literal[
    "kpi",
    "metric-comparison",
    "table",
    "pivot",
    "bar",
    "stacked-bar",
    "column",
    "line",
    "area",
    "pie",
    "donut",
    "scatter",
    "gauge",
    "progress",
    "text",
    "rich-text",
    "image",
    "filter",
    "date-filter",
    "map",
]
FilterOperator = Literal[
    "equals",
    "not_equals",
    "in",
    "not_in",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "between",
    "contains",
    "starts_with",
    "ends_with",
    "is_null",
    "is_not_null",
]
Scalar = str | int | float | bool | None
SAFE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
FORBIDDEN_TEXT = re.compile(
    r"(?is)<\s*(script|iframe|style)|javascript\s*:|\b(select|insert|update|delete|drop|alter)\b.+\b(from|into|table)\b|--|/\*"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GridLayout(StrictModel):
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0, le=10000)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def fits_grid(self) -> GridLayout:
        if self.x + self.w > 12:
            raise ValueError("Widget extends beyond the 12-column grid")
        return self


class SemanticFilter(StrictModel):
    field: str = Field(min_length=1, max_length=100)
    operator: FilterOperator
    value: Scalar | list[Scalar] = None

    @field_validator("field")
    @classmethod
    def safe_field(cls, value: str) -> str:
        if not SAFE_KEY.fullmatch(value):
            raise ValueError("Filter field must be a semantic key")
        return value


class SemanticOrder(StrictModel):
    field: str = Field(min_length=1, max_length=100)
    direction: Literal["asc", "desc"] = "asc"


class WidgetQuery(StrictModel):
    metrics: list[str] = Field(default_factory=list, max_length=20)
    dimensions: list[str] = Field(default_factory=list, max_length=10)
    filters: list[SemanticFilter] = Field(default_factory=list, max_length=25)
    order_by: list[SemanticOrder] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("metrics", "dimensions")
    @classmethod
    def safe_keys(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(
            not SAFE_KEY.fullmatch(value) for value in values
        ):
            raise ValueError("Semantic fields must be unique safe keys")
        return values


class WidgetInput(StrictModel):
    id: UUID | None = None
    page_id: UUID | None = None
    type: WidgetType
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    semantic_model_id: UUID | None = None
    query: WidgetQuery = Field(default_factory=WidgetQuery)
    config: dict[str, object] = Field(default_factory=dict)
    layout: GridLayout
    filters: list[SemanticFilter] = Field(default_factory=list, max_length=25)
    interactions: dict[str, object] = Field(default_factory=dict)
    content: str | None = Field(default=None, max_length=10000)
    hidden: bool = False

    @model_validator(mode="after")
    def validate_widget(self) -> WidgetInput:
        serialized = self.model_dump_json()
        if FORBIDDEN_TEXT.search(serialized):
            raise ValueError("Executable content and SQL are not allowed")
        data_widgets = {
            "kpi",
            "metric-comparison",
            "table",
            "pivot",
            "bar",
            "stacked-bar",
            "column",
            "line",
            "area",
            "pie",
            "donut",
            "scatter",
            "gauge",
            "progress",
            "map",
        }
        if self.type in data_widgets and (self.semantic_model_id is None or not self.query.metrics):
            raise ValueError("Data widgets require a semantic model and metric")
        allowed_config = {
            "decimals",
            "number_style",
            "currency",
            "show_legend",
            "show_labels",
            "show_gridlines",
            "legend_position",
            "color_scheme",
            "subtitle",
            "background",
            "border",
            "padding",
            "conditional",
            "locked",
            "aria_label",
            "min",
            "max",
            "target",
            "columns",
        }
        if set(self.config) - allowed_config:
            raise ValueError("Widget configuration contains unsupported fields")
        return self


class PageInput(StrictModel):
    id: UUID | None = None
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    position: int = Field(ge=0, le=49)
    canvas: dict[str, object] = Field(default_factory=dict)
    widgets: list[WidgetInput] = Field(default_factory=list, max_length=100)

    @field_validator("key")
    @classmethod
    def safe_key(cls, value: str) -> str:
        if not SAFE_KEY.fullmatch(value):
            raise ValueError("Page key must use lowercase letters, digits, and underscores")
        return value


class DashboardFilterInput(StrictModel):
    id: UUID | None = None
    key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    type: Literal["select", "multi_select", "date", "date_range", "number", "number_range", "text"]
    semantic_model_id: UUID
    dimension_key: str = Field(min_length=1, max_length=100)
    operator: FilterOperator
    default_value: Scalar | list[Scalar] = None
    widget_ids: list[UUID] = Field(default_factory=list, max_length=250)
    position: int = Field(ge=0, le=49)

    @field_validator("key", "dimension_key")
    @classmethod
    def safe_key(cls, value: str) -> str:
        if not SAFE_KEY.fullmatch(value):
            raise ValueError("Filter keys must be safe semantic identifiers")
        return value


class DashboardCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=20)


class DashboardUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=20)


class EditorSave(StrictModel):
    expected_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    pages: list[PageInput] = Field(min_length=1, max_length=50)
    filters: list[DashboardFilterInput] = Field(default_factory=list, max_length=50)
    change_summary: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_aggregate(self) -> EditorSave:
        page_keys = [page.key for page in self.pages]
        positions = [page.position for page in self.pages]
        if len(page_keys) != len(set(page_keys)) or len(positions) != len(set(positions)):
            raise ValueError("Page keys and positions must be unique")
        if sum(len(page.widgets) for page in self.pages) > 250:
            raise ValueError("Dashboard widget limit exceeded")
        return self


class DashboardSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    status: str
    owner_user_id: UUID
    tags: list[str]
    row_version: int
    page_count: int
    widget_count: int
    updated_at: datetime
    published_version: int | None


class DashboardDetail(DashboardSummary):
    created_at: datetime
    archived_at: datetime | None
    access: dict[str, bool]


class EditorResponse(StrictModel):
    dashboard: DashboardDetail
    pages: list[PageInput]
    filters: list[DashboardFilterInput]
    version: int
    etag: str


class VersionResponse(BaseModel):
    id: UUID
    version_number: int
    version_type: str
    created_by_user_id: UUID | None
    created_at: datetime
    published_at: datetime | None
    change_summary: str
    current_published: bool


class VersionMutation(StrictModel):
    expected_version: int = Field(ge=1)
    change_summary: str = Field(default="", max_length=500)


class ShareCreate(StrictModel):
    expected_version: int = Field(ge=1)
    principal_type: Literal["user", "workspace_role", "organization_role"]
    principal_id: UUID
    permission_level: Literal["view", "interact", "edit", "manage"]
    expires_at: datetime | None = None


class ShareResponse(BaseModel):
    id: UUID
    principal_type: str
    principal_id: UUID
    permission_level: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class SnapshotCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    filter_state: dict[str, Scalar | list[Scalar]] = Field(default_factory=dict)


class SnapshotResponse(BaseModel):
    id: UUID
    dashboard_version_id: UUID
    name: str
    description: str
    filter_state: dict[str, object]
    data_snapshot: dict[str, object]
    status: str
    created_by_user_id: UUID | None
    created_at: datetime
    expires_at: datetime | None


class WidgetDataRequest(StrictModel):
    dashboard_version: int | None = Field(default=None, ge=1)
    preview: bool = False
    filters: dict[str, Scalar | list[Scalar]] = Field(default_factory=dict)
    limit_override: int | None = Field(default=None, ge=1, le=1000)


class WidgetDataResponse(BaseModel):
    dashboard_id: UUID
    widget_id: UUID
    dashboard_version: int
    widget_type: str
    columns: list[dict[str, object]]
    rows: list[dict[str, Scalar]]
    row_count: int
    truncated: bool
    render_hint: dict[str, object]
    execution: dict[str, object]
    shaped: dict[str, object]
    correlation_id: str
