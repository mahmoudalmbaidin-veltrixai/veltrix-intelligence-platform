"""dataset quality evaluation history

Revision ID: 20260725_0009
Revises: 20260725_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0009"
down_revision: str | None = "20260725_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.Uuid()
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "dataset_quality_evaluations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("dataset_id", UUID, nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("total_rules", sa.Integer(), nullable=False),
        sa.Column("passing", sa.Integer(), nullable=False),
        sa.Column("warning", sa.Integer(), nullable=False),
        sa.Column("failing", sa.Integer(), nullable=False),
        sa.Column("unknown", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("started_at", TZ),
        sa.Column("completed_at", TZ),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dataset_id"],
            ["datasets.organization_id", "datasets.workspace_id", "datasets.id"],
            ondelete="CASCADE",
            name="fk_quality_evaluations_dataset_tenant",
        ),
    )
    op.create_index(
        "ix_quality_evaluations_dataset_created",
        "dataset_quality_evaluations",
        ["organization_id", "workspace_id", "dataset_id", "created_at"],
    )
    op.add_column(
        "dataset_quality_results",
        sa.Column(
            "evaluation_id",
            UUID,
            sa.ForeignKey("dataset_quality_evaluations.id", ondelete="CASCADE"),
        ),
    )
    op.add_column(
        "dataset_quality_results",
        sa.Column("issue_details", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("dataset_quality_results", sa.Column("duration_ms", sa.BigInteger()))


def downgrade() -> None:
    op.drop_column("dataset_quality_results", "duration_ms")
    op.drop_column("dataset_quality_results", "issue_details")
    op.drop_column("dataset_quality_results", "evaluation_id")
    op.drop_index(
        "ix_quality_evaluations_dataset_created",
        table_name="dataset_quality_evaluations",
    )
    op.drop_table("dataset_quality_evaluations")
