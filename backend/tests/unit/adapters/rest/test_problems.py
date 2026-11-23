"""Every domain error a request can raise answers with a status of its own, not 500 (M13 review
A-06)."""

import importlib
import pkgutil
from uuid import UUID, uuid4

import pytest

import lekto.adapters
import lekto.core
from lekto.adapters.inbound.rest import PREFIX
from lekto.adapters.inbound.rest.problems import NOT_FROM_REQUESTS, STATUSES
from lekto.adapters.inbound.schemas import MAX_POSITION
from lekto.core.domain.errors import DomainError
from lekto.core.domain.users import UserDeletionBlockedError
from lekto.core.ports.mail_server import MailServerError
from tests.api import auth
from tests.unit.adapters.rest.support import Api, post, upload


def _domain_errors() -> set[type[DomainError]]:
    """Every domain error of Lekto, wherever it is defined: the core and the adapters are
    imported first (the migrations aside, which run on import)."""
    for package in (lekto.core, lekto.adapters):
        for info in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
            if ".migrations" not in info.name:
                importlib.import_module(info.name)
    found: set[type[DomainError]] = set()
    stack: list[type[DomainError]] = [DomainError]
    while stack:
        for kind in stack.pop().__subclasses__():
            if kind not in found:
                found.add(kind)
                stack.append(kind)
    return {kind for kind in found if kind.__module__.startswith("lekto.")}


def test_every_domain_error_has_a_status_or_never_reaches_a_route() -> None:
    """Not only those of `errors.py`: one defined in a port or an adapter reaches a route as
    well (TC-01)."""
    every = _domain_errors()
    assert {MailServerError, UserDeletionBlockedError} <= every
    mapped = [kind for kind, _ in STATUSES]
    unmapped = {
        kind
        for kind in every
        if not any(issubclass(kind, base) for base in mapped) and kind not in NOT_FROM_REQUESTS
    }
    assert unmapped == set()
    assert not any(issubclass(kind, base) for kind in NOT_FROM_REQUESTS for base in mapped)


EDGES = ("9999-12-31T23:59:59-14:00", "0001-01-01T00:00:00+14:00")
"""Moments with an offset that lie beyond the calendar in UTC."""


async def test_a_moment_beyond_the_calendar_is_a_422(api: Api) -> None:
    """An API token's `expires_at`, a document's `created_at` (RB-01, RA-13)."""
    owner = await api.user()
    id = await upload(api, auth(owner))
    for edge in EDGES:
        async with api.sign_in(owner) as session:
            token = await session.client.post(
                f"{PREFIX}/auth/tokens",
                json={"name": "edge", "scope": "read", "expires_at": edge},
                headers=session.headers,
            )
        assert token.status_code == 422, token.text
        for path in ("", "/dry-run"):
            send = api.client.post if path else api.client.patch
            changed = await send(
                f"{PREFIX}/documents/{id}{path}", json={"created_at": edge}, headers=auth(owner)
            )
            assert changed.status_code == 422, (path, changed.text)
            assert "beyond the calendar" in changed.json()["detail"]


async def test_an_unexpected_error_is_marked_like_every_answer(api: Api) -> None:
    """Not cached, not sniffed, no referrer: also a 500, which passes no middleware (RB-03)."""

    async def broken() -> None:
        raise RuntimeError("broken")

    api.app.add_api_route(f"{PREFIX}/broken", broken)
    async with api.new_client(raise_app_exceptions=False) as client:
        response = await client.get(f"{PREFIX}/broken")
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


async def test_an_unexpected_error_is_logged_with_its_request(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    """Method and path, without the query: which request broke (RB-K08)."""

    async def broken() -> None:
        raise RuntimeError("broken")

    api.app.add_api_route(f"{PREFIX}/broken", broken, methods=["POST"])
    async with api.new_client(raise_app_exceptions=False) as client:
        await client.post(f"{PREFIX}/broken?secret=1")
    (record,) = [item for item in caplog.records if item.getMessage() == "request failed"]
    assert (vars(record)["method"], vars(record)["path"]) == ("POST", f"{PREFIX}/broken")


async def test_a_number_beyond_what_the_database_holds_is_a_422(api: Api) -> None:
    """Offsets and version numbers end at `MAX_POSITION`: beyond, they failed in the database
    with a 500 (RB-04)."""
    admin = await api.admin()
    missing = uuid4()
    paths = [
        f"/rules/{missing}/versions/{{n}}",
        f"/documents/{missing}/versions/{{n}}/original",
        "/jobs?offset={n}",
        "/documents?offset={n}",
        "/identifiers/open?offset={n}",
        f"/webhooks/{missing}/deliveries?offset={{n}}",
        f"/mailboxes/{missing}/mails?offset={{n}}",
    ]
    for path in paths:
        beyond = await api.client.get(PREFIX + path.format(n=MAX_POSITION + 1), headers=auth(admin))
        assert beyond.status_code == 422, path
        at = await api.client.get(PREFIX + path.format(n=MAX_POSITION), headers=auth(admin))
        assert at.status_code in (200, 404), (path, at.text)
    applied = await api.client.post(
        f"{PREFIX}/rules/{missing}/apply",
        json={"version": MAX_POSITION + 1, "document_ids": []},
        headers=auth(admin),
    )
    assert applied.status_code == 422


async def test_a_nul_in_a_text_of_a_body_is_a_422(api: Api) -> None:
    """Postgres takes no NUL: it is refused where it comes in, in a name, in a document's title,
    deep in a rule (RB-08)."""
    admin = await api.admin()
    id = await upload(api, auth(admin))
    rule = {
        "name": "Rule",
        "conditions": {"all": [{"field": "title", "op": "contains", "value": "a\x00b"}]},
        "actions": [{"type": "add_tags", "tag_names": ["x"]}],
    }
    for method, path, body in (
        ("POST", "/tags", {"name": "a\x00b"}),
        ("PATCH", f"/documents/{id}", {"title": "a\x00b"}),
        ("POST", "/rules", rule),
    ):
        response = await api.client.request(method, PREFIX + path, json=body, headers=auth(admin))
        assert response.status_code == 422, (path, response.text)
        assert "NUL" in response.json()["detail"], path


async def test_a_refusal_names_its_code_beside_the_text(api: Api) -> None:
    a = auth(await api.admin())
    await post(api, "/document-types", {"name": "Invoice"}, a)
    taken = await api.client.post(f"{PREFIX}/document-types", json={"name": "Invoice"}, headers=a)
    assert taken.status_code == 409
    assert taken.json()["detail"] == "'Invoice' already exists"
    assert taken.json()["reason"] == {"code": "name_taken", "params": {"name": "Invoice"}}
    missing = await api.client.get(f"{PREFIX}/contacts/{UUID(int=1)}", headers=a)
    assert missing.status_code == 404
    assert missing.json()["reason"] == {
        "code": "not_found",
        "params": {"kind": "contact", "id": str(UUID(int=1))},
    }


async def test_a_request_that_does_not_fit_names_each_part_with_its_code(api: Api) -> None:
    a = auth(await api.admin())
    response = await api.client.post(
        f"{PREFIX}/document-types", json={"name": "x" * 201, "icon": 7, "extra": 1}, headers=a
    )
    assert response.status_code == 422
    body = response.json()
    by_field = {item["field"]: item["reason"] for item in body["errors"]}
    assert by_field["name"]["code"] == "input_too_long"
    assert by_field["name"]["params"] == {"max": 200}
    assert by_field["icon"]["code"] == "input_not_text"
    assert by_field["extra"]["code"] == "input_unknown"
    assert body["detail"].startswith("name: String should have at most 200 characters")
