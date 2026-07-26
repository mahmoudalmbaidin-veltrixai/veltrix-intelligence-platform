"""pipeline backend

Revision ID: 20260722_0007
Revises: 1883cb49e703
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0007"
down_revision: str | None = "1883cb49e703"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.Uuid()
TZ = sa.DateTime(timezone=True)


def tenant_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "pipelines",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("published_version_id", UUID),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("canvas", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("archived_at", TZ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_pipelines_workspace_tenant",
        ),
        sa.UniqueConstraint("organization_id", "workspace_id", "id", name="uq_pipelines_tenant_id"),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "slug", name="uq_pipelines_tenant_slug"
        ),
    )
    op.create_index(
        "ix_pipelines_tenant_status", "pipelines", ["organization_id", "workspace_id", "status"]
    )
    op.create_table(
        "pipeline_nodes",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("pipeline_id", UUID, nullable=False),
        sa.Column("node_key", sa.String(100), nullable=False),
        sa.Column("node_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("position_x", sa.Float(), nullable=False),
        sa.Column("position_y", sa.Float(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_nodes_pipeline_tenant",
        ),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_nodes_tenant_id"
        ),
        sa.UniqueConstraint("pipeline_id", "node_key", name="uq_pipeline_nodes_key"),
    )
    op.create_table(
        "pipeline_edges",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("pipeline_id", UUID, nullable=False),
        sa.Column("edge_key", sa.String(100), nullable=False),
        sa.Column("source_node_key", sa.String(100), nullable=False),
        sa.Column("target_node_key", sa.String(100), nullable=False),
        sa.Column("source_port", sa.String(100)),
        sa.Column("target_port", sa.String(100)),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_edges_pipeline_tenant",
        ),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_edges_tenant_id"
        ),
        sa.UniqueConstraint("pipeline_id", "edge_key", name="uq_pipeline_edges_key"),
    )
    op.create_table(
        "pipeline_versions",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("pipeline_id", UUID, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("change_summary", sa.String(500), nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_versions_pipeline_tenant",
        ),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_versions_tenant_id"
        ),
        sa.UniqueConstraint("pipeline_id", "version_number", name="uq_pipeline_versions_number"),
    )
    op.create_foreign_key(
        "fk_pipelines_published_version",
        "pipelines",
        "pipeline_versions",
        ["published_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("pipeline_id", UUID, nullable=False),
        sa.Column("pipeline_version_id", UUID, nullable=False),
        sa.Column(
            "requested_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("current_attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("available_at", TZ, nullable=False),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_expires_at", TZ),
        sa.Column("safe_error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("rows_processed", sa.BigInteger(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("started_at", TZ),
        sa.Column("completed_at", TZ),
        sa.Column("updated_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.workspace_id", "pipelines.id"],
            ondelete="CASCADE",
            name="fk_pipeline_runs_pipeline_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "pipeline_version_id"],
            [
                "pipeline_versions.organization_id",
                "pipeline_versions.workspace_id",
                "pipeline_versions.id",
            ],
            ondelete="RESTRICT",
            name="fk_pipeline_runs_version_tenant",
        ),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_runs_tenant_id"
        ),
    )
    op.create_index(
        "ix_pipeline_runs_worker_queue", "pipeline_runs", ["status", "available_at", "created_at"]
    )
    op.create_index(
        "ix_pipeline_runs_history",
        "pipeline_runs",
        ["organization_id", "workspace_id", "pipeline_id", "created_at"],
    )
    op.create_table(
        "pipeline_run_attempts",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("completed_at", TZ),
        sa.Column("safe_error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_attempts_run_tenant",
        ),
        sa.UniqueConstraint("run_id", "attempt_number", name="uq_pipeline_attempt_number"),
    )
    op.create_table(
        "pipeline_node_runs",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("node_key", sa.String(100), nullable=False),
        sa.Column("node_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("rows_in", sa.BigInteger(), nullable=False),
        sa.Column("rows_out", sa.BigInteger(), nullable=False),
        sa.Column("started_at", TZ),
        sa.Column("completed_at", TZ),
        sa.Column("safe_error_code", sa.String(80)),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_node_runs_run_tenant",
        ),
        sa.UniqueConstraint("run_id", "attempt_number", "node_key", name="uq_pipeline_node_run"),
    )
    op.create_table(
        "pipeline_run_logs",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("node_key", sa.String(100)),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_logs_run_tenant",
        ),
    )
    op.create_index("ix_pipeline_logs_cursor", "pipeline_run_logs", ["run_id", "sequence"])
    op.create_table(
        "pipeline_artifacts",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("node_key", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_artifacts_run_tenant",
        ),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_pipeline_artifacts_tenant_id"
        ),
    )
    op.create_table(
        "pipeline_outbox_events",
        sa.Column("id", UUID, primary_key=True),
        *tenant_columns(),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("published_at", TZ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["pipeline_runs.organization_id", "pipeline_runs.workspace_id", "pipeline_runs.id"],
            ondelete="CASCADE",
            name="fk_pipeline_outbox_run_tenant",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "run_id",
            "event_type",
            "attempt_number",
            name="uq_pipeline_outbox_delivery",
        ),
    )
    op.create_index(
        "ix_pipeline_outbox_pending", "pipeline_outbox_events", ["published_at", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_outbox_pending", table_name="pipeline_outbox_events")
    op.drop_table("pipeline_outbox_events")
    op.drop_table("pipeline_artifacts")
    op.drop_index("ix_pipeline_logs_cursor", table_name="pipeline_run_logs")
    op.drop_table("pipeline_run_logs")
    op.drop_table("pipeline_node_runs")
    op.drop_table("pipeline_run_attempts")
    op.drop_index("ix_pipeline_runs_history", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_worker_queue", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_constraint("fk_pipelines_published_version", "pipelines", type_="foreignkey")
    op.drop_table("pipeline_versions")
    op.drop_table("pipeline_edges")
    op.drop_table("pipeline_nodes")
    op.drop_index("ix_pipelines_tenant_status", table_name="pipelines")
    op.drop_table("pipelines")
