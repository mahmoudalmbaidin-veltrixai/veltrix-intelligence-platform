"""dashboard exports and deliveries

Revision ID: 1883cb49e703
Revises: c3dd2191427c
Create Date: 2026-07-22 14:50:03.002424
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1883cb49e703"
down_revision: str | None = "c3dd2191427c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_dashboard_versions_tenant_id",
        "dashboard_versions",
        ["organization_id", "workspace_id", "id"],
    )
    op.create_table(
        "dashboard_delivery_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dashboard_id", sa.Uuid(), nullable=False),
        sa.Column("dashboard_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("cc", sa.JSON(), nullable=False),
        sa.Column("bcc", sa.JSON(), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("schedule_type", sa.String(length=16), nullable=False),
        sa.Column("schedule_expression", sa.String(length=120), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("include_dashboard_link", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_dashboard_delivery_schedules_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            name="fk_dashboard_delivery_schedules_dashboard_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_version_id"],
            [
                "dashboard_versions.organization_id",
                "dashboard_versions.workspace_id",
                "dashboard_versions.id",
            ],
            name="fk_dashboard_delivery_schedules_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dashboard_delivery_schedules")),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "id",
            name="uq_dashboard_delivery_schedules_tenant_id",
        ),
    )
    op.create_index(
        "ix_dashboard_delivery_schedules_due",
        "dashboard_delivery_schedules",
        ["enabled", "next_run_at"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_delivery_schedules_tenant_dashboard",
        "dashboard_delivery_schedules",
        ["organization_id", "workspace_id", "dashboard_id"],
        unique=False,
    )
    op.create_table(
        "dashboard_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dashboard_id", sa.Uuid(), nullable=False),
        sa.Column("dashboard_version_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_run_id", sa.Uuid(), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artifact_key", sa.String(length=500), nullable=True),
        sa.Column("artifact_content_type", sa.String(length=100), nullable=True),
        sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("safe_error_message", sa.String(length=500), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_id"],
            ["dashboards.organization_id", "dashboards.workspace_id", "dashboards.id"],
            name="fk_dashboard_exports_dashboard_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dashboard_version_id"],
            [
                "dashboard_versions.organization_id",
                "dashboard_versions.workspace_id",
                "dashboard_versions.id",
            ],
            name="fk_dashboard_exports_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_dashboard_exports_requested_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dashboard_exports")),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_dashboard_exports_tenant_id"
        ),
    )
    op.create_index(
        "ix_dashboard_exports_tenant_dashboard",
        "dashboard_exports",
        ["organization_id", "workspace_id", "dashboard_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_exports_worker_queue",
        "dashboard_exports",
        ["status", "available_at", "created_at"],
        unique=False,
    )
    op.create_table(
        "dashboard_delivery_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("safe_error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "export_id"],
            [
                "dashboard_exports.organization_id",
                "dashboard_exports.workspace_id",
                "dashboard_exports.id",
            ],
            name="fk_dashboard_delivery_runs_export_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "schedule_id"],
            [
                "dashboard_delivery_schedules.organization_id",
                "dashboard_delivery_schedules.workspace_id",
                "dashboard_delivery_schedules.id",
            ],
            name="fk_dashboard_delivery_runs_schedule_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dashboard_delivery_runs")),
    )
    op.create_index(
        "ix_dashboard_delivery_runs_history",
        "dashboard_delivery_runs",
        ["organization_id", "workspace_id", "schedule_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_delivery_runs_history", table_name="dashboard_delivery_runs")
    op.drop_table("dashboard_delivery_runs")
    op.drop_index("ix_dashboard_exports_worker_queue", table_name="dashboard_exports")
    op.drop_index("ix_dashboard_exports_tenant_dashboard", table_name="dashboard_exports")
    op.drop_table("dashboard_exports")
    op.drop_index(
        "ix_dashboard_delivery_schedules_tenant_dashboard",
        table_name="dashboard_delivery_schedules",
    )
    op.drop_index("ix_dashboard_delivery_schedules_due", table_name="dashboard_delivery_schedules")
    op.drop_table("dashboard_delivery_schedules")
    op.drop_constraint("uq_dashboard_versions_tenant_id", "dashboard_versions", type_="unique")
