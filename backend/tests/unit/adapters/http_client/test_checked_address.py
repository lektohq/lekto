"""The address check against DNS rebinding the logo fetcher and the webhook sender share
(AD-13)."""

from collections.abc import Sequence

import httpx2
import pytest

from lekto.adapters.outbound.http_client.resolver import NotPublicError, checked_address, pinned

PUBLIC, OTHER, PRIVATE = "93.184.216.34", "93.184.216.35", "10.0.0.7"


def answering(*addresses: str):  # type: ignore[no-untyped-def]
    async def resolve(host: str) -> Sequence[str]:
        return list(addresses)

    return resolve


async def test_the_first_address_once_every_one_is_public() -> None:
    assert await checked_address(answering(PUBLIC, OTHER), "muster.example") == PUBLIC
    assert await checked_address(answering(), PUBLIC) == PUBLIC  # its own, not resolved


@pytest.mark.parametrize("addresses", [(PUBLIC, PRIVATE), (PRIVATE,)])
async def test_one_address_that_is_not_public_refuses_the_host(addresses: tuple[str, ...]) -> None:
    with pytest.raises(NotPublicError):
        await checked_address(answering(*addresses), "muster.example")
    with pytest.raises(NotPublicError):
        await checked_address(answering(), PRIVATE)


async def test_a_name_without_an_address_is_a_failure_that_may_pass() -> None:
    with pytest.raises(OSError, match="no address"):
        await checked_address(answering(), "muster.example")


def test_the_request_goes_to_the_address_in_the_host_s_name() -> None:
    url, host, extensions = pinned(httpx2.URL("https://muster.example:8443/hook?x=1"), PUBLIC)
    assert str(url) == f"https://{PUBLIC}:8443/hook?x=1"
    assert (host, extensions) == ("muster.example:8443", {"sni_hostname": "muster.example"})
    url, host, extensions = pinned(httpx2.URL("http://muster.example/hook"), PUBLIC)
    assert (str(url), host, extensions) == (f"http://{PUBLIC}/hook", "muster.example", {})
