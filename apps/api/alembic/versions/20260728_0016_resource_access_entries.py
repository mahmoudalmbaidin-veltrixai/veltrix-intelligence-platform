"""Reusable resource ACL foundation (Slice A authorization foundation).

Additive: creates the tenant-scoped resource_access_entries table used by the
explainable resource-access evaluation service. No existing data is modified and
no existing decision path changes.

Revision ID: 20260728_0016
Revises: 20260728_0015
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0016"
down_revision: str | None = "20260728_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_access_entries",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("access_level", sa.String(length=32), nullable=False),
        sa.Column("effect", sa.String(length=8), nullable=False, server_default="allow"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "granted_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "resource_type",
            "resource_id",
            "subject_type",
            "subject_id",
            "access_level",
            "effect",
            name="uq_resource_access_unique_entry",
        ),
    )
    op.create_index(
        "ix_resource_access_resource",
        "resource_access_entries",
        ["organization_id", "workspace_id", "resource_type", "resource_id"],
    )
    op.create_index(
        "ix_resource_access_subject",
        "resource_access_entries",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_resource_access_expires",
        "resource_access_entries",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_resource_access_expires", table_name="resource_access_entries")
    op.drop_index("ix_resource_access_subject", table_name="resource_access_entries")
    op.drop_index("ix_resource_access_resource", table_name="resource_access_entries")
    op.drop_table("resource_access_entries")
