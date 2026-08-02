"""Add a 'suspended' value to the workspace status enum.

A suspended workspace blocks access to its resources while remaining
recoverable (distinct from archive/delete). Additive and non-destructive.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260728_0014"
down_revision: str | None = "20260728_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL 12+ allows ADD VALUE inside a transaction as long as the new
    # value is not used in the same transaction (we only add it here).
    op.execute("ALTER TYPE vip_workspace_status ADD VALUE IF NOT EXISTS 'suspended'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value safely; this is a no-op.
    pass
