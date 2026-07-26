"""Immutable semantic model publication snapshots.

Revision ID: 20260725_0010
Revises: 20260725_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0010"
down_revision: str | None = "20260725_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "semantic_model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("semantic_model_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["semantic_model_id"], ["semantic_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "semantic_model_id",
            "version_number",
            name="uq_semantic_model_versions_number",
        ),
    )
    op.create_index(
        "ix_semantic_model_versions_tenant",
        "semantic_model_versions",
        ["organization_id", "workspace_id", "semantic_model_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_semantic_model_versions_tenant", table_name="semantic_model_versions")
    op.drop_table("semantic_model_versions")
