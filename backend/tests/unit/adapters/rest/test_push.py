"""`/push`: the caller's devices for notifications, a test notification, and push switched off."""

import dataclasses
from typing import Any

import httpx2

from lekto.adapters.inbound.rest import PREFIX
from lekto.adapters.outbound.memory import FakePushSender
from lekto.adapters.outbound.memory.push import FAKE_PUBLIC_KEY
from lekto.composition.container import build_memory_container, build_services
from lekto.core.domain.push import PushKind
from lekto.core.ports.push import PushOutcome
from tests.api import auth
from tests.contracts.push import AUTH
from tests.unit.adapters.rest.support import Api, make_app

APPLE = "https://web.push.apple.com/QGuQyavXutnMH9Byyn6xHn"


def subscription(endpoint: str = APPLE, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "endpoint": endpoint,
        "keys": {"p256dh": FAKE_PUBLIC_KEY, "auth": AUTH},
        "name": "iPhone",
        "locale": "de",
    }
    body.update(changes)
    return body


def sender(api: Api) -> FakePushSender:
    push = api.container.push_sender
    assert isinstance(push, FakePushSender)
    return push


async def test_the_server_names_its_key(api: Api) -> None:
    user = await api.user()
    answer = (await api.client.get(f"{PREFIX}/push", headers=auth(user))).json()
    assert answer == {"enabled": True, "public_key": FAKE_PUBLIC_KEY}


async def test_a_device_is_registered_listed_and_removed(api: Api) -> None:
    user = await api.user()
    created = await api.client.post(
        f"{PREFIX}/push/devices", json=subscription(), headers=auth(user)
    )
    assert created.status_code == 201, created.text
    device = created.json()
    assert (device["name"], device["locale"], device["endpoint"]) == ("iPhone", "de", APPLE)
    listed = (await api.client.get(f"{PREFIX}/push/devices", headers=auth(user))).json()
    assert [item["id"] for item in listed] == [device["id"]]
    removed = await api.client.delete(f"{PREFIX}/push/devices/{device['id']}", headers=auth(user))
    assert removed.status_code == 204
    assert (await api.client.get(f"{PREFIX}/push/devices", headers=auth(user))).json() == []


async def test_the_same_browser_belongs_to_whoever_subscribes_last(api: Api) -> None:
    alice, bob = await api.user("alice"), await api.user("bob")
    first = await api.client.post(
        f"{PREFIX}/push/devices", json=subscription(), headers=auth(alice)
    )
    again = await api.client.post(
        f"{PREFIX}/push/devices", json=subscription(name="Safari"), headers=auth(bob)
    )
    assert again.json()["id"] == first.json()["id"]
    assert (await api.client.get(f"{PREFIX}/push/devices", headers=auth(alice))).json() == []
    (device,) = (await api.client.get(f"{PREFIX}/push/devices", headers=auth(bob))).json()
    assert device["name"] == "Safari"


async def test_an_address_of_no_push_service_and_bad_keys_are_refused(api: Api) -> None:
    user = await api.user()
    for endpoint in (
        "https://evil.example/push",
        "http://web.push.apple.com/x",
        "https://10.0.0.1/x",
    ):
        refused = await api.client.post(
            f"{PREFIX}/push/devices", json=subscription(endpoint), headers=auth(user)
        )
        assert refused.status_code == 422, endpoint
        assert refused.json()["reason"]["code"] == "push_endpoint_refused"
    bad = subscription(keys={"p256dh": "AAAA", "auth": AUTH})
    refused = await api.client.post(f"{PREFIX}/push/devices", json=bad, headers=auth(user))
    assert refused.json()["reason"]["code"] == "push_keys_invalid"


async def test_a_person_has_at_most_twenty_devices(api: Api) -> None:
    user = await api.user()
    for number in range(20):
        body = subscription(f"https://fcm.googleapis.com/fcm/send/{number}")
        created = await api.client.post(f"{PREFIX}/push/devices", json=body, headers=auth(user))
        assert created.status_code == 201
    body = subscription("https://fcm.googleapis.com/fcm/send/20")
    refused = await api.client.post(f"{PREFIX}/push/devices", json=body, headers=auth(user))
    assert refused.status_code == 409
    assert refused.json()["reason"]["code"] == "push_devices_limit"


async def test_another_persons_device_is_not_found(api: Api) -> None:
    alice, bob = await api.user("alice"), await api.user("bob")
    device = (
        await api.client.post(f"{PREFIX}/push/devices", json=subscription(), headers=auth(alice))
    ).json()
    for method, path in [("DELETE", ""), ("POST", "/test")]:
        response = await api.client.request(
            method, f"{PREFIX}/push/devices/{device['id']}{path}", headers=auth(bob)
        )
        assert response.status_code == 404


async def test_a_test_notification_and_a_device_the_push_service_forgot(api: Api) -> None:
    user = await api.user()
    device = (
        await api.client.post(f"{PREFIX}/push/devices", json=subscription(), headers=auth(user))
    ).json()
    tested = await api.client.post(f"{PREFIX}/push/devices/{device['id']}/test", headers=auth(user))
    assert tested.json() == {"outcome": "delivered"}
    (sent_to, message) = sender(api).sent[-1]
    assert (sent_to.endpoint, message.kind) == (APPLE, PushKind.TEST)
    listed = (await api.client.get(f"{PREFIX}/push/devices", headers=auth(user))).json()
    assert listed[0]["last_success_at"] is not None
    sender(api).answers = {APPLE: PushOutcome.GONE}
    gone = await api.client.post(f"{PREFIX}/push/devices/{device['id']}/test", headers=auth(user))
    assert gone.json() == {"outcome": "gone"}
    assert (await api.client.get(f"{PREFIX}/push/devices", headers=auth(user))).json() == []


async def test_without_a_key_there_is_no_push(api: Api) -> None:
    container = dataclasses.replace(build_memory_container(api.clock), push_sender=None)
    app = make_app(container, build_services(container))
    user = await Api(container, build_services(container), app, api.client, api.clock).user()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="https://lekto"
    ) as client:
        settings = (await client.get(f"{PREFIX}/push", headers=auth(user))).json()
        assert settings == {"enabled": False, "public_key": None}
        refused = await client.post(
            f"{PREFIX}/push/devices", json=subscription(), headers=auth(user)
        )
        assert refused.status_code == 409
        assert refused.json()["reason"]["code"] == "push_off"
