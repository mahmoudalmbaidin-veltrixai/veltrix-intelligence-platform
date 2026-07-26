"""Idempotent local B5 dataset catalog seed."""

from __future__ import annotations

import os
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.crypto import EnvironmentEncryptionKeyProvider
from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.tenancy.models import Organization, Workspace


async def seed_dataset_catalogs(db: AsyncSession, settings: Settings, password: str) -> UUID:
    """Seed a harmless local relational source and its real catalog metadata."""
    organization = await db.scalar(
        select(Organization).where(Organization.slug == "governance-demo")
    )
    if organization is None:
        raise RuntimeError("Run configure-governance-demo before seeding B5")
    workspace = await db.scalar(
        select(Workspace).where(
            Workspace.organization_id == organization.id, Workspace.slug == "default"
        )
    )
    if workspace is None:
        raise RuntimeError("The governance demo workspace is unavailable")
    connection_type = await db.scalar(
        select(ConnectionType).where(ConnectionType.key == "postgresql")
    )
    if connection_type is None:
        raise RuntimeError("Run seed-connection-types before seeding B5")
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS vip_b5_sales_demo ("
            "order_date date NOT NULL, country text NOT NULL, "
            "revenue numeric(18,2) NOT NULL, order_id bigint NOT NULL)"
        )
    )
    count = await db.scalar(text("SELECT count(*) FROM vip_b5_sales_demo"))
    if int(count or 0) == 0:
        await db.execute(
            text(
                "INSERT INTO vip_b5_sales_demo(order_date,country,revenue,order_id) VALUES "
                "('2026-07-01','Saudi Arabia',1250000.50,1),"
                "('2026-07-02','Jordan',340000.00,2),"
                "('2026-07-03','Saudi Arabia',410000.00,3)"
            )
        )
    connection = await db.scalar(
        select(Connection).where(
            Connection.organization_id == organization.id,
            Connection.workspace_id == workspace.id,
            Connection.normalized_name == "vip b5 demo warehouse",
        )
    )
    if connection is None:
        connection = Connection(
            organization_id=organization.id,
            workspace_id=workspace.id,
            connection_type_id=connection_type.id,
            name="VIP B5 Demo Warehouse",
            normalized_name="vip b5 demo warehouse",
            description="Local read-only analytics demonstration source",
            status="active",
            health_status="healthy",
            configuration={
                "host": os.getenv("B5_DEMO_POSTGRES_HOST", "localhost"),
                "port": 5432,
                "database": "vip",
                "username": "vip",
                "ssl_mode": "disable",
                "connect_timeout_seconds": 10,
            },
            credential_version=1,
            connection_type_version=connection_type.version,
        )
        db.add(connection)
        await db.flush()
        provider = DatabaseEncryptedSecretProvider(EnvironmentEncryptionKeyProvider(settings))
        secret = await provider.store_secret(
            db,
            organization_id=organization.id,
            workspace_id=workspace.id,
            connection_id=connection.id,
            credential_version=1,
            credentials={"password": password},
            actor_user_id=organization.created_by_user_id,
        )
        connection.secret_id = secret.id
    key = sha256(
        f"{connection.id}\x1fvip\x1fpublic\x1fvip_b5_sales_demo\x1ftable".encode()
    ).hexdigest()
    dataset = await db.scalar(
        select(Dataset).where(
            Dataset.organization_id == organization.id,
            Dataset.workspace_id == workspace.id,
            Dataset.source_key == key,
        )
    )
    if dataset is None:
        dataset = Dataset(
            organization_id=organization.id,
            workspace_id=workspace.id,
            connection_id=connection.id,
            dataset_type="table",
            source_catalog="vip",
            source_schema="public",
            source_name="vip_b5_sales_demo",
            source_key=key,
            qualified_name="vip.public.vip_b5_sales_demo",
            display_name="Sales Demo",
            description="Controlled B5 read-only semantic query dataset",
            source_object_type="table",
            certification_status="certified",
            created_by_user_id=organization.created_by_user_id,
            updated_by_user_id=organization.created_by_user_id,
        )
        db.add(dataset)
        await db.flush()
    definitions = (
        ("order_date", "date", "date", "timestamp"),
        ("country", "text", "string", "dimension"),
        ("revenue", "numeric", "decimal", "measure"),
        ("order_id", "bigint", "integer", "identifier"),
    )
    for ordinal, (name, physical, normalized, role) in enumerate(definitions, 1):
        field = await db.scalar(
            select(DatasetField).where(
                DatasetField.dataset_id == dataset.id, DatasetField.source_name == name
            )
        )
        if field is None:
            db.add(
                DatasetField(
                    organization_id=organization.id,
                    workspace_id=workspace.id,
                    dataset_id=dataset.id,
                    source_name=name,
                    display_name=name.replace("_", " ").title(),
                    ordinal_position=ordinal,
                    physical_data_type=physical,
                    normalized_data_type=normalized,
                    role=role,
                    is_nullable=False,
                )
            )
    await db.commit()
    return dataset.id
