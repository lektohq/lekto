"""The client's way to Lekto (pylekto underneath): what it repeats, how long it waits and what
a refusal says."""

from collections.abc import Callable

import httpx2
import pytest

from lekto_migration.lekto import ApiError, Lekto
from tests import fake_lekto
from tests.fake_lekto import FakeLekto


def answering(
    *answers: Callable[[httpx2.Request], httpx2.Response],
) -> tuple[httpx2.MockTransport, list[httpx2.Request]]:
    """A transport that gives the answers in turn, then those of an empty Lekto."""
    sent: list[httpx2.Request] = []
    rest = FakeLekto().transport()
    queue = list(answers)

    def handle(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        if queue:
            return queue.pop(0)(request)
        return rest.handle_request(request)

    return httpx2.MockTransport(handle), sent


def status(code: int, **headers: str) -> Callable[[httpx2.Request], httpx2.Response]:
    body = {"title": "error", "status": code, "detail": f"status {code}"}
    return lambda request: httpx2.Response(code, json=body, headers=headers)


def dropped(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("refused", request=request)


def calling(transport: httpx2.MockTransport, waited: list[float] | None = None) -> Lekto:
    async def sleep(seconds: float) -> None:
        if waited is not None:
            waited.append(seconds)

    return Lekto("http://lekto", fake_lekto.TOKEN, transport=transport, sleep=sleep)


async def test_server_errors_and_a_dropped_connection_are_repeated() -> None:
    waited: list[float] = []
    transport, sent = answering(status(503), dropped, status(502))
    lekto = calling(transport, waited)
    assert [u["username"] for u in await lekto.users()] == ["root"]
    assert (len(sent), waited) == (4, [1.0, 3.0, 10.0])
    await lekto.close()


async def test_too_many_requests_waits_as_long_as_lekto_says() -> None:
    waited: list[float] = []
    transport, _ = answering(
        status(429, **{"Retry-After": "7"}), status(429, **{"Retry-After": "600"}), status(429)
    )
    lekto = calling(transport, waited)
    await lekto.users()
    assert waited == [7.0, 60.0, 5.0]  # at most a minute; five without a number
    await lekto.close()


async def test_what_is_still_failing_after_the_repeats_is_an_api_error() -> None:
    transport, _ = answering(*[dropped] * 4)
    lekto = calling(transport)
    with pytest.raises(ApiError, match=r"HTTP 0: Lekto is not reachable: ConnectError"):
        await lekto.users()
    await lekto.close()
    transport, sent = answering(*[status(503)] * 4)
    lekto = calling(transport)
    with pytest.raises(ApiError) as raised:
        await lekto.users()
    assert (raised.value.status, raised.value.detail, len(sent)) == (503, "status 503", 4)
    await lekto.close()


async def test_a_refusal_is_not_repeated_and_names_a_duplicate() -> None:
    existing = "00000000-0000-0000-0000-000000000042"

    def conflict(request: httpx2.Request) -> httpx2.Response:
        body = {"title": "Conflict", "status": 409, "existing_document_id": existing}
        return httpx2.Response(409, json=body)

    transport, sent = answering(conflict)
    lekto = calling(transport)
    with pytest.raises(ApiError) as raised:
        await lekto.create_contact("ACME Energy")
    assert (raised.value.status, raised.value.detail, raised.value.existing) == (
        409,
        "Conflict",
        existing,
    )
    assert len(sent) == 1
    await lekto.close()


async def test_a_value_pylekto_refuses_is_not_sent() -> None:
    transport, sent = answering()
    lekto = calling(transport)
    with pytest.raises(ApiError, match="not sent") as raised:
        await lekto.align(fake_lekto.ADMIN["id"], {"no_such_value": 1})
    assert (raised.value.status, sent) == (422, [])
    await lekto.close()
