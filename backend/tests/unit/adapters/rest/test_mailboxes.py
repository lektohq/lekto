"""`/mailboxes`: admins set up the mailboxes Lekto fetches from; the password never comes back."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from lekto.adapters.inbound.rest import PREFIX
from lekto.adapters.inbound.rest.schemas.mailboxes import (
    ConnectionTestBody,
    MailboxCreate,
    MailboxPatch,
)
from lekto.adapters.outbound.memory import MemoryMailServer
from lekto.core.domain.users import User
from tests.api import auth
from tests.builders import NOW, drain
from tests.mails import LOGIN, plain_mail
from tests.unit.adapters.rest.support import Api, post

ACCOUNT = replace(LOGIN, password="app-password")
"""The account the API's tests make on the memory mail server, as `BODY` signs in."""

BODY = {
    "name": "Household",
    "host": "imap.example.test",
    "port": 993,
    "security": "tls",
    "username": "household@example.test",
    "password": "app-password",
}


def _server(api: Api) -> MemoryMailServer:
    server = api.container.mail_server
    assert isinstance(server, MemoryMailServer)
    return server


async def _test(api: Api, admin: User, extra: dict[str, Any]) -> Any:
    body = {key: BODY[key] for key in ("host", "port", "security", "username")} | extra
    answer = await api.client.post(f"{PREFIX}/mailboxes/test", json=body, headers=auth(admin))
    assert answer.status_code == 200, answer.text
    return answer.json()


async def test_a_mailbox_is_created_tested_changed_and_deleted(api: Api) -> None:
    admin = await api.admin()
    created = await post(
        api, "/mailboxes", {**BODY, "folders": ["INBOX", "Rechnungen"]}, auth(admin)
    )
    assert "password" not in created
    assert (created["folders"], created["interval_minutes"], created["start"]) == (
        ["INBOX", "Rechnungen"],
        5,
        "since_setup",
    )
    assert created["status"] == {
        "last_attempt_at": None,
        "last_success_at": None,
        "error": None,
        "mails": 0,
        "documents": 0,
        "skipped_at": None,
        "skipped": None,
        "step_failed_at": None,
        "step_failed": None,
        "keywords": [],
        "own_keywords": None,
    }
    url = f"{PREFIX}/mailboxes/{created['id']}"

    account = _server(api).add_account(ACCOUNT)
    account.add_folders("Rechnungen")
    account.deliver(
        "INBOX", plain_mail("Markiert"), arrived_at=NOW, flags={"\\Flagged", "Lekto", "$Junk"}
    )
    tested = await _test(api, admin, {"mailbox_id": created["id"]})
    assert tested == {
        "ok": True,
        "folders": ["INBOX", "Rechnungen"],
        "keywords": ["Lekto"],
        "own_keywords": True,
        "error": None,
    }
    refused = await _test(api, admin, {"password": "x"})
    assert refused["ok"] is False and refused["error"]["code"] == "mail_login_failed"

    changed = await api.client.patch(
        url,
        json={"start": "since_date", "since": "2026-01-01", "interval_minutes": 15},
        headers=auth(admin),
    )
    assert changed.status_code == 200, changed.text
    assert (changed.json()["since"], changed.json()["interval_minutes"]) == ("2026-01-01", 15)
    missing_day = await api.client.patch(url, json={"since": None}, headers=auth(admin))
    assert missing_day.status_code == 422

    listed = (await api.client.get(f"{PREFIX}/mailboxes", headers=auth(admin))).json()
    assert [item["name"] for item in listed] == ["Household"]
    assert (await api.client.delete(url, headers=auth(admin))).status_code == 204
    assert (await api.client.get(url, headers=auth(admin))).status_code == 404


def test_a_password_is_not_shown_by_the_bodies() -> None:
    """A body in a log line or an error shows no password."""
    bodies = [
        MailboxCreate.model_validate(BODY),
        MailboxPatch.model_validate({"password": BODY["password"]}),
        ConnectionTestBody.model_validate(
            {key: value for key, value in BODY.items() if key != "name"}
        ),
    ]
    for body in bodies:
        assert "app-password" not in repr(body)


