"""async jobs, files, and real-time platform infrastructure

Revision ID: 20260725_0008
Revises: 20260722_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0008"
down_revision: str | None = "20260722_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.Uuid()
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("handler", sa.String(160), nullable=False),
        sa.Column("queue_name", sa.String(80), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(64)),
        sa.Column(
            "created_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("started_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("cancelled_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("progress_step", sa.Integer(), nullable=False),
        sa.Column("progress_total_steps", sa.Integer()),
        sa.Column("progress_stage", sa.String(120)),
        sa.Column("progress_message", sa.String(500)),
        sa.Column("estimated_completion_at", TZ),
        sa.Column("retry_strategy", sa.String(24), nullable=False),
        sa.Column("retry_base_seconds", sa.Integer(), nullable=False),
        sa.Column("retry_max_seconds", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("current_attempt", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("worker_id", sa.String(120)),
        sa.Column("lease_owner", sa.String(120)),
        sa.Column("lease_expires_at", TZ),
        sa.Column("heartbeat_at", TZ),
        sa.Column("scheduled_at", TZ),
        sa.Column("available_at", TZ, nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("started_at", TZ),
        sa.Column("completed_at", TZ),
        sa.Column("cancelled_at", TZ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_jobs_workspace_tenant",
        ),
        sa.UniqueConstraint("organization_id", "workspace_id", "id", name="uq_jobs_tenant_id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "job_type",
            "idempotency_key",
            name="uq_jobs_tenant_idempotency",
        ),
        sa.CheckConstraint("priority BETWEEN -100 AND 100", name="jobs_priority_range"),
        sa.CheckConstraint("progress_percent BETWEEN 0 AND 100", name="jobs_progress_range"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 100", name="jobs_attempt_limit"),
    )
    op.create_index(
        "ix_jobs_queue_claim",
        "jobs",
        ["queue_name", "status", "available_at", "priority", "created_at"],
    )
    op.create_index(
        "ix_jobs_tenant_history", "jobs", ["organization_id", "workspace_id", "created_at", "id"]
    )
    op.create_index("ix_jobs_creator_history", "jobs", ["created_by_user_id", "created_at"])
    op.create_index("ix_jobs_lease_recovery", "jobs", ["status", "lease_expires_at"])

    op.create_table(
        "job_payloads",
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
    )
    op.create_table(
        "job_attempts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("worker_id", sa.String(120), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("completed_at", TZ),
        sa.Column("duration_ms", sa.BigInteger()),
        sa.Column("retryable", sa.Boolean()),
        sa.Column("error_code", sa.String(100)),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
    )
    op.create_index("ix_job_attempts_job_created", "job_attempts", ["job_id", "started_at"])
    op.create_table(
        "job_progress",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("percent", sa.Integer(), nullable=False),
        sa.Column("completed_steps", sa.Integer(), nullable=False),
        sa.Column("total_steps", sa.Integer()),
        sa.Column("stage", sa.String(120)),
        sa.Column("message", sa.String(500)),
        sa.Column("estimated_completion_at", TZ),
        sa.Column("created_at", TZ, nullable=False),
        sa.UniqueConstraint("job_id", "sequence", name="uq_job_progress_sequence"),
    )
    op.create_index("ix_job_progress_job_sequence", "job_progress", ["job_id", "sequence"])
    op.create_table(
        "job_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.UniqueConstraint("job_id", "sequence", name="uq_job_logs_sequence"),
    )
    op.create_index("ix_job_logs_job_sequence", "job_logs", ["job_id", "sequence"])
    op.create_table(
        "job_errors",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("safe_message", sa.String(500), nullable=False),
        sa.Column("exception_type", sa.String(200)),
        sa.Column("stack_trace", sa.Text()),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
    )
    op.create_index("ix_job_errors_job_created", "job_errors", ["job_id", "created_at"])
    op.create_table(
        "dead_letter_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("failure_reason", sa.String(500), nullable=False),
        sa.Column("last_error_code", sa.String(100), nullable=False),
        sa.Column("stack_trace", sa.Text()),
        sa.Column("worker_id", sa.String(120)),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("retried_at", TZ),
        sa.Column("discarded_at", TZ),
        sa.UniqueConstraint("job_id", name="uq_dead_letter_jobs_job"),
    )
    op.create_index(
        "ix_dead_letter_tenant_created",
        "dead_letter_jobs",
        ["organization_id", "workspace_id", "created_at"],
    )
    op.create_table(
        "job_results",
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("result_file_id", UUID),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ),
    )
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(120), primary_key=True),
        sa.Column("queue_name", sa.String(80), nullable=False),
        sa.Column("hostname", sa.String(200), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("active_jobs", sa.Integer(), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.Column("shutdown_at", TZ),
    )
    op.create_index(
        "ix_worker_heartbeats_queue_seen", "worker_heartbeats", ["queue_name", "last_seen_at"]
    )

    op.create_table(
        "files",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column(
            "created_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("file_kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("extension", sa.String(32), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("checksum", sa.String(128)),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("storage_provider", sa.String(32), nullable=False),
        sa.Column("storage_key", sa.String(600)),
        sa.Column("encryption_state", sa.String(24), nullable=False),
        sa.Column("retention_policy", sa.String(32), nullable=False),
        sa.Column("retention_until", TZ),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("deleted_at", TZ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_files_workspace_tenant",
        ),
        sa.UniqueConstraint("organization_id", "workspace_id", "id", name="uq_files_tenant_id"),
    )
    op.create_index(
        "ix_files_tenant_history", "files", ["organization_id", "workspace_id", "created_at", "id"]
    )
    op.create_index("ix_files_tenant_hash", "files", ["organization_id", "workspace_id", "sha256"])
    op.create_index("ix_files_retention", "files", ["status", "retention_until"])
    op.create_table(
        "file_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("storage_provider", sa.String(32), nullable=False),
        sa.Column("storage_key", sa.String(600), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("scan_status", sa.String(24), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.UniqueConstraint("file_id", "version_number", name="uq_file_versions_number"),
    )
    op.create_index("ix_file_versions_file_created", "file_versions", ["file_id", "created_at"])
    op.create_table(
        "file_uploads",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("bytes_received", sa.BigInteger(), nullable=False),
        sa.Column("safe_error_code", sa.String(100)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("completed_at", TZ),
    )
    op.create_index(
        "ix_file_uploads_tenant_created",
        "file_uploads",
        ["organization_id", "workspace_id", "created_at"],
    )
    op.create_table(
        "file_download_tokens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("used_at", TZ),
        sa.UniqueConstraint("token_hash", name="uq_file_download_tokens_hash"),
    )
    op.create_index(
        "ix_file_download_tokens_expiry", "file_download_tokens", ["expires_at", "used_at"]
    )
    op.create_table(
        "file_scans",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("signature", sa.String(200)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
    )
    op.create_index("ix_file_scans_file_created", "file_scans", ["file_id", "created_at"])
    op.create_foreign_key(
        "fk_job_results_result_file_id_files",
        "job_results",
        "files",
        ["result_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("dashboard_exports", sa.Column("platform_job_id", UUID))
    op.create_foreign_key(
        "fk_dashboard_exports_platform_job",
        "dashboard_exports",
        "jobs",
        ["platform_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_dashboard_exports_platform_job_id", "dashboard_exports", ["platform_job_id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_job_results_result_file_id_files", "job_results", type_="foreignkey")
    op.drop_constraint("uq_dashboard_exports_platform_job_id", "dashboard_exports", type_="unique")
    op.drop_constraint("fk_dashboard_exports_platform_job", "dashboard_exports", type_="foreignkey")
    op.drop_column("dashboard_exports", "platform_job_id")
    for table in (
        "file_scans",
        "file_download_tokens",
        "file_uploads",
        "file_versions",
        "files",
        "worker_heartbeats",
        "job_results",
        "dead_letter_jobs",
        "job_errors",
        "job_logs",
        "job_progress",
        "job_attempts",
        "job_payloads",
        "jobs",
    ):
        op.drop_table(table)
