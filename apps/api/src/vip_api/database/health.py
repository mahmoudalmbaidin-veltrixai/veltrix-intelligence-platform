"""Bounded database readiness checks."""

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from vip_api.database.session import Database


async def check_database(database: Database, timeout_seconds: float) -> bool:
    try:
        async with asyncio.timeout(timeout_seconds):
            async with database.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        return True
    except (TimeoutError, SQLAlchemyError, OSError):
        return False
