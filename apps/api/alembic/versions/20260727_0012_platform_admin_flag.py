"""Add a platform super-admin flag to users.

Platform administration is a cross-tenant capability held by a small number of
operators. It is intentionally a user-level flag (outside the per-organization
membership/role model) and defaults to false, so it is never self-granted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0012"
down_revision: str | None = "20260725_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_platform_admin")
