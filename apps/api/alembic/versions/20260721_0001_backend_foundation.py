"""Establish the migration baseline without domain tables.

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21
"""

from collections.abc import Sequence

revision: str = "20260721_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Alembic's own version table is sufficient for the foundation baseline."""


def downgrade() -> None:
    """No application objects were created by this baseline revision."""
