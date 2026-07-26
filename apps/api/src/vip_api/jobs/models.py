"""Normalized, tenant-qualified durable job records."""

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
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.auth.models import utc_now
from vip_api.database.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_jobs_workspace_tenant",
        ),
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_jobs_tenant_id"),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "job_type",
            "idempotency_key",
            name="uq_jobs_tenant_idempotency",
        ),
        CheckConstraint("priority BETWEEN -100 AND 100", name="jobs_priority_range"),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="jobs_progress_range"),
        CheckConstraint("max_attempts BETWEEN 1 AND 100", name="jobs_attempt_limit"),
        Index(
            "ix_jobs_queue_claim",
            "queue_name",
            "status",
            "available_at",
            "priority",
            "created_at",
        ),
        Index(
            "ix_jobs_tenant_history",
            "organization_id",
            "workspace_id",
            "created_at",
            "id",
        ),
        Index("ix_jobs_creator_history", "created_by_user_id", "created_at"),
        Index("ix_jobs_lease_recovery", "status", "lease_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    handler: Mapped[str] = mapped_column(String(160), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(80), default="default", nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_total_steps: Mapped[int | None] = mapped_column(Integer)
    progress_stage: Mapped[str | None] = mapped_column(String(120))
    progress_message: Mapped[str | None] = mapped_column(String(500))
    estimated_completion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_strategy: Mapped[str] = mapped_column(String(24), default="exponential", nullable=False)
    retry_base_seconds: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    retry_max_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    current_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(120))
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobPayload(Base):
    __tablename__ = "job_payloads"
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
        Index("ix_job_attempts_job_created", "job_id", "started_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="running", nullable=False)
    worker_id: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    error_code: Mapped[str | None] = mapped_column(String(100))


class JobProgress(Base):
    __tablename__ = "job_progress"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_job_progress_sequence"),
        Index("ix_job_progress_job_sequence", "job_id", "sequence"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_steps: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[str | None] = mapped_column(String(120))
    message: Mapped[str | None] = mapped_column(String(500))
    estimated_completion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class JobLog(Base):
    __tablename__ = "job_logs"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_job_logs_sequence"),
        Index("ix_job_logs_job_sequence", "job_id", "sequence"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    context: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class JobError(Base):
    __tablename__ = "job_errors"
    __table_args__ = (Index("ix_job_errors_job_created", "job_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    safe_message: Mapped[str] = mapped_column(String(500), nullable=False)
    exception_type: Mapped[str | None] = mapped_column(String(200))
    stack_trace: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_dead_letter_jobs_job"),
        Index("ix_dead_letter_tenant_created", "organization_id", "workspace_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    failure_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    last_error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(120))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    retried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobResult(Base):
    __tablename__ = "job_results"
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    result: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    result_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL")
    )
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (Index("ix_worker_heartbeats_queue_seen", "queue_name", "last_seen_at"),)
    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    queue_name: Mapped[str] = mapped_column(String(80), nullable=False)
    hostname: Mapped[str] = mapped_column(String(200), nullable=False)
    process_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="starting", nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    shutdown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
