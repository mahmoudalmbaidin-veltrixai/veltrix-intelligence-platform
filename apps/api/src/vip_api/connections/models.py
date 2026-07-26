"""Persistent connection catalog, resources, and immutable credential versions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.auth.models import utc_now
from vip_api.database.base import Base


class ConnectionType(Base):
    __tablename__ = "connection_types"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    configuration_schema: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    secret_schema: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    test_strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ConnectionSecret(Base):
    __tablename__ = "connection_secrets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "connection_id",
            "credential_version",
            name="uq_connection_secret_version",
        ),
        Index(
            "ix_connection_secrets_tenant_connection",
            "organization_id",
            "workspace_id",
            "connection_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("connections.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_algorithm: Mapped[str] = mapped_column(String(40), nullable=False)
    key_version: Mapped[str] = mapped_column(String(40), nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, nullable=False)
    secret_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_connections_tenant_id"),
        Index("ix_connections_tenant_status", "organization_id", "workspace_id", "status"),
        Index("ix_connections_tenant_health", "organization_id", "workspace_id", "health_status"),
        Index(
            "uq_connections_active_name",
            "organization_id",
            "workspace_id",
            "normalized_name",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        CheckConstraint("version > 0", name="connections_positive_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    connection_type_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("connection_types.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    health_status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    secret_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "connection_secrets.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_connections_secret_id_connection_secrets",
        ),
        nullable=True,
    )
    credential_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connection_type_version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(20))
    last_test_error_code: Mapped[str | None] = mapped_column(String(80))
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_healthy_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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
