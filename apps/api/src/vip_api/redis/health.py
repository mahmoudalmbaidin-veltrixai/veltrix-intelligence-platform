"""Bounded Redis readiness checks."""

import asyncio

from redis.exceptions import RedisError

from vip_api.redis.client import RedisClient


async def check_redis(redis_client: RedisClient, timeout_seconds: float) -> bool:
    try:
        async with asyncio.timeout(timeout_seconds):
            return bool(await redis_client.client.ping())
    except (TimeoutError, RedisError, OSError):
        return False
