"""Custom roles and role assignments (Enterprise permissions — Slice C).

Additive only. Extends ``roles`` with nullable tenant-configurable columns
(system roles keep them NULL/false so existing behavior is unchanged) and adds
``user_role_assignments`` and ``group_role_assignments`` for direct and
group-based role grants. No existing data is modified destructively.

Revision ID: 20260728_0018
Revises: 20260728_0017
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0018"
down_revision: str | None = "20260728_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "roles",
        sa.Column(
            "workspace_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("roles", sa.Column("slug", sa.String(length=160), nullable=True))
    op.add_column(
        "roles",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column(
        "roles",
        sa.Column("is_editable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "roles",
        sa.Column(
            "created_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "roles",
        sa.Column(
            "updated_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "roles",
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("roles", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("roles", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_roles_org_slug", "roles", ["organization_id", "slug"])
    op.create_index("ix_roles_org_scope", "roles", ["organization_id", "scope"])
    op.create_index("ix_roles_workspace", "roles", ["workspace_id"])

    op.create_table(
        "user_role_assignments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column(
            "assigned_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "user_id",
            "role_id",
            name="uq_user_role_assignment",
        ),
    )
    op.create_index("ix_user_role_assignments_user", "user_role_assignments", ["user_id"])
    op.create_index("ix_user_role_assignments_role", "user_role_assignments", ["role_id"])
    op.create_index(
        "ix_user_role_assignments_tenant",
        "user_role_assignments",
        ["organization_id", "workspace_id"],
    )

    op.create_table(
        "group_role_assignments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "group_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column(
            "assigned_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "group_id",
            "role_id",
            name="uq_group_role_assignment",
        ),
    )
    op.create_index("ix_group_role_assignments_group", "group_role_assignments", ["group_id"])
    op.create_index("ix_group_role_assignments_role", "group_role_assignments", ["role_id"])
    op.create_index(
        "ix_group_role_assignments_tenant",
        "group_role_assignments",
        ["organization_id", "workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_group_role_assignments_tenant", table_name="group_role_assignments")
    op.drop_index("ix_group_role_assignments_role", table_name="group_role_assignments")
    op.drop_index("ix_group_role_assignments_group", table_name="group_role_assignments")
    op.drop_table("group_role_assignments")
    op.drop_index("ix_user_role_assignments_tenant", table_name="user_role_assignments")
    op.drop_index("ix_user_role_assignments_role", table_name="user_role_assignments")
    op.drop_index("ix_user_role_assignments_user", table_name="user_role_assignments")
    op.drop_table("user_role_assignments")
    op.drop_index("ix_roles_workspace", table_name="roles")
    op.drop_index("ix_roles_org_scope", table_name="roles")
    op.drop_constraint("uq_roles_org_slug", "roles", type_="unique")
    op.drop_column("roles", "deleted_at")
    op.drop_column("roles", "archived_at")
    op.drop_column("roles", "row_version")
    op.drop_column("roles", "updated_by_user_id")
    op.drop_column("roles", "created_by_user_id")
    op.drop_column("roles", "is_editable")
    op.drop_column("roles", "status")
    op.drop_column("roles", "slug")
    op.drop_column("roles", "workspace_id")
    op.drop_column("roles", "organization_id")
