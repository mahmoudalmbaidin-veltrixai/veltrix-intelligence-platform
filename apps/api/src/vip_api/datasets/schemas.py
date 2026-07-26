"""Validated dataset, quality, lineage, and discovery contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

Classification = Literal[
    "public", "internal", "confidential", "restricted", "personal", "financial", "operational"
]


class DatasetCreate(BaseModel):
    connection_id: UUID
    dataset_type: Literal[
        "table", "view", "materialized_view", "external_table", "file", "api_resource", "logical"
    ]
    source_catalog: str = Field(default="", max_length=255)
    source_schema: str = Field(min_length=1, max_length=255)
    source_name: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    description: str = Field(default="", max_length=2000)
    is_read_only: bool = True


class CsvIngestRequest(BaseModel):
    connection_id: UUID
    source_schema: str = Field(min_length=1, max_length=63, pattern=r"^[a-z][a-z0-9_]*$")
    source_name: str = Field(min_length=1, max_length=63, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str | None = Field(default=None, max_length=255)
    description: str = Field(default="", max_length=2000)
    csv_content: str = Field(min_length=1, max_length=5_000_000)


class FileCsvIngestRequest(BaseModel):
    file_id: UUID
    connection_id: UUID
    source_schema: str = Field(min_length=1, max_length=63, pattern=r"^[a-z][a-z0-9_]*$")
    source_name: str = Field(min_length=1, max_length=63, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str | None = Field(default=None, max_length=255)
    description: str = Field(default="", max_length=2000)


class DatasetPreviewColumn(BaseModel):
    name: str
    display_name: str
    physical_type: str
    normalized_type: str
    nullable: bool
    primary_key: bool
    unique: bool
    sensitive: bool
    classification: str


class DatasetPreviewResponse(BaseModel):
    dataset_id: UUID
    columns: list[DatasetPreviewColumn]
    rows: list[dict[str, object]]
    page: int
    page_size: int
    returned_rows: int
    sampled: bool = True
    masked_fields: list[str]
    refreshed_at: datetime


class DatasetProfileField(BaseModel):
    name: str
    null_count: int
    distinct_count: int
    minimum: str | None
    maximum: str | None
    sampled: bool = True


class DatasetProfileResponse(BaseModel):
    dataset_id: UUID
    fields: list[DatasetProfileField]
    sample_size: int
    refreshed_at: datetime


class DatasetUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    classification: Classification | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    business_domain: str | None = Field(default=None, max_length=160)
    refresh_expectation: str | None = Field(default=None, max_length=160)
    certification_status: (
        Literal["uncertified", "draft", "reviewed", "certified", "deprecated"] | None
    ) = None
    documentation_url: HttpUrl | None = None
    owner_user_id: UUID | None = None
    steward_user_id: UUID | None = None
    version: int = Field(ge=1)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({item.strip().lower() for item in value if item.strip()})


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    connection_id: UUID
    dataset_type: str
    source_catalog: str
    source_schema: str
    source_name: str
    qualified_name: str
    display_name: str
    description: str
    status: str
    discovery_status: str
    quality_status: str
    classification: str
    owner_user_id: UUID | None
    steward_user_id: UUID | None
    source_object_type: str
    is_read_only: bool
    row_count_estimate: int | None
    size_bytes_estimate: int | None
    tags: list[str]
    certification_status: str
    last_discovered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    page: int
    page_size: int
    total: int


class DatasetFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    source_name: str
    display_name: str
    description: str
    ordinal_position: int
    physical_data_type: str
    normalized_data_type: str
    semantic_type: str | None
    role: str
    is_nullable: bool
    is_primary_key: bool
    is_unique: bool
    is_hidden: bool
    is_sensitive: bool
    classification: str
    default_aggregation: str | None
    format: dict[str, object]
    version: int


class DatasetFieldUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    semantic_type: str | None = Field(default=None, max_length=32)
    role: (
        Literal["dimension", "measure", "identifier", "attribute", "timestamp", "hidden"] | None
    ) = None
    is_hidden: bool | None = None
    is_sensitive: bool | None = None
    classification: Classification | None = None
    default_aggregation: (
        Literal["sum", "count", "count_distinct", "average", "min", "max"] | None
    ) = None
    version: int = Field(ge=1)


class DiscoveryRequest(BaseModel):
    connection_id: UUID
    catalog: str | None = Field(default=None, max_length=255)
    schemas: list[str] = Field(default_factory=lambda: ["public"], min_length=1, max_length=20)
    include_object_types: list[Literal["table", "view", "materialized_view"]] = Field(
        default_factory=lambda: ["table", "view"]  # type: ignore[arg-type]
    )
    include_names: list[str] = Field(default_factory=lambda: ["*"], max_length=50)
    exclude_names: list[str] = Field(default_factory=list, max_length=50)
    persist: bool = True


class DiscoveryResult(BaseModel):
    datasets: list[DatasetResponse]
    discovered_count: int
    persisted_count: int
    truncated: bool
    warnings: list[str]
    correlation_id: str


RuleType = Literal[
    "not_null",
    "unique",
    "accepted_values",
    "range",
    "regex",
    "freshness",
    "row_count",
    "custom_reference",
]


class QualityRuleCreate(BaseModel):
    field_id: UUID | None = None
    rule_type: RuleType
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    configuration: dict[str, object] = Field(default_factory=dict)
    severity: Literal["info", "warning", "error", "critical"] = "warning"

    @field_validator("configuration")
    @classmethod
    def reject_sql(cls, value: dict[str, object]) -> dict[str, object]:
        forbidden = {"sql", "query", "expression", "statement"}
        if forbidden.intersection(key.lower() for key in value):
            raise ValueError("Arbitrary query text is not supported")
        return value


class QualityRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    field_id: UUID | None
    rule_type: str
    name: str
    description: str
    configuration: dict[str, object]
    severity: str
    status: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class QualityResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    quality_rule_id: UUID
    status: str
    observed_at: datetime
    evaluated_at: datetime
    observed_value: str | None
    expected_value: str | None
    failure_count: int | None
    sample_size: int | None
    safe_message: str | None
    execution_reference: str | None
    evaluation_id: UUID | None = None
    issue_details: list[dict[str, object]] = Field(default_factory=list)
    duration_ms: int | None = None


class QualitySummary(BaseModel):
    status: str
    score: int | None = None
    total_rules: int
    passing: int
    warning: int
    failing: int
    not_evaluated: int


class QualityEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    job_id: UUID | None
    status: str
    score: int | None
    total_rules: int
    passing: int
    warning: int
    failing: int
    unknown: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class LineageCreate(BaseModel):
    target_dataset_id: UUID
    lineage_type: Literal[
        "derived_from",
        "reads_from",
        "joins_with",
        "aggregates",
        "filters",
        "copies",
        "references",
        "produces",
    ]
    description: str = Field(default="", max_length=1000)


class LineageEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_dataset_id: UUID
    target_dataset_id: UUID
    lineage_type: str
    origin: str
    description: str


class LineageGraph(BaseModel):
    nodes: list[DatasetResponse]
    edges: list[LineageEdgeResponse]
    truncated: bool
    max_depth: int
