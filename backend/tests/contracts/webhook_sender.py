"""Contract suite for `WebhookSender`. A receiver stands in for the other side; the adapter test
provides it (`receiver` fixture). Paths the receiver answers:

- `/status/<code>`: that status code
- `/redirect`: 302 to `/status/200`
- `/slow`: no answer for longer than the timeouts of these tests
"""

from datetime import timedelta
from typing import Protocol

import pytest

from lekto.core.ports.webhook_sender import WebhookRequest, WebhookResponse, WebhookSender

BODY = b'{"id":"e","type":"webhook.test"}'
HEADERS = {"webhook-id": "e", "content-type": "application/json"}


class Receiver(Protocol):
    @property
    def url(self) -> str:
        """The base URL, without a trailing slash."""
        ...

    @property
    def unreachable_url(self) -> str:
        """An address where nobody listens."""
        ...

    @property
    def private_url(self) -> str:
        """The receiver at an address that is not public (the own network or the machine)."""
        ...

    def hits(self, path: str) -> int:
        """How many requests the path has received."""
        ...

    def last_body(self) -> bytes: ...

    def last_headers(self) -> dict[str, str]:
        """Header names in lower case."""
        ...


def request(url: str, timeout: float = 5.0, *, private: bool = True) -> WebhookRequest:
    return WebhookRequest(
        url=url, headers=HEADERS, body=BODY, timeout=timedelta(seconds=timeout), private=private
    )


class WebhookSenderContract:
    @pytest.fixture
    def sender(self) -> WebhookSender:
        raise NotImplementedError

    @pytest.fixture
    def receiver(self) -> Receiver:
        raise NotImplementedError

    async def test_delivers_the_request_as_given(
        self, sender: WebhookSender, receiver: Receiver
    ) -> None:
        response = await sender.send(request(f"{receiver.url}/status/200"))
        assert response.status_code == 200
        assert response.error is None
        assert response.duration_ms >= 0
        assert receiver.last_body() == BODY
        headers = receiver.last_headers()
        assert headers["webhook-id"] == "e"
        assert headers["content-type"] == "application/json"

    async def test_a_target_in_the_own_network_is_reached_only_when_allowed(
        self, sender: WebhookSender, receiver: Receiver
    ) -> None:
        refused = await sender.send(request(f"{receiver.private_url}/status/200", private=False))
        assert (refused.status_code, refused.refused) == (None, True)
        assert refused.error
        assert receiver.private_url not in refused.error
        assert receiver.hits("/status/200") == 0
        allowed = await sender.send(request(f"{receiver.private_url}/status/200"))
        assert (allowed.status_code, allowed.refused) == (200, False)
        assert receiver.hits("/status/200") == 1

    @pytest.mark.parametrize("code", [204, 400, 404, 410, 429, 500, 503])
    async def test_a_status_is_an_answer_not_an_error(
        self, sender: WebhookSender, receiver: Receiver, code: int
    ) -> None:
        response = await sender.send(request(f"{receiver.url}/status/{code}"))
        assert (response.status_code, response.error) == (code, None)

    async def test_redirects_are_not_followed(
        self, sender: WebhookSender, receiver: Receiver
    ) -> None:
        response = await sender.send(request(f"{receiver.url}/redirect"))
        assert (response.status_code, response.error) == (302, None)
        assert receiver.hits("/redirect") == 1
        assert receiver.hits("/status/200") == 0

    async def test_a_receiver_that_does_not_answer_ends_with_an_error(
        self, sender: WebhookSender, receiver: Receiver
    ) -> None:
        response = await sender.send(request(f"{receiver.url}/slow", timeout=0.3))
        assert response.status_code is None
        assert response.error

    async def test_an_unreachable_receiver_ends_with_an_error(
        self, sender: WebhookSender, receiver: Receiver
    ) -> None:
        response = await sender.send(request(receiver.unreachable_url))
        assert response.status_code is None
        assert response.error

    async def test_errors_do_not_name_the_url(
        self, sender: WebhookSender, receiver: Receiver
    ) -> None:
        secret_path = "/hooks/s3cr3t-token"
        response: WebhookResponse = await sender.send(
            request(receiver.unreachable_url + secret_path)
        )
        assert response.error
        assert "s3cr3t-token" not in response.error
