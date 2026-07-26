"""Durable B7 pipeline, version, queue, run, and artifact records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.auth.models import utc_now
from vip_api.database.base import Base


class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_pipelines_workspace_tenant",
        ),
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_pipelines_tenant_id"),
        UniqueConstraint(
            "organization_id", "workspace_id", "slug", name="uq_pipelines_tenant_slug"
        ),
        Index("ix_pipelines_tenant_status", "organization_id", "workspace_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    published_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "pipeline_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_pipelines_published_version",
        ),
    )
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    canvas: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PipelineNode(Base):
    __tablename__ = "pipeline_nodes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_nodes_pipeline_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_nodes_tenant_id"
        ),
        UniqueConstraint("pipeline_id", "node_key", name="uq_pipeline_nodes_key"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position_x: Mapped[float] = mapped_column(nullable=False)
    position_y: Mapped[float] = mapped_column(nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class PipelineEdge(Base):
    __tablename__ = "pipeline_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_edges_pipeline_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_edges_tenant_id"
        ),
        UniqueConstraint("pipeline_id", "edge_key", name="uq_pipeline_edges_key"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    edge_key: Mapped[str] = mapped_column(String(100), nullable=False)
    source_node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    target_node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    source_port: Mapped[str | None] = mapped_column(String(100))
    target_port: Mapped[str | None] = mapped_column(String(100))


class PipelineVersion(Base):
    __tablename__ = "pipeline_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_versions_pipeline_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_versions_tenant_id"
        ),
        UniqueConstraint("pipeline_id", "version_number", name="uq_pipeline_versions_number"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    change_summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_runs_pipeline_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_version_id"],
            [
                "pipeline_versions.organization_id",
                "pipeline_versions.workspace_id",
                "pipeline_versions.id",
            ],
            ondelete="RESTRICT",
            name="fk_pipeline_runs_version_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_runs_tenant_id"
        ),
        Index("ix_pipeline_runs_worker_queue", "status", "available_at", "created_at"),
        Index(
            "ix_pipeline_runs_history",
            "organization_id",
            "workspace_id",
            "pipeline_id",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_version_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(24), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    rows_processed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    result_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PipelineRunAttempt(Base):
    __tablename__ = "pipeline_run_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_attempts_run_tenant",
        ),
        UniqueConstraint("run_id", "attempt_number", name="uq_pipeline_attempt_number"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))


class PipelineNodeRun(Base):
    __tablename__ = "pipeline_node_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_node_runs_run_tenant",
        ),
        UniqueConstraint("run_id", "attempt_number", "node_key", name="uq_pipeline_node_run"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    rows_in: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rows_out: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))


class PipelineRunLog(Base):
    __tablename__ = "pipeline_run_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_logs_run_tenant",
        ),
        Index("ix_pipeline_logs_cursor", "run_id", "sequence"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_key: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PipelineArtifact(Base):
    __tablename__ = "pipeline_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_artifacts_run_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_artifacts_tenant_id"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PipelineOutboxEvent(Base):
    __tablename__ = "pipeline_outbox_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_outbox_run_tenant",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "run_id",
            "event_type",
            "attempt_number",
            name="uq_pipeline_outbox_delivery",
        ),
        Index("ix_pipeline_outbox_pending", "published_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
