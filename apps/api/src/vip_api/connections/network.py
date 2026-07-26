"""Network destination validation for connection tests and redirects."""

from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import urlparse

from vip_api.core.config import Settings


class UnsafeDestinationError(ValueError):
    pass


_METADATA_ADDRESSES = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}


def _blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address, settings: Settings) -> bool:
    if settings.CONNECTION_BLOCK_CLOUD_METADATA and address in _METADATA_ADDRESSES:
        return True
    if (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    ):
        return True
    return not settings.CONNECTION_ALLOW_PRIVATE_NETWORKS and (
        address.is_private or address.is_reserved
    )


async def validate_host(host: str, port: int, settings: Settings) -> None:
    if not host or any(char in host for char in ("/", "\\", "\x00", "\r", "\n")):
        raise UnsafeDestinationError("Connection destination is invalid")
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
        addresses = {literal}
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            records = await asyncio.wait_for(
                loop.getaddrinfo(host, port, type=0, proto=0),
                timeout=min(settings.CONNECTION_TEST_TIMEOUT_SECONDS, 5),
            )
        except (OSError, TimeoutError) as exc:
            raise UnsafeDestinationError("Connection destination could not be resolved") from exc
        addresses = {ipaddress.ip_address(record[4][0]) for record in records}
    if not addresses or any(_blocked(address, settings) for address in addresses):
        raise UnsafeDestinationError("Connection destination is blocked by network policy")


async def validate_url(url: str, settings: Settings) -> None:
    parsed = urlparse(url)
    allowed = {"https"}
    if settings.CONNECTION_ALLOW_HTTP:
        allowed.add("http")
    if parsed.scheme not in allowed or parsed.username or parsed.password or not parsed.hostname:
        raise UnsafeDestinationError("Connection URL is not allowed")
    default_port = 443 if parsed.scheme == "https" else 80
    await validate_host(parsed.hostname, parsed.port or default_port, settings)
