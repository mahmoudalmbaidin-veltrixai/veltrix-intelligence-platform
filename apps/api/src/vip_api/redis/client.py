"""Asynchronous Redis client lifecycle."""

from redis.asyncio import Redis

from vip_api.core.config import Settings


class RedisClient:
    """Own a request-independent Redis client and its connection pool."""

    def __init__(self, settings: Settings) -> None:
        self.client: Redis = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            health_check_interval=30,
            decode_responses=True,
        )

    async def close(self) -> None:
        await self.client.aclose()
