"""Durable B6.5 export and delivery records."""

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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.auth.models import utc_now
from vip_api.database.base import Base


class DashboardExport(Base):
    """A durable, worker-consumable export job compatible with future common jobs."""

    __tablename__ = "dashboard_exports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_exports_dashboard_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_version_id"],
            [
                "dashboard_versions.organization_id",
                "dashboard_versions.workspace_id",
                "dashboard_versions.id",
            ],
            ondelete="RESTRICT",
            name="fk_dashboard_exports_version_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_dashboard_exports_tenant_id"
        ),
        Index(
            "ix_dashboard_exports_worker_queue",
            "status",
            "available_at",
            "created_at",
        ),
        Index(
            "ix_dashboard_exports_tenant_dashboard",
            "organization_id",
            "workspace_id",
            "dashboard_id",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_version_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    delivery_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    platform_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), unique=True
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    filters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    locale: Mapped[str] = mapped_column(String(32), default="en-US", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_key: Mapped[str | None] = mapped_column(String(500))
    artifact_content_type: Mapped[str | None] = mapped_column(String(100))
    artifact_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DashboardDeliverySchedule(Base):
    """Scheduler-ready immutable-version delivery definition."""

    __tablename__ = "dashboard_delivery_schedules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_delivery_schedules_dashboard_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_version_id"],
            [
                "dashboard_versions.organization_id",
                "dashboard_versions.workspace_id",
                "dashboard_versions.id",
            ],
            ondelete="RESTRICT",
            name="fk_dashboard_delivery_schedules_version_tenant",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "id",
            name="uq_dashboard_delivery_schedules_tenant_id",
        ),
        Index(
            "ix_dashboard_delivery_schedules_due",
            "enabled",
            "next_run_at",
        ),
        Index(
            "ix_dashboard_delivery_schedules_tenant_dashboard",
            "organization_id",
            "workspace_id",
            "dashboard_id",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_version_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    cc: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bcc: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    filters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(16), nullable=False)
    schedule_expression: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    include_dashboard_link: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="scheduled", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DashboardDeliveryRun(Base):
    """One auditable delivery attempt, optionally linked to an export job."""

    __tablename__ = "dashboard_delivery_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "schedule_id"],
            [
                "dashboard_delivery_schedules.organization_id",
                "dashboard_delivery_schedules.workspace_id",
                "dashboard_delivery_schedules.id",
            ],
            ondelete="CASCADE",
            name="fk_dashboard_delivery_runs_schedule_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "export_id"],
            [
                "dashboard_exports.organization_id",
                "dashboard_exports.workspace_id",
                "dashboard_exports.id",
            ],
            name="fk_dashboard_delivery_runs_export_tenant",
        ),
        Index(
            "ix_dashboard_delivery_runs_history",
            "organization_id",
            "workspace_id",
            "schedule_id",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    schedule_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    export_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