async def test_only_admins(api: Api) -> None:
    user = await api.user()
    answer = await api.client.get(f"{PREFIX}/mailboxes", headers=auth(user))
    assert answer.status_code == 403
    answer = await api.client.post(f"{PREFIX}/mailboxes", json=BODY, headers=auth(user))
    assert answer.status_code == 403


async def test_a_name_is_taken_once(api: Api) -> None:
    admin = await api.admin()
    await post(api, "/mailboxes", BODY, auth(admin))
    again = await api.client.post(
        f"{PREFIX}/mailboxes", json={**BODY, "name": "HOUSEHOLD"}, headers=auth(admin)
    )
    assert again.status_code == 409


async def test_the_log_of_a_mailbox(api: Api) -> None:
    """The mails a mailbox fetched, by outcome and rule, with their documents; a mail no rule
    took names the rule switched on since that takes it at the next fetch."""
    admin, user = await api.admin(), await api.user()
    created = await post(api, "/mailboxes", BODY, auth(admin))
    account = _server(api).add_account(ACCOUNT)
    soon = api.clock.now() + timedelta(minutes=1)
    account.deliver("INBOX", plain_mail("Ihre Rechnung"), arrived_at=soon)
    account.deliver("INBOX", plain_mail("Unser Newsletter"), arrived_at=soon)
    api.clock.advance(timedelta(minutes=2))
    await drain(api.services.mail_intake)
    url = f"{PREFIX}/mailboxes/{created['id']}/mails"
    assert (await api.client.get(url, headers=auth(user))).status_code == 403

    rule = await post(
        api,
        "/mail-rules",
        {
            "mailbox_id": created["id"],
            "name": "Rechnungen",
            "conditions": {"all": [{"field": "subject", "op": "contains", "value": "Rechnung"}]},
            "user_id": str(admin.id),
            "enabled": False,
        },
        auth(admin),
    )
    page = (await api.client.get(url, headers=auth(admin))).json()
    assert (page["total"], page["next_offset"]) == (2, None)
    assert {item["subject"]: item["outcome"] for item in page["items"]} == {
        "Ihre Rechnung": "no_rule",
        "Unser Newsletter": "no_rule",
    }
    assert all(item["waiting"] and item["next_rule"] is None for item in page["items"])

    switched = await api.client.patch(
        f"{PREFIX}/mail-rules/{rule['id']}", json={"enabled": True}, headers=auth(admin)
    )
    assert switched.status_code == 200, switched.text
    summary = (await api.client.get(f"{url}/summary", headers=auth(admin))).json()
    assert summary["counts"] == {"no_rule": 2}
    assert [(item["rule"]["name"], item["mails"]) for item in summary["waiting"]] == [
        ("Rechnungen", 1)
    ]
    assert summary["kept"] == 500 and [item["name"] for item in summary["rules"]] == ["Rechnungen"]

    await drain(api.services.mail_intake)  # switching it on brought the fetch forward
    taken = (await api.client.get(url, params={"outcome": "taken"}, headers=auth(admin))).json()
    (item,) = taken["items"]
    assert (item["subject"], item["rule"], item["rule_id"]) == (
        "Ihre Rechnung",
        "Rechnungen",
        rule["id"],
    )
    assert [document["title"] for document in item["documents"]] == ["Ihre Rechnung"]
    assert item["documents_hidden"] == 0 and not item["waiting"]
    by_rule = await api.client.get(url, params={"rule_id": rule["id"]}, headers=auth(admin))
    assert by_rule.json()["total"] == 1
    paged = (await api.client.get(url, params={"limit": 1}, headers=auth(admin))).json()
    assert (len(paged["items"]), paged["next_offset"]) == (1, 1)


