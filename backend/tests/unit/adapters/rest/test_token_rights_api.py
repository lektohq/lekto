"""API tokens with the rights chosen one by one (`.knowledge/plans/token-rights.md`): created
with a session, shown with their rights and the preset they match, refused where they lack the
right an operation needs; an admin's token without an admin right acts as a user."""

from typing import Any

from lekto.adapters.inbound.rest import PREFIX
from lekto.core.domain.users import Role
from tests.api import auth, bearer
from tests.builders import SAMPLES
from tests.unit.adapters.rest.support import Api

HOME_ASSISTANT = [
    "documents:read",
    "documents:upload",
    "webhooks:read",
    "webhooks:write",
    "system:read",
    "system:write",
    "admin:count_all",
    "admin:mailboxes",
    "admin:private_webhooks",
]


async def _token(api: Api, role: Role, **body: Any) -> tuple[int, dict[str, Any]]:
    user = await api.user(role=role)
    async with api.sign_in(user) as session:
        answer = await session.client.post(
            f"{PREFIX}/auth/tokens", json={"name": "t", **body}, headers=session.headers
        )
    return answer.status_code, answer.json()


async def test_a_token_takes_a_preset_or_rights_one_by_one(api: Api) -> None:
    status, created = await _token(api, Role.USER, rights=["documents:read", "rules:read"])
    assert status == 201, created
    assert created["rights"] == ["documents:read", "rules:read"]
    assert created["scope"] is None
    status, created = await _token(api, Role.USER, rights=["documents:upload"])
    assert (status, created["scope"]) == (201, "upload")

    # A preset carries the admin rights for an admin, and is told as that preset.
    status, created = await _token(api, Role.ADMIN, scope="read")
    assert status == 201
    assert created["scope"] == "read"
    assert "admin:count_all" in created["rights"] and "documents:write" not in created["rights"]
    status, created = await _token(api, Role.USER, scope="read")
    assert created["scope"] == "read"
    assert not [right for right in created["rights"] if right.startswith("admin:")]


async def test_a_token_needs_rights_it_may_have(api: Api) -> None:
    refusals: list[tuple[Role, dict[str, Any], str]] = [
        (Role.USER, {"rights": ["admin:count_all"]}, "token_admin_rights"),
        (Role.ADMIN, {"rights": []}, "token_rights_empty"),
    ]
    for role, body, code in refusals:
        status, answer = await _token(api, role, **body)
        assert status == 422, answer
        assert answer["reason"]["code"] == code
    for body in ({}, {"scope": "read", "rights": ["documents:read"]}, {"rights": ["nonsense"]}):
        status, _ = await _token(api, Role.USER, **body)
        assert status == 422, body


async def test_a_token_reaches_what_its_rights_open(api: Api) -> None:
    user = await api.user()
    async with api.sign_in(user) as session:
        created = await session.client.post(
            f"{PREFIX}/auth/tokens",
            json={"name": "rules", "rights": ["rules:read", "spaces:read"]},
            headers=session.headers,
        )
    headers = bearer(created.json()["token"])
    me = (await api.client.get(f"{PREFIX}/auth/me", headers=headers)).json()
    assert me["rights"] == ["rules:read", "spaces:read"]
    assert me["token_scope"] is None
    assert (await api.client.get(f"{PREFIX}/rules", headers=headers)).status_code == 200
    assert (await api.client.get(f"{PREFIX}/spaces", headers=headers)).status_code == 200
    refused = await api.client.get(f"{PREFIX}/documents", headers=headers)
    assert refused.status_code == 403
    assert refused.json()["reason"] == {
        "code": "token_lacks_right",
        "params": {"right": "documents:read"},
    }
    written = await api.client.post(f"{PREFIX}/spaces", json={"name": "A"}, headers=headers)
    assert written.status_code == 403
    assert written.json()["reason"]["code"] == "read_only_token"  # it holds only reading rights
    session_only = await api.client.get(f"{PREFIX}/auth/tokens", headers=headers)
    assert session_only.status_code == 403

    # A session holds every right of its user.
    me = (await api.client.get(f"{PREFIX}/auth/me", headers=auth(user))).json()
    assert "documents:write" in me["rights"] and "admin:manage" not in me["rights"]


async def test_home_assistant_counts_the_household_and_reads_nothing_of_others(
    api: Api,
) -> None:
    """An admin's token as Home Assistant's: the numbers of every user, its own documents, no
    one else's, no management."""
    admin, owner = await api.admin(), await api.user()
    files = {"file": ("scan.pdf", (SAMPLES / "scan.pdf").read_bytes(), "application/pdf")}
    uploaded = await api.client.post(f"{PREFIX}/documents", files=files, headers=auth(owner))
    assert uploaded.status_code == 202, uploaded.text
    document = uploaded.json()["id"]
    async with api.sign_in(admin) as session:
        created = await session.client.post(
            f"{PREFIX}/auth/tokens",
            json={"name": "Home Assistant", "rights": HOME_ASSISTANT},
            headers=session.headers,
        )
    assert created.status_code == 201, created.text
    headers = bearer(created.json()["token"])

    every = await api.client.get(
        f"{PREFIX}/documents/count", params={"all_users": "true"}, headers=headers
    )
    assert every.status_code == 200, every.text
    assert every.json()["total"] == 1
    summary = await api.client.get(
        f"{PREFIX}/inbox/summary", params={"all_users": "true"}, headers=headers
    )
    assert summary.status_code == 200
    assert (await api.client.get(f"{PREFIX}/mailboxes", headers=headers)).status_code == 200

    listed = await api.client.get(
        f"{PREFIX}/documents", params={"all_users": "true"}, headers=headers
    )
    assert listed.status_code == 403
    assert listed.json()["reason"]["params"] == {"right": "admin:documents_all"}
    assert (
        await api.client.get(f"{PREFIX}/documents/{document}", headers=headers)
    ).status_code == 404
    contact = await api.client.post(
        f"{PREFIX}/contacts", json={"name": "Muster Bäckerei"}, headers=headers
    )
    assert contact.status_code == 403
    users = await api.client.get(f"{PREFIX}/users", headers=headers)
    assert users.status_code == 403  # spaces:read is not among its rights
