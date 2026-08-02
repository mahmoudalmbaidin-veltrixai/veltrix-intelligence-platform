"""Identity: username login + optional email + enterprise profile fields.

Backward compatible and data-safe:
  * Adds a required, globally-unique ``username`` (backfilled from the email
    local-part with collision-safe suffixing) — existing user IDs and password
    hashes are never touched.
  * Makes ``email`` optional (nullable); its uniqueness becomes a *partial*
    unique index that only applies when an email value is present.
  * Adds optional enterprise profile / lifecycle columns.

Login accepts username OR email (see auth.authentication), so existing
email-based logins keep working during and after the transition.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0013"
down_revision: str | None = "20260727_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add username columns (nullable first so we can backfill).
    op.add_column("users", sa.Column("username", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("normalized_username", sa.String(length=150), nullable=True))

    # 2. Add enterprise profile / lifecycle columns (all safe additive).
    op.add_column(
        "users",
        sa.Column("account_type", sa.String(length=50), nullable=False, server_default="standard"),
    )
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("default_organization_id", sa.Uuid(as_uuid=True)))
    op.add_column("users", sa.Column("default_workspace_id", sa.Uuid(as_uuid=True)))
    op.add_column("users", sa.Column("locale", sa.String(length=20)))
    op.add_column("users", sa.Column("timezone", sa.String(length=64)))
    op.add_column("users", sa.Column("job_title", sa.String(length=150)))
    op.add_column("users", sa.Column("department", sa.String(length=150)))
    op.add_column("users", sa.Column("phone", sa.String(length=50)))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=1024)))
    op.add_column("users", sa.Column("created_by", sa.Uuid(as_uuid=True)))
    op.add_column("users", sa.Column("updated_by", sa.Uuid(as_uuid=True)))

    # 3. Backfill usernames from email local-parts, collision-safe + globally
    #    unique. Pure SQL (a window function suffixes duplicates deterministically).
    op.execute(
        sa.text(
            """
            WITH base AS (
                SELECT
                    id,
                    COALESCE(
                        NULLIF(
                            regexp_replace(
                                lower(split_part(COALESCE(email, ''), '@', 1)),
                                '[^a-z0-9_.-]+', '', 'g'
                            ),
                            ''
                        ),
                        'user'
                    ) AS uname,
                    created_at
                FROM users
            ),
            numbered AS (
                SELECT
                    id,
                    uname,
                    row_number() OVER (PARTITION BY uname ORDER BY created_at, id) AS rn
                FROM base
            )
            UPDATE users u
            SET username = CASE WHEN n.rn = 1 THEN n.uname ELSE n.uname || n.rn::text END,
                normalized_username = lower(
                    CASE WHEN n.rn = 1 THEN n.uname ELSE n.uname || n.rn::text END
                )
            FROM numbered n
            WHERE u.id = n.id
            """
        )
    )

    # 4. Enforce NOT NULL + unique on username now that it is populated.
    op.alter_column("users", "username", nullable=False)
    op.alter_column("users", "normalized_username", nullable=False)
    op.create_index("uq_users_normalized_username", "users", ["normalized_username"], unique=True)

    # 5. Make email optional; swap the unconditional unique constraint for a
    #    partial unique index (only enforced when email is present).
    op.drop_constraint("uq_users_normalized_email", "users", type_="unique")
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=True)
    op.alter_column("users", "normalized_email", existing_type=sa.String(length=320), nullable=True)
    op.create_index(
        "uq_users_normalized_email_present",
        "users",
        ["normalized_email"],
        unique=True,
        postgresql_where=sa.text("normalized_email IS NOT NULL"),
    )


def downgrade() -> None:
    # Reverse: restore unconditional email uniqueness and drop username/profile.
    op.drop_index("uq_users_normalized_email_present", table_name="users")
    op.alter_column(
        "users", "normalized_email", existing_type=sa.String(length=320), nullable=False
    )
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=False)
    op.create_unique_constraint("uq_users_normalized_email", "users", ["normalized_email"])

    op.drop_index("uq_users_normalized_username", table_name="users")
    for column in (
        "updated_by",
        "created_by",
        "avatar_url",
        "phone",
        "department",
        "job_title",
        "timezone",
        "locale",
        "default_workspace_id",
        "default_organization_id",
        "must_change_password",
        "account_type",
        "normalized_username",
        "username",
    ):
        op.drop_column("users", column)
