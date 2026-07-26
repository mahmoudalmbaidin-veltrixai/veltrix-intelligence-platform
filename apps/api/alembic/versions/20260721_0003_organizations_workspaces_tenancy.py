"""Add organizations, workspaces, memberships, and invitations.

Revision ID: 20260721_0003
Revises: 20260721_0002
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0003"
down_revision: str | None = "20260721_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

organization_status = postgresql.ENUM(
    "active", "suspended", "archived", "deleted", name="vip_organization_status", create_type=False
)
workspace_status = postgresql.ENUM(
    "active", "archived", "deleted", name="vip_workspace_status", create_type=False
)
membership_role = postgresql.ENUM(
    "owner", "admin", "member", name="vip_membership_role", create_type=False
)
membership_status = postgresql.ENUM(
    "active", "invited", "suspended", "removed", name="vip_membership_status", create_type=False
)
invitation_status = postgresql.ENUM(
    "pending", "accepted", "expired", "revoked", name="vip_invitation_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        organization_status,
        workspace_status,
        membership_role,
        membership_status,
        invitation_status,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("status", organization_status, nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_organizations_creator",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_status", "organizations", ["status"])
    op.create_index("ix_organizations_created_by_user_id", "organizations", ["created_by_user_id"])

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("status", workspace_status, nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE", name="fk_workspaces_org"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT", name="fk_workspaces_creator"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspaces_organization_slug"),
        sa.UniqueConstraint("organization_id", "id", name="uq_workspaces_organization_id"),
    )
    op.create_index(
        "ix_workspaces_organization_status", "workspaces", ["organization_id", "status"]
    )
    op.create_index(
        "uq_workspaces_default_per_organization",
        "workspaces",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND deleted_at IS NULL"),
    )

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", membership_role, nullable=False),
        sa.Column("status", membership_status, nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
    )
    op.create_index(
        "ix_org_memberships_user_status", "organization_memberships", ["user_id", "status"]
    )
    op.create_index(
        "ix_org_memberships_org_status", "organization_memberships", ["organization_id", "status"]
    )

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", membership_role, nullable=False),
        sa.Column("status", membership_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_workspace_memberships_workspace_tenant",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_memberships"),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_memberships_workspace_user"
        ),
    )
    op.create_index(
        "ix_workspace_memberships_user_status", "workspace_memberships", ["user_id", "status"]
    )
    op.create_index(
        "ix_workspace_memberships_tenant_status",
        "workspace_memberships",
        ["organization_id", "workspace_id", "status"],
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("organization_role", membership_role, nullable=False),
        sa.Column("workspace_role", membership_role, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", invitation_status, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_invitations"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"])
    op.create_index("ix_invitations_org_status", "invitations", ["organization_id", "status"])
    op.create_index("ix_invitations_email", "invitations", ["normalized_email"])
    op.create_index("ix_invitations_expires", "invitations", ["expires_at"])
    op.create_index(
        "uq_invitations_pending_org_email",
        "invitations",
        ["organization_id", "normalized_email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "invitation_workspaces",
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="CASCADE",
            name="fk_invitation_workspaces_workspace_tenant",
        ),
        sa.PrimaryKeyConstraint("invitation_id", "workspace_id", name="pk_invitation_workspaces"),
    )


def downgrade() -> None:
    op.drop_table("invitation_workspaces")
    op.drop_index("uq_invitations_pending_org_email", table_name="invitations")
    op.drop_index("ix_invitations_expires", table_name="invitations")
    op.drop_index("ix_invitations_email", table_name="invitations")
    op.drop_index("ix_invitations_org_status", table_name="invitations")
    op.drop_index("ix_invitations_token_hash", table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("ix_workspace_memberships_tenant_status", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_user_status", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_index("ix_org_memberships_org_status", table_name="organization_memberships")
    op.drop_index("ix_org_memberships_user_status", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_index("uq_workspaces_default_per_organization", table_name="workspaces")
    op.drop_index("ix_workspaces_organization_status", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_organizations_created_by_user_id", table_name="organizations")
    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_table("organizations")
    bind = op.get_bind()
    for enum_type in (
        invitation_status,
        membership_status,
        membership_role,
        workspace_status,
        organization_status,
    ):
        enum_type.drop(bind, checkfirst=True)
