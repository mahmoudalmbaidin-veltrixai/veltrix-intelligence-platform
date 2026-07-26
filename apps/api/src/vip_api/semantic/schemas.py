"""Strongly typed semantic, glossary, and analytical query contracts."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SemanticKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")]


class SemanticModelCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    primary_dataset_id: UUID
    timezone: str = Field(default="UTC", max_length=80)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class SemanticModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    timezone: str | None = Field(default=None, max_length=80)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    version: int = Field(ge=1)


class SemanticModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    name: str
    description: str
    status: str
    primary_dataset_id: UUID
    timezone: str
    currency: str
    version_number: int
    published_version: int | None
    created_at: datetime
    updated_at: datetime
    version: int


class SemanticModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    semantic_model_id: UUID
    version_number: int
    definition: dict[str, object]
    published_by_user_id: UUID | None
    published_at: datetime


class ValidationIssue(BaseModel):
    code: str
    message: str
    resource: str | None = None


class SemanticValidationResponse(BaseModel):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]


class DimensionCreate(BaseModel):
    dataset_id: UUID
    field_id: UUID
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    dimension_type: Literal["categorical", "time", "geographic", "identifier", "boolean", "numeric"]
    is_time_dimension: bool = False
    time_granularities: list[Literal["day", "week", "month", "quarter", "year"]] = Field(
        default_factory=list
    )
    is_hidden: bool = False


class DimensionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    semantic_model_id: UUID
    dataset_id: UUID
    field_id: UUID
    key: str
    name: str
    description: str
    dimension_type: str
    data_type: str
    is_time_dimension: bool
    time_granularities: list[str]
    format: dict[str, object]
    is_hidden: bool
    sort_order: int


class MeasureCreate(BaseModel):
    dataset_id: UUID
    field_id: UUID | None = None
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    aggregation: Literal["sum", "count", "count_distinct", "average", "min", "max"]
    is_hidden: bool = False

    @model_validator(mode="after")
    def validate_field(self) -> "MeasureCreate":
        if self.aggregation != "count" and self.field_id is None:
            raise ValueError("A field is required for this aggregation")
        return self


class MeasureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    semantic_model_id: UUID
    dataset_id: UUID
    field_id: UUID | None
    key: str
    name: str
    description: str
    aggregation: str
    data_type: str
    format: dict[str, object]
    is_hidden: bool
    filters: list[dict[str, object]]


class MetricCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    metric_type: Literal["measure", "ratio"]
    base_measure_id: UUID | None = None
    numerator_metric_id: UUID | None = None
    denominator_metric_id: UUID | None = None
    unit: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "MetricCreate":
        if self.metric_type == "measure" and self.base_measure_id is None:
            raise ValueError("Measure metrics require a base measure")
        if self.metric_type == "ratio" and (
            self.numerator_metric_id is None or self.denominator_metric_id is None
        ):
            raise ValueError("Ratio metrics require numerator and denominator metrics")
        return self


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    semantic_model_id: UUID
    key: str
    name: str
    description: str
    metric_type: str
    base_measure_id: UUID | None
    numerator_metric_id: UUID | None
    denominator_metric_id: UUID | None
    format: dict[str, object]
    unit: str | None
    status: str


class KpiCreate(BaseModel):
    metric_id: UUID
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    target_value: Decimal | None = None
    warning_threshold: Decimal | None = None
    critical_threshold: Decimal | None = None
    comparison_operator: Literal[
        "greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal", "between"
    ]
    target_period: str | None = Field(default=None, max_length=40)


class KpiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    semantic_model_id: UUID
    metric_id: UUID
    key: str
    name: str
    description: str
    target_value: Decimal | None
    warning_threshold: Decimal | None
    critical_threshold: Decimal | None
    comparison_operator: str
    target_period: str | None
    status: str


class GlossaryDomainCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)


class GlossaryDomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    name: str
    description: str


class GlossaryTermCreate(BaseModel):
    domain_id: UUID
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    definition: str = Field(min_length=1, max_length=4000)
    synonyms: list[str] = Field(default_factory=list, max_length=30)
    examples: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("definition", "name")
    @classmethod
    def reject_markup(cls, value: str) -> str:
        if "<" in value or ">" in value:
            raise ValueError("HTML markup is not supported")
        return value.strip()


class GlossaryTermResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    domain_id: UUID
    key: str
    name: str
    definition: str
    status: str
    synonyms: list[str]
    examples: list[str]
    source: str


class GlossaryRelationshipCreate(BaseModel):
    target_term_id: UUID
    relationship_type: Literal[
        "broader_than", "narrower_than", "related_to", "synonym_of", "replaces"
    ]


class GlossaryRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_term_id: UUID
    target_term_id: UUID
    relationship_type: str


class GlossaryAssignmentCreate(BaseModel):
    resource_type: Literal[
        "dataset", "dataset_field", "semantic_model", "dimension", "measure", "metric", "kpi"
    ]
    resource_id: UUID


class GlossaryAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    term_id: UUID
    resource_type: str
    resource_id: UUID


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
    "is_null",
    "is_not_null",
    "contains",
    "starts_with",
    "ends_with",
]
Scalar = str | int | float | bool | None


class QueryFilter(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    operator: FilterOperator
    value: Scalar | list[Scalar] = None

    @model_validator(mode="after")
    def validate_shape(self) -> "QueryFilter":
        if self.operator in {"is_null", "is_not_null"} and self.value is not None:
            raise ValueError("Null operators do not accept a value")
        if self.operator == "between" and (
            not isinstance(self.value, list) or len(self.value) != 2
        ):
            raise ValueError("Between requires exactly two values")
        if self.operator in {"in", "not_in"} and not isinstance(self.value, list):
            raise ValueError("Set operators require a list")
        return self


class QueryOrder(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    direction: Literal["asc", "desc"] = "asc"


class SemanticQueryRequest(BaseModel):
    semantic_model_id: UUID
    metrics: list[SemanticKey] = Field(min_length=1)
    dimensions: list[SemanticKey] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    order_by: list[QueryOrder] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


class QueryColumn(BaseModel):
    key: str
    label: str
    data_type: str
    role: Literal["dimension", "metric"]
    format: dict[str, object] = Field(default_factory=dict)


class QueryExecution(BaseModel):
    status: Literal["success"] = "success"
    duration_ms: int
    executed_at: datetime


class SemanticQueryResult(BaseModel):
    query_id: UUID
    semantic_model: dict[str, str]
    columns: list[QueryColumn]
    rows: list[dict[str, Scalar]]
    row_count: int
    truncated: bool
    execution: QueryExecution
    correlation_id: str
