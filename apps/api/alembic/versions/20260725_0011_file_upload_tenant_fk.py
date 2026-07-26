"""Cascade upload attempts with their tenant workspace.

Revision ID: 20260725_0011
Revises: 20260725_0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260725_0011"
down_revision: str | None = "20260725_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_file_uploads_workspace_tenant",
        "file_uploads",
        "workspaces",
        ["organization_id", "workspace_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_file_uploads_workspace_tenant", "file_uploads", type_="foreignkey")
