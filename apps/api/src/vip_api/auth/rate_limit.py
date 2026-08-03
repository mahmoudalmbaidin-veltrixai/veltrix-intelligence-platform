"""Small Redis-backed login rate-limit foundation."""

import logging
from hashlib import sha256

from redis.exceptions import RedisError

from vip_api.core.config import Settings
from vip_api.redis.client import RedisClient

logger = logging.getLogger(__name__)


async def login_rate_limited(
    redis_client: RedisClient, client_identifier: str, settings: Settings
) -> bool:
    identifier_hash = sha256(client_identifier.encode()).hexdigest()
    key = f"vip:auth:login-rate:{identifier_hash}"
    try:
        count = await redis_client.client.incr(key)
        if count == 1:
            await redis_client.client.expire(key, 60)
        return bool(count > settings.AUTH_LOGIN_RATE_LIMIT_PER_MINUTE)
    except RedisError:
        logger.warning(
            "Login rate-limit store unavailable", extra={"security_event": "rate_limit_unavailable"}
        )
        return False


async def password_reset_rate_limited(
    redis_client: RedisClient, scope: str, settings: Settings
) -> bool:
    """Throttle password-reset requests. ``scope`` should combine the client IP
    and the submitted identifier so neither an IP nor a single account can be
    flooded. Fails open if Redis is unavailable so recovery stays possible."""
    scope_hash = sha256(scope.encode()).hexdigest()
    key = f"vip:auth:pwreset-rate:{scope_hash}"
    try:
        count = await redis_client.client.incr(key)
        if count == 1:
            await redis_client.client.expire(key, 60)
        return bool(count > settings.PASSWORD_RESET_RATE_LIMIT_PER_MINUTE)
    except RedisError:
        logger.warning(
            "Password-reset rate-limit store unavailable",
            extra={"security_event": "rate_limit_unavailable"},
        )
        return False
