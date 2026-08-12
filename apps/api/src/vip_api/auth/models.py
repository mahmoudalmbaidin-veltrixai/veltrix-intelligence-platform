"""Persistent authentication models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.database.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_username(username: str) -> str:
    """Canonical form for globally-unique username lookups (case-insensitive)."""
    return username.strip().casefold()


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"
    SUSPENDED = "suspended"
    DELETED = "deleted"


user_status_enum = Enum(
    UserStatus,
    name="vip_user_status",
    native_enum=True,
    values_callable=lambda statuses: [status.value for status in statuses],
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Username is the globally-unique primary login identifier.
        Index("uq_users_normalized_username", "normalized_username", unique=True),
        # Email is optional; uniqueness is enforced only when a value is present.
        Index(
            "uq_users_normalized_email_present",
            "normalized_email",
            unique=True,
            postgresql_where=text("normalized_email IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_username: Mapped[str] = mapped_column(String(150), nullable=False)
    # Email is optional (nullable). Never store a placeholder; NULL means "no email".
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    normalized_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        user_status_enum, default=UserStatus.ACTIVE, nullable=False
    )
    account_type: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    is_platform_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Enterprise profile fields (all optional).
    default_organization_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    default_workspace_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    locale: Mapped[str | None] = mapped_column(String(20))
    timezone: Mapped[str | None] = mapped_column(String(64))
    job_title: Mapped[str | None] = mapped_column(String(150))
    department: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(50))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    # Self-service UI preferences (theme, density, reduced motion, date/time
    # format, etc.). A single JSON bag keeps personalization additive without a
    # migration per preference. locale/timezone remain first-class columns above.
    preferences: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    created_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    updated_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_active", "user_id", "revoked_at", "refresh_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(100))
    rotated_from_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("auth_sessions.id", ondelete="SET NULL"), index=True
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_tokens_user_active", "user_id", "used_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    requested_ip_hash: Mapped[str | None] = mapped_column(String(64))
