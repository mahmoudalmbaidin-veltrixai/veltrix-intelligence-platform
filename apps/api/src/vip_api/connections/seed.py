"""Idempotent synchronization of the checked-in connection-type catalog."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.connections.catalog import CONNECTION_TYPES
from vip_api.connections.models import ConnectionType


async def seed_connection_types(db: AsyncSession) -> None:
    for definition in CONNECTION_TYPES:
        item = await db.scalar(select(ConnectionType).where(ConnectionType.key == definition.key))
        values: dict[str, object] = {
            "name": definition.name,
            "description": definition.description,
            "category": definition.category,
            "configuration_schema": definition.configuration_schema,
            "secret_schema": definition.secret_schema,
            "capabilities": list(definition.capabilities),
            "test_strategy": definition.test_strategy,
            "is_enabled": definition.enabled,
            "is_system": True,
            "version": definition.version,
        }
        if item is None:
            db.add(ConnectionType(key=definition.key, **values))
        else:
            for key, value in values.items():
                setattr(item, key, value)
    await db.commit()
