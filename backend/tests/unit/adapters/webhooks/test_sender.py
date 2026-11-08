"""The httpx2 sender against a receiver on the loopback interface: the contracts, and what the
contract cannot say (the headers it adds, certificate errors)."""

from collections.abc import AsyncIterator
from datetime import timedelta

import httpx2
import pytest

from lekto import __version__
from lekto.adapters.outbound.webhooks import HttpWebhookSender
from lekto.core.ports.webhook_sender import WebhookRequest, WebhookSender
from tests.contracts.webhook_sender import Receiver, WebhookSenderContract, request
from tests.webhook_receiver import LocalReceiver


class TestHttpWebhookSender(WebhookSenderContract):
    @pytest.fixture
    def sender(self) -> WebhookSender:
        return HttpWebhookSender(user_agent=f"Lekto/{__version__}")

    @pytest.fixture
    async def receiver(self) -> AsyncIterator[Receiver]:
        async with LocalReceiver() as receiver:
            yield receiver

    async def test_sends_a_post_with_a_user_agent(
        self, sender: WebhookSender, receiver: LocalReceiver
    ) -> None:
        await sender.send(request(f"{receiver.url}/status/200"))
        sent = receiver.received[-1]
        assert sent.method == "POST"
        assert sent.headers["user-agent"] == f"Lekto/{__version__}"

    async def test_the_timeout_covers_the_whole_exchange(
        self, sender: WebhookSender, receiver: LocalReceiver
    ) -> None:
        response = await sender.send(request(f"{receiver.url}/slow", timeout=0.3))
        assert response.error == "no answer within 0.3 seconds"
        assert response.duration_ms < 3000

    async def test_a_certificate_error_is_named_without_the_url(
        self, receiver: LocalReceiver
    ) -> None:
        # The receiver speaks plain HTTP: the TLS handshake fails.
        sender = HttpWebhookSender()
        response = await sender.send(
            request(receiver.url.replace("http://", "https://") + "/hooks/token")
        )
        assert response.status_code is None
        assert response.error
        assert "token" not in response.error

    async def test_an_unusable_address_is_an_error_too(self, sender: WebhookSender) -> None:
        response = await sender.send(
            WebhookRequest(
                url="http://[::1:99999/x",
                headers={},
                body=b"{}",
                timeout=timedelta(seconds=1),
                private=True,
            )
        )
        assert response.status_code is None
        assert response.error


class _Network:
    """A name server and a network that record what the sender asks and where it connects."""

    def __init__(self, names: dict[str, list[str]]) -> None:
        self.names = names
        self.sent: list[httpx2.Request] = []

    async def resolve(self, host: str) -> list[str]:
        if host not in self.names:
            raise OSError(f"{host} resolves to no address")
        return self.names[host]

    def transport(self) -> httpx2.MockTransport:
        def answer(request: httpx2.Request) -> httpx2.Response:
            self.sent.append(request)
            return httpx2.Response(204)

        return httpx2.MockTransport(answer)


def _sender(network: _Network) -> HttpWebhookSender:
    return HttpWebhookSender(transport=network.transport(), resolver=network.resolve)


async def test_a_public_target_is_reached_at_the_address_that_was_checked() -> None:
    network = _Network({"hooks.example.org": ["93.184.216.34", "2606:2800:220:1::"]})
    response = await _sender(network).send(
        request("https://hooks.example.org:8443/in", private=False)
    )
    assert (response.status_code, response.refused) == (204, False)
    (sent,) = network.sent
    assert sent.url.host == "93.184.216.34" and sent.url.port == 8443
    assert sent.headers["host"] == "hooks.example.org:8443"
    assert sent.extensions["sni_hostname"] == "hooks.example.org"


@pytest.mark.parametrize(
    ("url", "names"),
    [
        ("http://hooks.example.org/in", {"hooks.example.org": ["93.184.216.34", "10.0.0.5"]}),
        ("http://localhost:1880/flows", {"localhost": ["127.0.0.1", "::1"]}),
        ("http://ollama:11434/api/pull", {"ollama": ["172.18.0.4"]}),
        ("http://192.168.178.1/", {}),
        ("http://[::ffff:127.0.0.1]/", {}),  # mapped
        ("http://[64:ff9b::a00:5]/", {}),  # NAT64 of 10.0.0.5
        ("http://169.254.169.254/latest", {}),  # a cloud's metadata service
    ],
)
async def test_a_target_with_an_address_that_is_not_public_is_refused(
    url: str, names: dict[str, list[str]]
) -> None:
    network = _Network(names)
    response = await _sender(network).send(request(url, private=False))
    assert (response.status_code, response.refused) == (None, True)
    assert response.error and "ollama" not in response.error
    assert network.sent == []


async def test_a_name_that_does_not_resolve_is_a_failure_not_a_refusal() -> None:
    network = _Network({})
    response = await _sender(network).send(request("https://hooks.example.org/in", private=False))
    assert (response.status_code, response.refused) == (None, False)
    assert response.error
    assert network.sent == []


async def test_with_leave_the_own_network_is_reached_as_the_url_says() -> None:
    network = _Network({})
    response = await _sender(network).send(request("http://ollama:11434/api/tags"))
    assert response.status_code == 204
    (sent,) = network.sent
    assert sent.url.host == "ollama"
