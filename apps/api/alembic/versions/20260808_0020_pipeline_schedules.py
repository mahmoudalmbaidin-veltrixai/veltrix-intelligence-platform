"""Pipeline run schedules + schedule-run history (post-Core P1).

Revision ID: 20260808_0020
Revises: 20260803_0019
Create Date: 2026-08-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0020"
down_revision: str | None = "20260803_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_version_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("schedule_type", sa.String(length=16), nullable=False),
        sa.Column("schedule_expression", sa.String(length=120), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            name="fk_pipeline_schedules_pipeline_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_pipeline_schedules_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_schedules_tenant_id"
        ),
    )
    op.create_index("ix_pipeline_schedules_due", "pipeline_schedules", ["enabled", "next_run_at"])
    op.create_index(
        "ix_pipeline_schedules_tenant_pipeline",
        "pipeline_schedules",
        ["organization_id", "workspace_id", "pipeline_id"],
    )
    op.create_table(
        "pipeline_schedule_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("safe_error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "schedule_id"],
            [
                "pipeline_schedules.organization_id",
                "pipeline_schedules.workspace_id",
                "pipeline_schedules.id",
            ],
            name="fk_pipeline_schedule_runs_schedule_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_schedule_runs_history",
        "pipeline_schedule_runs",
        ["schedule_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_schedule_runs_history", table_name="pipeline_schedule_runs")
    op.drop_table("pipeline_schedule_runs")
    op.drop_index("ix_pipeline_schedules_tenant_pipeline", table_name="pipeline_schedules")
    op.drop_index("ix_pipeline_schedules_due", table_name="pipeline_schedules")
    op.drop_table("pipeline_schedules")
