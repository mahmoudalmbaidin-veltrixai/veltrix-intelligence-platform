"""Persist malware scan evidence for rejected uploads.

Revision ID: 20260728_0015
Revises: 20260728_0014
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0015"
down_revision: str | None = "20260728_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("file_uploads", sa.Column("scan_provider", sa.String(length=80)))
    op.add_column("file_uploads", sa.Column("scan_status", sa.String(length=24)))
    op.add_column("file_uploads", sa.Column("scan_signature", sa.String(length=200)))


def downgrade() -> None:
    op.drop_column("file_uploads", "scan_signature")
    op.drop_column("file_uploads", "scan_status")
    op.drop_column("file_uploads", "scan_provider")
