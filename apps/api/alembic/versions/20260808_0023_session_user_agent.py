"""Store the User-Agent on auth sessions for honest device display.

Revision ID: 20260808_0023
Revises: 20260808_0022
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0023"
down_revision: str | None = "20260808_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("user_agent", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_sessions", "user_agent")
