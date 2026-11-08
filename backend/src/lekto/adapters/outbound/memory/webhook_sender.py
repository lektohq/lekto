"""A stand-in webhook receiver for tests: the test decides what each request is answered with."""

from collections.abc import Callable
from urllib.parse import urlsplit

from lekto.core.domain.addresses import is_public, literal
from lekto.core.ports.webhook_sender import WebhookRequest, WebhookResponse

REFUSED = "the target has an address in the own network, which this webhook may not reach"

type Answer = int | str | Exception
"""A status code, or an error text (no answer), or an exception that is turned into an error."""


class FakeWebhookSender:
    """Records the requests it sends. Answers with 200 unless `answers` is given: a list used
    in turn (the last one stays), or a function of the request. Without `private`, it refuses
    `localhost` and an address that is not public, and sends nothing; it asks no name server,
    so any other name counts as public."""

    def __init__(
        self, answers: list[Answer] | Callable[[WebhookRequest], Answer] | None = None
    ) -> None:
        self.requests: list[WebhookRequest] = []
        self.answers: list[Answer] | Callable[[WebhookRequest], Answer] = (
            [200] if answers is None else answers
        )

    async def send(self, request: WebhookRequest) -> WebhookResponse:
        if not request.private and _private(request.url):
            return WebhookResponse(status_code=None, duration_ms=0, error=REFUSED, refused=True)
        self.requests.append(request)
        if callable(self.answers):
            answer = self.answers(request)
        else:
            answer = self.answers[min(len(self.requests), len(self.answers)) - 1]
        if isinstance(answer, int):
            return WebhookResponse(status_code=answer, duration_ms=5)
        text = type(answer).__name__ if isinstance(answer, Exception) else answer
        return WebhookResponse(status_code=None, duration_ms=5, error=text)


def _private(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    address = literal(host)
    return address is not None and not is_public(address)
