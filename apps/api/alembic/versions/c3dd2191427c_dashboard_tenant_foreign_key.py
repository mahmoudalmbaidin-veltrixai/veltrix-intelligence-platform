"""dashboard tenant foreign key

Revision ID: c3dd2191427c
Revises: a069d0a8a1ca
Create Date: 2026-07-22 13:26:09.097347
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3dd2191427c"
down_revision: str | None = "a069d0a8a1ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_dashboards_workspace_tenant",
        "dashboards",
        "workspaces",
        ["organization_id", "workspace_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_dashboards_workspace_tenant", "dashboards", type_="foreignkey")
