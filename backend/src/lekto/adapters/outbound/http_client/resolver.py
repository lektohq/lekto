"""Resolving host names for adapters that connect only where an address check allows
(`core.domain.addresses`): they resolve first, check every address, then connect to the one
they checked, so that a second answer of the name server cannot lead elsewhere (DNS
rebinding)."""

import asyncio
import socket
from collections.abc import Awaitable, Callable, Sequence

type Resolver = Callable[[str], Awaitable[Sequence[str]]]
"""The addresses (as text) a host name resolves to; OSError if it resolves to none."""


async def system_resolver(host: str) -> list[str]:
    """The addresses the system's resolver gives `host` for TCP."""
    loop = asyncio.get_running_loop()
    found = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    addresses = list(dict.fromkeys(str(info[4][0]) for info in found))
    if not addresses:
        raise OSError(f"{host} resolves to no address")
    return addresses
