"""Persistence for per-user notification read state.

Notifications themselves are a tenant-scoped, derived projection of jobs (they
are not stored rows), so read state cannot live on a notification row. Instead
each user records which notification ids they have read. Unread is then
"feed item whose id has no read marker for this user". Read state is strictly
per-user and survives logout/login and refresh.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from vip_api.database.base import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class NotificationRead(Base):
    __tablename__ = "notification_reads"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "notification_id", name="uq_notification_reads_user_notification"
        ),
        Index("ix_notification_reads_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The derived feed id, e.g. "job:<uuid>:<row_version>". Stored as text because
    # a notification is not a real row and its id encodes the source + version.
    notification_id: Mapped[str] = mapped_column(String(200), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
