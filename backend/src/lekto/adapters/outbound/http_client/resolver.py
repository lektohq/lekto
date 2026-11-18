"""Resolving host names for adapters that connect only where an address check allows
(`core.domain.addresses`): they resolve first, check every address, then connect to the one
they checked, so that a second answer of the name server cannot lead elsewhere (DNS
rebinding)."""

import asyncio
import socket
from collections.abc import Awaitable, Callable, Sequence

import httpx2

from lekto.core.domain.addresses import is_public, literal

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


class NotPublicError(Exception):
    """A host with an address that is not public (`core.domain.addresses.is_public`)."""


async def checked_address(resolve: Resolver, host: str) -> str:
    """The address to connect to for `host`: its own, or the first its name resolves to, once
    every one of them is public; the request then goes to it (`pinned`). OSError if the name
    resolves to none (it may later); NotPublicError if an address is not public (AD-13)."""
    own = literal(host)
    addresses = [own] if own is not None else list(await resolve(host))
    if not addresses:
        raise OSError(f"{host} resolves to no address")
    if not all(is_public(address) for address in addresses):
        raise NotPublicError(host)
    return addresses[0]


def pinned(url: httpx2.URL, address: str) -> tuple[httpx2.URL, str, dict[str, str]]:
    """`url` sent to `address` (`checked_address`): the URL, the `Host` header of its own host
    (with its port), and the extensions that keep that host's name for TLS."""
    host = url.raw_host.decode("ascii")
    extensions = {"sni_hostname": host} if url.scheme == "https" else {}
    return url.copy_with(host=address), url.netloc.decode("ascii"), extensions
