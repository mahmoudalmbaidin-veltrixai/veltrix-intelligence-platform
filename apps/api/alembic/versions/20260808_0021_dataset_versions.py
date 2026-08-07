"""Dataset schema/metadata version snapshots (post-Core P2).

Revision ID: 20260808_0021
Revises: 20260808_0020
Create Date: 2026-08-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0021"
down_revision: str | None = "20260808_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_type", sa.String(length=32), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.String(length=500), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            name="fk_dataset_versions_dataset_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_dataset_versions_creator",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_versions_number"),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_dataset_versions_tenant_id"
        ),
    )
    op.create_index(
        "ix_dataset_versions_history", "dataset_versions", ["dataset_id", "version_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_versions_history", table_name="dataset_versions")
    op.drop_table("dataset_versions")
