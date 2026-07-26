"""Persistent Dashboard Studio aggregate models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
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


class Dashboard(Base):
    __tablename__ = "dashboards"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_dashboards_workspace_tenant",
        ),
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_dashboards_tenant_id"),
        UniqueConstraint(
            "organization_id", "workspace_id", "slug", name="uq_dashboards_tenant_slug"
        ),
        Index("ix_dashboards_tenant_status", "organization_id", "workspace_id", "status"),
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
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    default_page_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    published_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DashboardPage(Base):
    __tablename__ = "dashboard_pages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_pages_dashboard_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_dashboard_pages_tenant_id"
        ),
        UniqueConstraint("dashboard_id", "page_key", name="uq_dashboard_pages_key"),
        UniqueConstraint("dashboard_id", "position", name="uq_dashboard_pages_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    page_key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class DashboardWidget(Base):
    __tablename__ = "dashboard_widgets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_widgets_dashboard_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "page_id"],
            [
                "dashboard_pages.organization_id",
                "dashboard_pages.workspace_id",
                "dashboard_pages.id",
            ],
            ondelete="CASCADE",
            name="fk_dashboard_widgets_page_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "semantic_model_id"],
            [
                "semantic_models.organization_id",
                "semantic_models.workspace_id",
                "semantic_models.id",
            ],
            ondelete="RESTRICT",
            name="fk_dashboard_widgets_semantic_model_tenant",
        ),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_dashboard_widgets_tenant_id"
        ),
        Index("ix_dashboard_widgets_page", "dashboard_id", "page_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    page_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    widget_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    semantic_model_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    query_definition: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    visualization_config: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    layout: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    filters: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    interactions: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    content: Mapped[str | None] = mapped_column(String(10000))
    is_hidden: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class DashboardFilter(Base):
    __tablename__ = "dashboard_filters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_filters_dashboard_tenant",
        ),
        UniqueConstraint("dashboard_id", "filter_key", name="uq_dashboard_filters_key"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    filter_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    filter_type: Mapped[str] = mapped_column(String(32), nullable=False)
    semantic_model_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dimension_key: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(32), nullable=False)
    default_value: Mapped[object | None] = mapped_column(JSON)
    widget_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class DashboardVersion(Base):
    __tablename__ = "dashboard_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_versions_dashboard_tenant",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "id",
            name="uq_dashboard_versions_tenant_id",
        ),
        UniqueConstraint("dashboard_id", "version_number", name="uq_dashboard_versions_number"),
        Index("ix_dashboard_versions_history", "dashboard_id", "version_number"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_type: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    source_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dashboard_versions.id", ondelete="SET NULL")
    )


class DashboardShare(Base):
    __tablename__ = "dashboard_shares"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_shares_dashboard_tenant",
        ),
        UniqueConstraint(
            "dashboard_id", "principal_type", "principal_id", name="uq_dashboard_shares_principal"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    principal_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DashboardSnapshot(Base):
    __tablename__ = "dashboard_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            ondelete="CASCADE",
            name="fk_dashboard_snapshots_dashboard_tenant",
        ),
        Index("ix_dashboard_snapshots_dashboard", "dashboard_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dashboard_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dashboard_versions.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    filter_state: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    data_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ready", nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
