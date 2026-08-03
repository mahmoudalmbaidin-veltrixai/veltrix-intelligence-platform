"""Dataset certification metadata (Phase B9.1B).

Additive only. Adds certified_by_user_id, certified_at, and certification_note
so certify/revoke can persist actor, timestamp, and note independently of the
generic dataset update path (which remains edit-gated).

Revision ID: 20260803_0019
Revises: 20260728_0018
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0019"
down_revision: str | None = "20260728_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column(
            "certified_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "datasets",
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "datasets",
        sa.Column("certification_note", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("datasets", "certification_note")
    op.drop_column("datasets", "certified_at")
    op.drop_column("datasets", "certified_by_user_id")
