"""Every domain error a request can raise answers with a status of its own, not 500 (M13 review
A-06)."""

from uuid import UUID

from lekto.adapters.inbound.rest import PREFIX
from lekto.adapters.inbound.rest.problems import NOT_FROM_REQUESTS, STATUSES
from lekto.core.domain import errors
from lekto.core.domain.errors import DomainError
from tests.api import auth
from tests.unit.adapters.rest.support import Api, post, upload


def _domain_errors() -> set[type[DomainError]]:
    found: set[type[DomainError]] = set()
    stack: list[type[DomainError]] = [DomainError]
    while stack:
        for kind in stack.pop().__subclasses__():
            if kind not in found:
                found.add(kind)
                stack.append(kind)
    return found


def test_every_domain_error_has_a_status_or_never_reaches_a_route() -> None:
    every = {
        kind
        for kind in vars(errors).values()
        if isinstance(kind, type) and issubclass(kind, DomainError) and kind is not DomainError
    }
    assert every <= _domain_errors()
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
