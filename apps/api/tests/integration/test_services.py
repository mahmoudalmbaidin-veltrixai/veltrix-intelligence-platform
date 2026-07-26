"""Live PostgreSQL and Redis integration checks."""

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from vip_api.core.config import Settings
from vip_api.database.health import check_database
from vip_api.database.session import Database
from vip_api.redis.client import RedisClient
from vip_api.redis.health import check_redis


@pytest.mark.integration
async def test_async_database_session_executes_query(settings: Settings) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
        assert await check_database(database, 5)
    finally:
        await database.dispose()


@pytest.mark.integration
async def test_redis_client_can_ping(settings: Settings) -> None:
    redis_client = RedisClient(settings)
    try:
        assert await check_redis(redis_client, 5)
    finally:
        await redis_client.close()


@pytest.mark.integration
async def test_redis_failure_is_clean(settings: Settings) -> None:
    broken_settings = settings.model_copy(update={"REDIS_URL": SecretStr("redis://127.0.0.1:1/0")})
    redis_client = RedisClient(broken_settings)
    try:
        assert not await check_redis(redis_client, 0.1)
    finally:
        await redis_client.close()
