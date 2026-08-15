"""Alembic environment for the asynchronous SQLAlchemy engine."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, inspect, pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from vip_api.core.config import get_settings
from vip_api.database.metadata import target_metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))


IncludeObject = Callable[[object, str | None, str, bool, object | None], bool]


def _include_object_for(external_source_tables: frozenset[str]) -> IncludeObject:
    def include_object(
        _object: object,
        name: str | None,
        type_: str,
        reflected: bool,
        compare_to: object | None,
    ) -> bool:
        """Compare platform schema while excluding governed external source data."""
        if not reflected or type_ != "table" or compare_to is not None:
            return True
        table_name = name or ""
        return not (table_name.startswith("vip_b5_") or table_name in external_source_tables)

    return include_object


def _external_source_table_names(connection: Connection) -> frozenset[str]:
    """Identify registered warehouse tables when a connection targets the app database."""
    if not inspect(connection).has_table("datasets"):
        return frozenset()
    names = connection.execute(
        text("SELECT source_name FROM datasets WHERE source_object_type = 'table'")
    ).scalars()
    return frozenset(str(name) for name in names)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=_include_object_for(frozenset()),
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=_include_object_for(_external_source_table_names(connection)),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        # SQLAlchemy 2.0 async connections are commit-as-you-go: without an
        # explicit commit the transaction is rolled back when the block exits,
        # which silently discards the applied migration. Commit explicitly.
        await connection.commit()
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
