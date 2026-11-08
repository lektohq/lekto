"""Sends webhook requests over httpx2.

- One POST per call, no redirects (a 3xx is the answer: the signature would not hold for
  another target), no retries, no proxy settings from the environment.
- The response body is neither read nor kept; leaving the request closes the connection.
- `https` certificates are verified. The timeout covers the whole exchange; connecting may take
  `connect_timeout` of it.
- Errors name the kind of failure only. The URL stays out of them and out of the log: its path
  may carry a secret of the receiver.
- A request that may not reach the own network (`private` False) resolves the host first and is
  refused unless every address is public (`core.domain.addresses.is_public`); then it goes to
  the address that was checked, with the host as `Host` and for TLS (SNI and the certificate),
  as the logo fetcher does (DNS rebinding).
"""

import asyncio
import logging
import time

import httpx2

from lekto.adapters.outbound.http_client import CONNECT_TIMEOUT, describe_failure
from lekto.adapters.outbound.http_client.resolver import Resolver, system_resolver
from lekto.core.domain.addresses import is_public, literal
from lekto.core.ports.webhook_sender import WebhookRequest, WebhookResponse

REFUSED = "the target has an address in the own network, which this webhook may not reach"

log = logging.getLogger(__name__)


class HttpWebhookSender:
    def __init__(
        self,
        *,
        user_agent: str = "Lekto",
        connect_timeout: float = CONNECT_TIMEOUT,
        transport: httpx2.AsyncBaseTransport | None = None,
        resolver: Resolver = system_resolver,
    ) -> None:
        """`transport` and `resolver` replace the network and the name server in tests."""
        self._user_agent = user_agent
        self._connect_timeout = connect_timeout
        self._transport = transport
        self._resolve = resolver

    async def send(self, request: WebhookRequest) -> WebhookResponse:
        limit = request.timeout.total_seconds()
        headers = {"User-Agent": self._user_agent, **request.headers}
        started = time.monotonic()
        status: int | None = None
        error: str | None = None
        refused = False
        try:
            async with asyncio.timeout(limit):
                url = httpx2.URL(request.url)
                extensions: dict[str, str] = {}
                if not request.private:
                    host = url.raw_host.decode("ascii")
                    address = await self._public_address(host)
                    if address is None:
                        refused = True
                        raise _RefusedError
                    headers["Host"] = url.netloc.decode("ascii")
                    if url.scheme == "https":
                        extensions["sni_hostname"] = host
                    url = url.copy_with(host=address)
                async with (
                    httpx2.AsyncClient(
                        transport=self._transport,
                        follow_redirects=False,
                        trust_env=False,
                        timeout=httpx2.Timeout(limit, connect=min(self._connect_timeout, limit)),
                    ) as client,
                    client.stream(
                        "POST",
                        url,
                        content=request.body,
                        headers=headers,
                        extensions=extensions,
                    ) as response,
                ):
                    status = response.status_code
        except _RefusedError:
            error = REFUSED
        except (TimeoutError, httpx2.TimeoutException):
            error = f"no answer within {limit:g} seconds"
        except httpx2.HTTPError as failure:
            error = describe_failure(failure)
        except (httpx2.InvalidURL, ValueError, OSError) as failure:  # an unusable address
            error = f"cannot send: {type(failure).__name__}"
        duration_ms = int((time.monotonic() - started) * 1000)
        if error is not None:
            log.info("webhook request failed", extra={"error": error})
        return WebhookResponse(
            status_code=status, duration_ms=duration_ms, error=error, refused=refused
        )

    async def _public_address(self, host: str) -> str | None:
        """The address to connect to: the host's own, or the first its name resolves to, once
        every one of them is public; None if one is not. OSError if the name resolves to
        none (a failure like any other: it may resolve later)."""
        own = literal(host)
        addresses = [own] if own is not None else list(await self._resolve(host))
        if not addresses or not all(is_public(address) for address in addresses):
            return None
        return addresses[0]


class _RefusedError(Exception):
    """The target is not public and the request may not reach it."""
