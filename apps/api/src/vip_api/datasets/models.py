"""Persistent B5 dataset catalog models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.auth.models import utc_now
from vip_api.database.base import Base


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "connection_id"],
            ["connections.organization_id", "connections.workspace_id", "connections.id"],
            ondelete="RESTRICT",
            name="fk_datasets_connection_tenant",
        ),
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_datasets_tenant_id"),
        UniqueConstraint(
            "organization_id", "workspace_id", "source_key", name="uq_datasets_source_key"
        ),
        CheckConstraint("version > 0", name="datasets_positive_version"),
        Index("ix_datasets_tenant_status", "organization_id", "workspace_id", "status"),
        Index("ix_datasets_connection", "organization_id", "workspace_id", "connection_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_catalog: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_schema: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_key: Mapped[str] = mapped_column(String(700), nullable=False)
    qualified_name: Mapped[str] = mapped_column(String(700), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    discovery_status: Mapped[str] = mapped_column(String(24), default="discovered", nullable=False)
    metadata_status: Mapped[str] = mapped_column(String(24), default="current", nullable=False)
    quality_status: Mapped[str] = mapped_column(String(24), default="not_evaluated", nullable=False)
    classification: Mapped[str] = mapped_column(String(24), default="internal", nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    steward_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    source_object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_read_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    row_count_estimate: Mapped[int | None] = mapped_column(BigInteger)
    size_bytes_estimate: Mapped[int | None] = mapped_column(BigInteger)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    business_domain: Mapped[str | None] = mapped_column(String(160))
    refresh_expectation: Mapped[str | None] = mapped_column(String(160))
    certification_status: Mapped[str] = mapped_column(
        String(24), default="uncertified", nullable=False
    )
    documentation_url: Mapped[str | None] = mapped_column(String(1000))
    last_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_metadata_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_profiled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class DatasetField(Base):
    __tablename__ = "dataset_fields"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="CASCADE",
            name="fk_dataset_fields_dataset_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_dataset_fields_tenant_id"
        ),
        UniqueConstraint("dataset_id", "source_name", name="uq_dataset_fields_source_name"),
        Index("ix_dataset_fields_dataset_order", "dataset_id", "ordinal_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)
    physical_data_type: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_data_type: Mapped[str] = mapped_column(String(24), nullable=False)
    semantic_type: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(24), default="attribute", nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    classification: Mapped[str] = mapped_column(String(24), default="internal", nullable=False)
    default_aggregation: Mapped[str | None] = mapped_column(String(24))
    format: Mapped[dict[str, object]] = mapped_column(
        "display_format", JSON, default=dict, nullable=False
    )
    timezone: Mapped[str | None] = mapped_column(String(80))
    precision: Mapped[int | None] = mapped_column(Integer)
    scale: Mapped[int | None] = mapped_column(Integer)
    max_length: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class DatasetQualityRule(Base):
    __tablename__ = "dataset_quality_rules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="CASCADE",
            name="fk_quality_rules_dataset_tenant",
        ),
        Index("ix_quality_rules_tenant_dataset", "organization_id", "workspace_id", "dataset_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    field_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dataset_fields.id", ondelete="CASCADE")
    )
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="warning", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="not_evaluated", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DatasetQualityResult(Base):
    __tablename__ = "dataset_quality_results"
    __table_args__ = (
        Index("ix_quality_results_rule_evaluated", "quality_rule_id", "evaluated_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quality_rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dataset_quality_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    observed_value: Mapped[str | None] = mapped_column(String(255))
    expected_value: Mapped[str | None] = mapped_column(String(255))
    failure_count: Mapped[int | None] = mapped_column(BigInteger)
    sample_size: Mapped[int | None] = mapped_column(BigInteger)
    safe_message: Mapped[str | None] = mapped_column(String(500))
    execution_reference: Mapped[str | None] = mapped_column(String(160))
    evaluation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dataset_quality_evaluations.id", ondelete="CASCADE"),
    )
    issue_details: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)


class DatasetQualityEvaluation(Base):
    __tablename__ = "dataset_quality_evaluations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="CASCADE",
            name="fk_quality_evaluations_dataset_tenant",
        ),
        Index(
            "ix_quality_evaluations_dataset_created",
            "organization_id",
            "workspace_id",
            "dataset_id",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    score: Mapped[int | None] = mapped_column(Integer)
    total_rules: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passing: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failing: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unknown: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DatasetLineageEdge(Base):
    __tablename__ = "dataset_lineage_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "source_dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="RESTRICT",
            name="fk_lineage_source_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "target_dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="RESTRICT",
            name="fk_lineage_target_tenant",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "source_dataset_id",
            "target_dataset_id",
            "lineage_type",
            name="uq_lineage_edge",
        ),
        CheckConstraint("source_dataset_id <> target_dataset_id", name="lineage_no_self_reference"),
        Index("ix_lineage_source", "organization_id", "workspace_id", "source_dataset_id"),
        Index("ix_lineage_target", "organization_id", "workspace_id", "target_dataset_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    lineage_type: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), default="manual", nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    edge_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
