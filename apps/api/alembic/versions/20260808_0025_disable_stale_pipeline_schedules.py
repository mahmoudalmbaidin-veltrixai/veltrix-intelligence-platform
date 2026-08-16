"""Disable stale pipeline schedules for archived/missing pipelines
(PIPE-P2-STALE-SCHEDULES).

Data-only, forward-only cleanup: existing enabled schedules whose pipeline has
been archived (soft-deleted) or no longer exists are disabled and detached from
the due-index (next_run_at cleared). History is preserved — rows are made
inactive, never deleted. Going forward, archiving a pipeline disables its
schedules in-transaction and the scheduler skips schedules without a live
pipeline, so this backfill only reconciles pre-existing state.

Revision ID: 20260808_0025
Revises: 20260808_0024
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260808_0025"
down_revision: str | None = "20260808_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Schedules whose pipeline is archived (soft-deleted).
    op.execute(
        """
        UPDATE pipeline_schedules AS ps
        SET enabled = false,
            status = 'archived',
            next_run_at = NULL,
            row_version = ps.row_version + 1,
            updated_at = now()
        FROM pipelines AS p
        WHERE ps.organization_id = p.organization_id
          AND ps.workspace_id = p.workspace_id
          AND ps.pipeline_id = p.id
          AND p.archived_at IS NOT NULL
          AND ps.enabled = true
        """
    )
    # Legacy orphans: schedules whose pipeline row no longer exists at all.
    op.execute(
        """
        UPDATE pipeline_schedules AS ps
        SET enabled = false,
            status = 'archived',
            next_run_at = NULL,
            row_version = ps.row_version + 1,
            updated_at = now()
        WHERE ps.enabled = true
          AND NOT EXISTS (
            SELECT 1 FROM pipelines AS p
            WHERE p.organization_id = ps.organization_id
              AND p.workspace_id = ps.workspace_id
              AND p.id = ps.pipeline_id
          )
        """
    )


def downgrade() -> None:
    # One-way reconciliation of inconsistent state; there is no safe automatic
    # way to distinguish these rows from intentionally-disabled schedules.
    pass
