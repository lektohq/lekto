"""Sends webhook requests over httpx2.

- One POST per call, no redirects (a 3xx is the answer: the signature would not hold for
  another target), no retries, no proxy settings from the environment.
- The response body is neither read nor kept; leaving the request closes the connection.
- `https` certificates are verified. The timeout covers the whole exchange; connecting may take
  `connect_timeout` of it.
- Errors name the kind of failure only. The URL stays out of them and out of the log: its path
  may carry a secret of the receiver.
- A request that may not reach the own network (`private` False) resolves the host first and is
  refused unless every address is public (`core.domain.addresses.is_public`), a name without
  any too; a name server that does not answer for now is a failure that is tried again. Then
  it goes to the address that was checked, with the host as `Host` and for TLS (SNI and the
  certificate), as the logo fetcher does (DNS rebinding).
"""

import asyncio
import logging
import socket
import time

import httpx2

from lekto.adapters.outbound.http_client import CONNECT_TIMEOUT, describe_failure
from lekto.adapters.outbound.http_client.resolver import (
    NotPublicError,
    Resolver,
    checked_address,
    pinned,
    system_resolver,
)
from lekto.core.ports.webhook_sender import REFUSED, WebhookRequest, WebhookResponse

log = logging.getLogger(__name__)


class HttpWebhookSender:
    def __init__(
        self,
        *,
        user_agent: str,
        transport: httpx2.AsyncBaseTransport | None = None,
        resolver: Resolver = system_resolver,
    ) -> None:
        """`transport` and `resolver` replace the network and the name server in tests."""
        self._user_agent = user_agent
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
                    try:
                        address = await checked_address(self._resolve, url.raw_host.decode("ascii"))
                    except OSError as failure:
                        if _answers_later(failure):
                            raise _UnresolvedError from None
                        # A name that does not exist is refused too: else the log would tell
                        # which names the own network has (XB-K02).
                        refused = True
                        raise _RefusedError from None
                    except NotPublicError:
                        refused = True
                        raise _RefusedError from None
                    url, headers["Host"], extensions = pinned(url, address)
                async with (
                    httpx2.AsyncClient(
                        transport=self._transport,
                        follow_redirects=False,
                        trust_env=False,
                        timeout=httpx2.Timeout(limit, connect=min(CONNECT_TIMEOUT, limit)),
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
        except _UnresolvedError:
            error = UNRESOLVED
        except TimeoutError, httpx2.TimeoutException:
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


UNRESOLVED = "the name server gave no answer for the target's name for now"
"""The error of a request whose host name the name server could not resolve for now
(`EAI_AGAIN`): a status-less failure, tried again like one."""


def _answers_later(failure: OSError) -> bool:
    """Whether the name server failed for now (`EAI_AGAIN`: no answer, or a failure of its own)
    rather than said the name has no address. Someone who may not reach the own network
    cannot bring that about for a name there only, so it tells nothing about them."""
    return isinstance(failure, socket.gaierror) and failure.errno == socket.EAI_AGAIN


class _RefusedError(Exception):
    """The target is not public and the request may not reach it."""


class _UnresolvedError(Exception):
    """The name server could not resolve the target's name for now."""