async def test_fetch_now_and_the_origin_of_a_document(api: Api) -> None:
    admin, user = await api.admin(), await api.user()
    created = await post(
        api,
        "/mailboxes",
        {**BODY, "fallback": "everything", "fallback_user_id": str(admin.id)},
        auth(admin),
    )
    account = _server(api).add_account(ACCOUNT)
    account.deliver("INBOX", plain_mail(), arrived_at=api.clock.now() + timedelta(minutes=1))
    api.clock.advance(timedelta(minutes=2))
    await drain(api.services.mail_intake)  # the first fetch, at once after creating
    url = f"{PREFIX}/mailboxes/{created['id']}/fetch"
    assert (await api.client.post(url, headers=auth(user))).status_code == 403
    assert (await api.client.post(url, headers=auth(admin))).status_code == 202

    listed = (await api.client.get(f"{PREFIX}/documents", headers=auth(admin))).json()
    (document,) = listed["items"]
    assert document["channel"] == "mail"
    origin = await api.client.get(
        f"{PREFIX}/documents/{document['id']}/origin", headers=auth(admin)
    )
    assert origin.status_code == 200, origin.text
    mail = origin.json()["mail"]
    assert (mail["mailbox"], mail["role"], mail["subject"], mail["rule"]) == (
        "Household",
        "cover",
        "Ihre Rechnung Oktober",
        None,
    )
    assert mail["sender"] == [
        {"name": "Stadtwerke Musterstadt", "address": "rechnung@stadtwerke.example"}
    ]
    hidden = await api.client.get(f"{PREFIX}/documents/{document['id']}/origin", headers=auth(user))
    assert hidden.status_code == 404

    paused = await api.client.patch(
        f"{PREFIX}/mailboxes/{created['id']}", json={"enabled": False}, headers=auth(admin)
    )
    assert paused.status_code == 200
    assert (await api.client.post(url, headers=auth(admin))).status_code == 422


async def test_mail_rules(api: Api) -> None:
    admin, user = await api.admin(), await api.user()
    mailbox = await post(api, "/mailboxes", BODY, auth(admin))
    body = {
        "mailbox_id": mailbox["id"],
        "name": "Strom",
        "priority": 1,
        "conditions": {
            "any": [
                {"field": "sender", "op": "ends_with", "value": "@stadtwerke.example"},
                {"all": [{"field": "attachments", "op": "present"}], "not": True},
            ]
        },
        "user_id": str(user.id),
        "after": [
            {"action": "add_keyword", "value": "Lekto"},
            {"action": "move", "value": "Lekto/Erledigt"},
        ],
    }
    created = await post(api, "/mail-rules", body, auth(admin))
    assert (created["parts"], created["enabled"], created["text_type_id"]) == ("all", True, None)
    assert created["conditions"] == {
        "any": [
            {"field": "sender", "op": "ends_with", "value": "@stadtwerke.example"},
            {"all": [{"field": "attachments", "op": "present", "value": None}], "not": True},
        ],
        "not": False,
    }
    every = await api.client.patch(
        f"{PREFIX}/mail-rules/{created['id']}", json={"conditions": None}, headers=auth(admin)
    )
    assert every.status_code == 200, every.text
    assert every.json()["conditions"] is None  # every mail
    url = f"{PREFIX}/mail-rules/{created['id']}"
    changed = await api.client.patch(
        url, json={"after": [{"action": "read"}], "enabled": False}, headers=auth(admin)
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["after"] == [{"action": "read", "value": None}]
    wrong = await api.client.patch(
        url,
        json={"after": [{"action": "trash"}, {"action": "read"}]},
        headers=auth(admin),
    )
    assert wrong.status_code == 422  # trashing comes last
    bad = await api.client.patch(url, json={"user_id": None}, headers=auth(admin))
    assert bad.status_code == 422  # it takes something: for whom?
    assert (await api.client.get(f"{PREFIX}/mail-rules", headers=auth(user))).status_code == 403
    listed = (await api.client.get(f"{PREFIX}/mail-rules", headers=auth(admin))).json()
    assert [item["name"] for item in listed] == ["Strom"]
    dry = await api.client.post(
        f"{PREFIX}/mail-rules/dry-run",
        json={**body, "rule_id": created["id"]},
        headers=auth(admin),
    )
    assert dry.status_code == 200, dry.text
    assert dry.json() == []  # nothing fetched yet
    assert (await api.client.delete(url, headers=auth(admin))).status_code == 204
