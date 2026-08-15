"""Alembic migration and schema-drift validation against PostgreSQL."""

import asyncio
import os
import sys
from pathlib import Path
from subprocess import run
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vip_api.auth.models import User, UserStatus
from vip_api.home.models import NotificationRead

NOTIFICATION_REVISION = "20260808_0024"
PRE_NOTIFICATION_REVISION = "20260808_0023"


def _config() -> Config:
    return Config(Path(__file__).parents[2] / "alembic.ini")


def _require_test_database() -> None:
    database_name = make_url(os.environ["DATABASE_URL"]).database or ""
    assert database_name.endswith("_test"), "migration tests require a dedicated *_test database"


async def _notification_schema() -> dict[str, Any]:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.connect() as async_connection:

            def inspect_schema(connection: Connection) -> dict[str, Any]:
                inspector = inspect(connection)
                tables = inspector.get_table_names(schema="public")
                if "notification_reads" not in tables:
                    return {"tables": tables}
                columns = inspector.get_columns("notification_reads", schema="public")
                return {
                    "tables": tables,
                    "columns": {
                        str(column["name"]): {
                            "type": type(column["type"]).__name__,
                            "nullable": column["nullable"],
                            "default": column["default"],
                            "length": getattr(column["type"], "length", None),
                            "timezone": getattr(column["type"], "timezone", None),
                        }
                        for column in columns
                    },
                    "pk": inspector.get_pk_constraint("notification_reads", schema="public"),
                    "fks": inspector.get_foreign_keys("notification_reads", schema="public"),
                    "uniques": inspector.get_unique_constraints(
                        "notification_reads", schema="public"
                    ),
                    "indexes": inspector.get_indexes("notification_reads", schema="public"),
                }

            return await async_connection.run_sync(inspect_schema)
    finally:
        await engine.dispose()


def _assert_notification_schema(schema: dict[str, Any]) -> None:
    assert schema["tables"].count("notification_reads") == 1
    columns = schema["columns"]
    assert columns == {
        "id": {
            "type": "UUID",
            "nullable": False,
            "default": None,
            "length": None,
            "timezone": None,
        },
        "user_id": {
            "type": "UUID",
            "nullable": False,
            "default": None,
            "length": None,
            "timezone": None,
        },
        "notification_id": {
            "type": "VARCHAR",
            "nullable": False,
            "default": None,
            "length": 200,
            "timezone": None,
        },
        "read_at": {
            "type": "TIMESTAMP",
            "nullable": False,
            "default": None,
            "length": None,
            "timezone": True,
        },
    }
    assert schema["pk"] == {
        "constrained_columns": ["id"],
        "name": "pk_notification_reads",
        "comment": None,
        "dialect_options": {"postgresql_include": []},
    }
    assert {
        (foreign_key["name"], tuple(foreign_key["constrained_columns"]))
        for foreign_key in schema["fks"]
    } == {("fk_notification_reads_user", ("user_id",))}
    foreign_key = schema["fks"][0]
    assert foreign_key["referred_schema"] == "public"
    assert foreign_key["referred_table"] == "users"
    assert foreign_key["referred_columns"] == ["id"]
    assert foreign_key["options"] == {"ondelete": "CASCADE"}
    assert {(unique["name"], tuple(unique["column_names"])) for unique in schema["uniques"]} == {
        ("uq_notification_reads_user_notification", ("user_id", "notification_id"))
    }
    assert {
        (index["name"], tuple(index["column_names"]), index["unique"])
        for index in schema["indexes"]
    } == {
        ("ix_notification_reads_user", ("user_id",), False),
        ("uq_notification_reads_user_notification", ("user_id", "notification_id"), True),
    }
    unique_index = next(index for index in schema["indexes"] if index["unique"])
    assert unique_index["duplicates_constraint"] == "uq_notification_reads_user_notification"


async def _insert_notification_marker() -> tuple[UUID, UUID]:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    try:
        async with sessions() as session:
            user = User(
                username=f"migration-{suffix}",
                normalized_username=f"migration-{suffix}",
                email=f"migration-{suffix}@vip.test",
                normalized_email=f"migration-{suffix}@vip.test",
                password_hash="not-used",
                display_name="Migration preservation",
                status=UserStatus.ACTIVE,
            )
            session.add(user)
            await session.flush()
            marker = NotificationRead(
                user_id=user.id,
                notification_id=f"job:{uuid4()}:1",
            )
            session.add(marker)
            await session.commit()
            return user.id, marker.id
    finally:
        await engine.dispose()


async def _assert_marker_and_cleanup(user_id: UUID, marker_id: UUID) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            marker = await session.scalar(
                select(NotificationRead).where(NotificationRead.id == marker_id)
            )
            assert marker is not None
            assert marker.user_id == user_id
            user = await session.get(User, user_id)
            assert user is not None
            await session.delete(user)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_alembic_clean_upgrade_and_current_head() -> None:
    _require_test_database()
    root = Path(__file__).parents[2]
    config = _config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    result = run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert heads == [NOTIFICATION_REVISION]
    assert NOTIFICATION_REVISION in result.stdout
    _assert_notification_schema(asyncio.run(_notification_schema()))


@pytest.mark.integration
def test_notification_read_upgrade_from_previous_revision() -> None:
    _require_test_database()
    config = _config()
    command.downgrade(config, PRE_NOTIFICATION_REVISION)
    assert "notification_reads" not in asyncio.run(_notification_schema())["tables"]

    command.upgrade(config, "head")

    _assert_notification_schema(asyncio.run(_notification_schema()))


@pytest.mark.integration
def test_notification_read_schema_has_no_alembic_drift() -> None:
    _require_test_database()
    config = _config()
    command.upgrade(config, "head")

    command.check(config)


@pytest.mark.integration
def test_notification_read_data_survives_head_upgrade() -> None:
    _require_test_database()
    config = _config()
    command.upgrade(config, "head")
    user_id, marker_id = asyncio.run(_insert_notification_marker())

    command.upgrade(config, "head")

    asyncio.run(_assert_marker_and_cleanup(user_id, marker_id))
