"""Persistent semantic-layer and business-glossary models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.auth.models import utc_now
from vip_api.database.base import Base


class SemanticModel(Base):
    __tablename__ = "semantic_models"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "primary_dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="RESTRICT",
            name="fk_semantic_models_primary_dataset_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_semantic_models_tenant_id"
        ),
        UniqueConstraint("organization_id", "workspace_id", "key", name="uq_semantic_models_key"),
        Index("ix_semantic_models_tenant_status", "organization_id", "workspace_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    primary_dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    published_version: Mapped[int | None] = mapped_column(Integer)
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


class SemanticModelVersion(Base):
    __tablename__ = "semantic_model_versions"
    __table_args__ = (
        UniqueConstraint(
            "semantic_model_id", "version_number", name="uq_semantic_model_versions_number"
        ),
        Index(
            "ix_semantic_model_versions_tenant",
            "organization_id",
            "workspace_id",
            "semantic_model_id",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SemanticModelDataset(Base):
    __tablename__ = "semantic_model_datasets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "semantic_model_id"],
            [
                "semantic_models.organization_id",
                "semantic_models.workspace_id",
                "semantic_models.id",
            ],
            ondelete="CASCADE",
            name="fk_model_datasets_model_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="RESTRICT",
            name="fk_model_datasets_dataset_tenant",
        ),
        UniqueConstraint("semantic_model_id", "dataset_id", name="uq_model_datasets_dataset"),
        UniqueConstraint("semantic_model_id", "alias", name="uq_model_datasets_alias"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(24), default="primary", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SemanticJoin(Base):
    __tablename__ = "semantic_joins"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "semantic_model_id"],
            [
                "semantic_models.organization_id",
                "semantic_models.workspace_id",
                "semantic_models.id",
            ],
            ondelete="CASCADE",
            name="fk_semantic_joins_model_tenant",
        ),
        UniqueConstraint(
            "semantic_model_id", "left_dataset_id", "right_dataset_id", name="uq_semantic_join_path"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    left_dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    right_dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    left_field_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dataset_fields.id", ondelete="CASCADE"), nullable=False
    )
    right_field_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dataset_fields.id", ondelete="CASCADE"), nullable=False
    )
    join_type: Mapped[str] = mapped_column(String(16), nullable=False)
    relationship: Mapped[str] = mapped_column(String(24), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SemanticDimension(Base):
    __tablename__ = "semantic_dimensions"
    __table_args__ = (
        UniqueConstraint("semantic_model_id", "key", name="uq_semantic_dimensions_key"),
        Index("ix_semantic_dimensions_model", "semantic_model_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dataset_fields.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    dimension_type: Mapped[str] = mapped_column(String(24), nullable=False)
    data_type: Mapped[str] = mapped_column(String(24), nullable=False)
    is_time_dimension: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    time_granularities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    format: Mapped[dict[str, object]] = mapped_column(
        "display_format", JSON, default=dict, nullable=False
    )
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SemanticMeasure(Base):
    __tablename__ = "semantic_measures"
    __table_args__ = (
        UniqueConstraint("semantic_model_id", "key", name="uq_semantic_measures_key"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dataset_fields.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    aggregation: Mapped[str] = mapped_column(String(24), nullable=False)
    data_type: Mapped[str] = mapped_column(String(24), nullable=False)
    format: Mapped[dict[str, object]] = mapped_column(
        "display_format", JSON, default=dict, nullable=False
    )
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    filters: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SemanticMetric(Base):
    __tablename__ = "semantic_metrics"
    __table_args__ = (UniqueConstraint("semantic_model_id", "key", name="uq_semantic_metrics_key"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    metric_type: Mapped[str] = mapped_column(String(24), nullable=False)
    base_measure_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_measures.id", ondelete="RESTRICT")
    )
    numerator_metric_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_metrics.id", ondelete="RESTRICT")
    )
    denominator_metric_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_metrics.id", ondelete="RESTRICT")
    )
    format: Mapped[dict[str, object]] = mapped_column(
        "display_format", JSON, default=dict, nullable=False
    )
    unit: Mapped[str | None] = mapped_column(String(40))
    target_direction: Mapped[str | None] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SemanticKpi(Base):
    __tablename__ = "semantic_kpis"
    __table_args__ = (UniqueConstraint("semantic_model_id", "key", name="uq_semantic_kpis_key"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False
    )
    metric_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("semantic_metrics.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    warning_threshold: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    critical_threshold: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    comparison_operator: Mapped[str] = mapped_column(String(32), nullable=False)
    target_period: Mapped[str | None] = mapped_column(String(40))
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class GlossaryDomain(Base):
    __tablename__ = "glossary_domains"
    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "key", name="uq_glossary_domains_key"),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_glossary_domains_tenant_id"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "domain_id"],
            [
                "glossary_domains.organization_id",
                "glossary_domains.workspace_id",
                "glossary_domains.id",
            ],
            ondelete="CASCADE",
            name="fk_glossary_terms_domain_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_glossary_terms_tenant_id"
        ),
        UniqueConstraint("organization_id", "workspace_id", "key", name="uq_glossary_terms_key"),
        Index("ix_glossary_terms_search", "organization_id", "workspace_id", "name"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    domain_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    definition: Mapped[str] = mapped_column(String(4000), nullable=False)
    business_owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    data_steward_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    examples: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(160), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class GlossaryTermRelationship(Base):
    __tablename__ = "glossary_term_relationships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "source_term_id"],
            ["glossary_terms.organization_id", "glossary_terms.workspace_id", "glossary_terms.id"],
            ondelete="CASCADE",
            name="fk_glossary_rel_source_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "target_term_id"],
            ["glossary_terms.organization_id", "glossary_terms.workspace_id", "glossary_terms.id"],
            ondelete="CASCADE",
            name="fk_glossary_rel_target_tenant",
        ),
        UniqueConstraint(
            "source_term_id", "target_term_id", "relationship_type", name="uq_glossary_relationship"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(24), nullable=False)


class GlossaryAssignment(Base):
    __tablename__ = "glossary_assignments"
    __table_args__ = (
        UniqueConstraint("term_id", "resource_type", "resource_id", name="uq_glossary_assignment"),
        Index(
            "ix_glossary_assignments_resource",
            "organization_id",
            "workspace_id",
            "resource_type",
            "resource_id",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    term_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("glossary_terms.id", ondelete="CASCADE"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
