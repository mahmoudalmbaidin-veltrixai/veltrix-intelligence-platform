"""connections and encrypted secrets

Revision ID: 20260721_0005
Revises: 53957b92b086
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0005"
down_revision: str | None = "53957b92b086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connection_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("configuration_schema", sa.JSON(), nullable=False),
        sa.Column("secret_schema", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("test_strategy", sa.String(80), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connection_types")),
        sa.UniqueConstraint("key", name=op.f("uq_connection_types_key")),
    )
    op.create_table(
        "connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_type_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("health_status", sa.String(20), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("secret_id", sa.Uuid(), nullable=True),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("connection_type_version", sa.Integer(), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(20), nullable=True),
        sa.Column("last_test_error_code", sa.String(80), nullable=True),
        sa.Column("last_test_latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_healthy_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_connections_connections_positive_version")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
            name=op.f("fk_connections_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
            name=op.f("fk_connections_workspace_id_workspaces"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_type_id"],
            ["connection_types.id"],
            ondelete="RESTRICT",
            name=op.f("fk_connections_connection_type_id_connection_types"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_connections_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_connections_updated_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connections")),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_connections_tenant_id"
        ),
    )
    op.create_index(
        "ix_connections_tenant_status", "connections", ["organization_id", "workspace_id", "status"]
    )
    op.create_index(
        "ix_connections_tenant_health",
        "connections",
        ["organization_id", "workspace_id", "health_status"],
    )
    op.create_index(
        "uq_connections_active_name",
        "connections",
        ["organization_id", "workspace_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_table(
        "connection_secrets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_reference", sa.String(200), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_algorithm", sa.String(40), nullable=False),
        sa.Column("key_version", sa.String(40), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("secret_fields", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
            name=op.f("fk_connection_secrets_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
            name=op.f("fk_connection_secrets_workspace_id_workspaces"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            ondelete="CASCADE",
            name=op.f("fk_connection_secrets_connection_id_connections"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_connection_secrets_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connection_secrets")),
        sa.UniqueConstraint(
            "provider_reference", name=op.f("uq_connection_secrets_provider_reference")
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "connection_id",
            "credential_version",
            name="uq_connection_secret_version",
        ),
    )
    op.create_index(
        "ix_connection_secrets_tenant_connection",
        "connection_secrets",
        ["organization_id", "workspace_id", "connection_id"],
    )
    op.create_foreign_key(
        "fk_connections_secret_id_connection_secrets",
        "connections",
        "connection_secrets",
        ["secret_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_connections_secret_id_connection_secrets", "connections", type_="foreignkey"
    )
    op.drop_index("ix_connection_secrets_tenant_connection", table_name="connection_secrets")
    op.drop_table("connection_secrets")
    op.drop_index(
        "uq_connections_active_name",
        table_name="connections",
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.drop_index("ix_connections_tenant_health", table_name="connections")
    op.drop_index("ix_connections_tenant_status", table_name="connections")
    op.drop_table("connections")
    op.drop_table("connection_types")
