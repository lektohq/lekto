"""Sending one webhook request.

First adapter: httpx2. The sender only transports: it neither signs nor decides about retries
(that is the delivery service's job), and it never raises for what goes wrong on the way.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from lekto.core.domain.reasons import Reason

REFUSED = "the target has no public address, and this webhook may reach no other"
"""The error of a request refused before it was sent (`WebhookResponse.refused`); every adapter
says it alike. One text for a target in the own network and a name that does not exist, so that
it tells nobody which names the own network has (XB-K02)."""


@dataclass(frozen=True, kw_only=True)
class WebhookRequest:
    """A POST of `body` to `url`. `timeout` is the limit for the whole exchange. `private`:
    whether the target may be an address that is not public (`core.domain.addresses`: the own
    network, the machine itself); if not, the sender refuses such a target without sending."""

    url: str
    headers: Mapping[str, str]
    body: bytes
    timeout: timedelta
    private: bool


@dataclass(frozen=True, kw_only=True)
class WebhookResponse:
    """What came back: the status code, or None and a short `error` if there was no answer
    (unreachable, certificate refused, timeout). `duration_ms` is the time until then. The
    receiver's response body is not part of it: it is not read, kept or logged. `refused`: not
    sent, because the target has an address that is not public, or its name none at all, and
    the request did not allow one (`error` says so); trying again would not change that."""

    status_code: int | None
    duration_ms: int
    error: str | None = None
    refused: bool = False
    reason: Reason | None = None
    """Why Lekto did not send it, with its code (`error` is its text); none for an answer."""


class WebhookSender(Protocol):
    async def send(self, request: WebhookRequest) -> WebhookResponse:
        """Send it once. Redirects are not followed (a 3xx is the answer). A failure on the way
        is the answer, with `status_code` None and an `error` that does not contain the URL
        (it may carry a secret in its path). Without `private`, a host that resolves to an address
        that is not public, or to none, is refused (`refused`); one whose name server does not
        answer for now is not (it may later). The request goes to the address that was checked,
        so that a second answer of the name server cannot lead elsewhere. Never raises."""
        ...
