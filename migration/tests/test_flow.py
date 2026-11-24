"""The phases end to end against stand-ins for both APIs: plan, check, prepare, run."""

import asyncio
import json
import sqlite3
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from pylekto import API_VERSION

from lekto_migration import plan as plans
from lekto_migration.basis import Basis
from tests import fake_lekto
from tests.conftest import Setup

PAPERLESS_KEY = "paperless-test-key"


def by_title(setup: Setup, title: str) -> dict[str, Any]:
    return next(d for d in setup.lekto.documents.values() if d["title"] == title)


def named(items: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    return next(i for i in items.values() if i.get("name", i.get("username")) == name)


def row(report: dict[str, Any], id: int) -> dict[str, Any]:
    return next(d for d in report["documents"] if d["id"] == id)


# --- plan -------------------------------------------------------------------------------------


async def test_the_first_plan_is_written_from_what_both_sides_hold(setup: Setup) -> None:
    id = str(uuid4())
    setup.lekto.contacts[id] = {"id": id, "name": "ACME ENERGY", "group_ids": []}
    assert await setup.run("plan") == 0
    assert setup.lekto.writes() == []
    assert all(method == "GET" for method, _ in setup.paperless.requests)
    plan, _ = plans.load(setup.plan_path)
    assert (plan.source, plan.target) == ("http://paperless", "http://lekto")
    acme = plan.entry("correspondents", "ACME Energy")
    assert acme is not None and acme.targets == (plans.Target("contact", "ACME Energy"),)
    unused = plan.entry("correspondents", "Unused")
    assert unused is not None and unused.targets[0].create
    report = setup.report("plan")
    assert report["written"] and report["problems"] == []
    assert report["entries"]["tags"] == {"entries": 2, "dropped": 0}
    assert setup.questions == []  # a new plan needs no question


async def test_a_second_plan_adds_what_is_new_and_asks_first(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    assert await setup.run("plan") == 0  # up to date: nothing asked
    assert setup.questions == []
    setup.archive.tags.append({"id": 9, "name": "Insurance", "parent": None})
    before = setup.plan_path.read_text()
    setup.answer = False
    assert await setup.run("plan") == 1
    assert setup.plan_path.read_text() == before and len(setup.questions) == 1
    setup.answer = True
    assert await setup.run("plan") == 0
    assert "Insurance: {to: tag, name: Insurance, create: true}" in setup.plan_path.read_text()
    assert setup.report("plan")["changes"]["added"] == ["tags.Insurance"]


async def test_a_plan_belongs_to_one_paperless_and_one_lekto(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    assert await setup.run("plan", lekto_url="http://elsewhere") == 2
    assert await setup.run("check", paperless_url="http://other") == 2


@pytest.mark.parametrize("written", ["", "- a list\n", "settings: [\n"])
async def test_a_plan_file_that_is_no_plan_stops_every_command_alike(
    setup: Setup, written: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Empty, a list or no YAML at all: a problem of the plan for `plan` too, no traceback
    (MI-06)."""
    setup.plan_path.write_text(written, encoding="utf-8")
    for command in ("plan", "check"):
        assert await setup.run(command) == 2
        assert "migration-plan.yaml" in capsys.readouterr().err


def answering(status: int, **response: Any) -> Callable[[], httpx2.MockTransport]:
    return lambda: httpx2.MockTransport(lambda request: httpx2.Response(status, **response))


async def test_an_answer_that_is_no_json_stops_with_a_word_not_a_traceback(
    setup: Setup, capsys: pytest.CaptureFixture[str]
) -> None:
    """An address that is sent on (`http` to `https`) or a proxy's sign-in page: what went
    wrong, exit 2 (MI-07)."""
    real = setup.paperless.transport
    page = {"text": "<html>Sign in</html>", "headers": {"content-type": "text/html"}}
    for transport, said in (
        (answering(301, headers={"location": "https://paperless.example/"}), "sent on to"),
        (answering(200, **page), "no JSON in the answer (text/html)"),
    ):
        setup.paperless.transport = transport  # type: ignore[method-assign]
        assert await setup.run("plan") == 2
        assert said in capsys.readouterr().err
    setup.paperless.transport = real  # type: ignore[method-assign]
    for transport, said in (
        (answering(308, headers={"location": "https://lekto.example/"}), "sent on to"),
        (answering(200, **page), "no JSON in the answer (text/html)"),
    ):
        setup.lekto.transport = transport  # type: ignore[method-assign]
        assert await setup.run("plan") == 2
        assert said in capsys.readouterr().err


async def test_a_plan_with_problems_is_reported(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    setup.edit("tags", "tax", "{to: shelf, name: x}")
    assert await setup.run("plan") == 1
    assert any("tags.tax.to" in p for p in setup.report("plan")["problems"])
    assert await setup.run("check") == 2  # a plan that cannot be read stops the others
    setup.edit("tags", "tax", "{to: tag, name: Taxes}")  # no create: missing in Lekto
    assert await setup.run("plan") == 1
    assert any("tag 'Taxes' does not exist" in p for p in setup.report("plan")["problems"])


async def test_without_a_plan_nothing_else_runs(setup: Setup) -> None:
    for command in ("check", "prepare", "run"):
        assert await setup.run(command) == 2
    assert setup.lekto.writes() == []


# --- check and prepare ------------------------------------------------------------------------


async def test_the_cold_run_says_what_would_happen_and_writes_nothing(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    assert await setup.run("check") == 0
    assert setup.lekto.writes() == [] and setup.paperless.downloads == []
    assert not (setup.directory / "state.sqlite").exists()
    report = setup.report("check")
    assert report["document_results"] == {"new": 8, "skipped": 2}
    statuses = {(a["kind"], a["status"]) for a in report["actions"]}
    assert ("user", "create") in statuses and ("space", "create") in statuses
    ten = row(report, 10)
    assert ten["becomes"]["contact"] == "ACME Energy"
    assert ten["becomes"]["sources"]["contact"] == "correspondent 'ACME Energy'"
    assert "user 'johndoe'" in ten["prepare"]
    text = (setup.directory / "reports" / "check.md").read_text()
    assert "## New documents (8)" in text and "wordprocessingml" in text
    assert PAPERLESS_KEY not in text and fake_lekto.TOKEN not in text


async def test_the_cold_run_says_who_sees_a_document_beyond_paperless(setup: Setup) -> None:
    """The plan puts ACME's documents of johndoe (10) and erika (12) into one space: each sees
    the other's there, which Paperless did not let them."""
    assert await setup.run("plan") == 0
    setup.edit(
        "correspondents",
        "ACME Energy",
        "[{to: contact, name: ACME Energy, create: true},"
        " {to: space, name: Energie, create: true}]",
    )
    assert await setup.run("check") == 0
    report = setup.report("check")
    ten, twelve = row(report, 10), row(report, 12)
    assert ten["becomes"]["members"] == ["erika: edit", "johndoe: edit"]
    assert (ten["becomes"]["beyond"], twelve["becomes"]["beyond"]) == (["erika"], ["johndoe"])
    space = next(a for a in report["actions"] if a["kind"] == "space" and a["name"] == "Energie")
    assert "erika and johndoe see each other's documents in 'Energie'" in space["notes"]
    text = (setup.directory / "reports" / "check.md").read_text()
    assert "## New documents visible beyond Paperless' permissions" in text
    # In their personal spaces only the uploader sees a document.
    setup.edit("correspondents", "ACME Energy", "{to: contact, name: ACME Energy, create: true}")
    assert await setup.run("check") == 0
    ten = row(setup.report("check"), 10)
    assert (ten["becomes"]["members"], ten["becomes"]["beyond"]) == (["johndoe: edit"], [])


async def test_a_bound_that_does_not_fit_its_field_stops_the_commands(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    setup.edit("documents", "exclude", "{custom_fields: {Due: {from: 2024}}}")
    assert await setup.run("check") == 2  # a date field: from a day


async def test_a_plan_cannot_name_a_shared_space_like_a_personal_one(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    setup.edit("storage_paths", "Bank", "{to: space, name: Persönlich, create: true}")
    assert await setup.run("check") == 2


async def test_run_waits_for_prepare_and_prepare_for_a_complete_plan(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    assert await setup.run("run") == 2
    assert setup.lekto.uploads == []
    setup.archive.tags.append({"id": 9, "name": "Insurance", "parent": None})
    assert await setup.run("prepare") == 2  # the plan lacks the new tag
    assert await setup.run("check") == 1
    assert "run plan" in setup.report("check")["problems"][0]


async def test_prepare_asks_and_creates_the_master_data(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    setup.answer = False
    assert await setup.run("prepare") == 1
    assert setup.lekto.writes() == []
    setup.answer = True
    assert await setup.run("prepare") == 0
    lekto = setup.lekto
    assert {u["username"] for u in lekto.users.values()} == {
        "root",
        "johndoe",
        "erika",
        "bob",
        "gone",
    }
    assert named(lekto.users, "gone")["active"] is True  # deactivated at the end of the run
    assert sorted(c["name"] for c in lekto.contacts.values()) == ["ACME Energy", "Unused"]
    tags = {t["name"]: t for t in lekto.tags.values()}
    assert tags["tax/2024"]["parent_id"] == tags["tax"]["id"]
    assert "Notizen" not in {f["name"] for f in lekto.fields.values()}
    assert named(lekto.fields, "Kind")["choices"] == ["One", "Two"]
    # One space for each combination of members: document 13's and document 16's (gone,
    # deactivated in Paperless, reads it as Paperless lets them).
    assert sum(1 for s in lekto.spaces.values() if s["personal_of"] is None) == 2
    writes = len(lekto.writes())
    assert await setup.run("prepare") == 0  # nothing left to do
    assert len(lekto.writes()) == writes


async def test_profiles_are_filled_once_and_never_hold_the_run_back(setup: Setup) -> None:
    """An existing user without a name gets an e-mail alone; a name another user has and an
    address Lekto refuses are left out. None of it is an open need for `run`, and a second
    `prepare` does not ask Lekto again."""
    lekto = setup.lekto
    johndoe = lekto.add_user("johndoe")
    lekto.add_user("carla", display_name="Bob")
    for user in setup.archive.users:
        if user["username"] == "johndoe":
            user["email"] = "johndoe@mail.example"
        elif user["username"] == "erika":
            user["email"] = "erika@localhost"
    assert await setup.run("plan") == 0
    assert await setup.run("prepare") == 0
    assert lekto.profiles[johndoe]["email"] == "johndoe@mail.example"
    erika = named(lekto.users, "erika")
    assert erika["display_name"] == "Erika Mustermann"
    assert not lekto.profiles[erika["id"]]["email"]
    assert not named(lekto.users, "bob").get("display_name")
    notes = {a["name"]: a["notes"] for a in setup.report("prepare")["actions"]}
    assert any("refused by Lekto" in note for note in notes["erika"])
    assert any("is taken" in note for note in notes["bob"])
    assert await setup.run("check") == 0
    users = [a for a in setup.report("check")["actions"] if a["kind"] == "user"]
    assert {a["status"] for a in users} == {"exists"}
    writes = len(lekto.writes())
    assert await setup.run("prepare") == 0  # asked once
    assert len(lekto.writes()) == writes
    assert await setup.run("run") == 0


# --- the migration ----------------------------------------------------------------------------


async def test_the_migration_takes_everything_over(setup: Setup) -> None:
    assert await setup.migrate() == 0
    lekto = setup.lekto
    assert named(lekto.users, "gone")["active"] is False and named(lekto.users, "bob")["active"]
    assert len(lekto.documents) == 8
    first = by_title(setup, "Document 10")
    assert first["channel"] == "migration"
    assert first["uploaded_by"] == named(lekto.users, "johndoe")["id"]
    assert first["space_id"] == fake_lekto.personal_id(first["uploaded_by"])
    assert first["document_date"] == "2024-05-01"
    assert datetime.fromisoformat(first["created_at"]) == datetime(2024, 4, 2, 7, 30, tzinfo=UTC)
    assert first["contact_id"] == named(lekto.contacts, "ACME Energy")["id"]
    assert first["document_type_id"] == named(lekto.document_types, "Invoice")["id"]
    assert len(first["tag_ids"]) == 2
    values = {lekto.fields[k]["name"]: v for k, v in first["fields"].items()}
    assert values == {
        "Text": "Hello",
        "Long": "Some long text",
        "Site": "https://example.org/x",
        "Due": "2024-06-30",
        "Paid": True,
        "Count": "42",
        "Ratio": "1.5",
        "Net": {"amount": "12.50", "currency": "USD"},
        "Gross": {"amount": "99.90", "currency": "EUR"},
        "Kind": "Two",
        "ASN": "77",
    }
    assert by_title(setup, "Document 11")["fields"] == {}  # an invalid URL is left out
    assert by_title(setup, "Document 14")["uploaded_by"] == fake_lekto.ADMIN["id"]
    assert by_title(setup, "Document 15")["uploaded_by"] == fake_lekto.ADMIN["id"]
    assert lekto.spaces[by_title(setup, "Document 12")["space_id"]]["personal_of"] is not None
    shared = by_title(setup, "Document 13")
    space = lekto.spaces[shared["space_id"]]
    assert space["name"] == "Geteilt: bob (lesen), erika (bearbeiten), johndoe (bearbeiten)"
    erika = named(lekto.users, "erika")["id"]
    assert shared["uploaded_by"] == erika
    assert {"user_id": erika, "role": "edit"} in space["members"]
    upload = next(u for u in lekto.uploads if u["filename"] == "scan-13.pdf")
    assert upload["channel"] == "migration" and upload["space_id"] == space["id"]
    assert upload["uploaded_by"] == erika
    assert json.loads(upload["metadata"])["review"] == []
    report = setup.report("run")
    assert report["document_results"] == {"done": 8, "skipped": 2}
    assert report["lanes"] == {"green": 8}
    ten = row(report, 10)
    assert "2 notes are not taken over (Lekto has no notes)" in ten["notes"]


async def test_after_the_migration_the_check_finds_everything_the_same(setup: Setup) -> None:
    assert await setup.migrate() == 0
    assert await setup.run("check") == 0
    report = setup.report("check")
    assert report["document_results"] == {"same": 8, "skipped": 2}
    assert {a["status"] for a in report["actions"]} == {"exists"}


async def test_a_second_run_writes_nothing(setup: Setup) -> None:
    assert await setup.migrate() == 0
    uploads, writes = len(setup.lekto.uploads), len(setup.lekto.writes())
    downloads = len(setup.paperless.downloads)
    assert await setup.run("run") == 0
    assert len(setup.lekto.uploads) == uploads and len(setup.paperless.downloads) == downloads
    assert len(setup.lekto.writes()) == writes


async def test_a_member_taken_out_of_a_migration_space_stays_out(setup: Setup) -> None:
    assert await setup.migrate() == 0
    space = next(s for s in setup.lekto.spaces.values() if "bob (lesen)" in s["name"])
    bob = named(setup.lekto.users, "bob")
    space["members"] = [m for m in space["members"] if m["user_id"] != bob["id"]]
    writes = len(setup.lekto.writes())
    assert await setup.run("prepare") == 0  # its uploader erika is in: nothing to do
    assert len(setup.lekto.writes()) == writes
    assert bob["id"] not in {m["user_id"] for m in space["members"]}


async def test_a_field_named_notes_is_aligned_as_any_other(setup: Setup) -> None:
    """Once the notes field of migrations before the plan, which the alignment left alone: a
    field the plan names `notes` kept its values after `drop` (MI-11)."""
    assert await setup.run("plan") == 0
    setup.edit("custom_fields", "Text", "{to: field, name: notes, create: true}")
    assert await setup.migrate() == 0
    notes = named(setup.lekto.fields, "notes")
    assert by_title(setup, "Document 10")["fields"][notes["id"]] == "Hello"
    setup.edit("custom_fields", "Text", "drop")
    assert await setup.run("run") == 0
    assert notes["id"] not in by_title(setup, "Document 10")["fields"]


async def test_check_shows_the_alignment_run_makes(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both stand on one `Basis`: the same base and the same wish for every document (MI-09)."""
    assert await setup.migrate() == 0
    setup.edit("custom_fields", "Count", "drop")
    seen: list[str] = []
    real = Basis.align

    def spying(self: Basis, base: dict[str, Any], details: dict[str, Any], resolved: Any) -> Any:
        seen.append(json.dumps([base, self.want(resolved)], sort_keys=True))
        return real(self, base, details, resolved)

    monkeypatch.setattr(Basis, "align", spying)
    assert await setup.run("check") == 0
    checked, seen[:] = sorted(seen), []
    assert await setup.run("run") == 0
    assert sorted(seen) == checked and checked


async def test_a_changed_plan_aligns_what_was_migrated(setup: Setup) -> None:
    assert await setup.migrate() == 0
    setup.edit("tags", "tax", "[{to: topic, name: Taxes, create: true}, {to: tag, name: tax}]")
    setup.edit("custom_fields", "Count", "drop")
    assert await setup.run("check") == 0
    report = setup.report("check")
    ten = row(report, 10)
    assert ten["status"] == "differs" and ten["prepare"] == ["topic 'Taxes'"]
    whats = {(d["what"], d["action"]) for d in ten["differences"]}
    assert ("field Count", "update") in whats
    assert await setup.run("run") == 2  # the topic does not exist yet
    assert await setup.run("prepare") == 0
    assert await setup.run("check") == 0
    whats = {(d["what"], d["action"]) for d in row(setup.report("check"), 10)["differences"]}
    assert ("topic_id", "update") in whats
    assert await setup.run("run") == 0
    topic = named(setup.lekto.tags, "Taxes")
    first = by_title(setup, "Document 10")
    assert first["topic_id"] == topic["id"]
    assert "Count" not in {setup.lekto.fields[k]["name"] for k in first["fields"]}
    aligned = [body for _, body in setup.lekto.aligned]
    assert any("topic_id" in body for body in aligned)
    assert await setup.run("check") == 0
    assert row(setup.report("check"), 10)["status"] == "same"


async def test_a_topic_without_a_contact_is_not_taken_over(setup: Setup) -> None:
    """Lekto keeps a topic only with a contact: it refused the alignment at every run (MI-04)."""
    assert await setup.run("plan") == 0
    setup.edit("correspondents", "ACME Energy", "drop")
    setup.edit("tags", "tax", "{to: topic, name: Taxes, create: true}")
    assert await setup.run("check") == 0, setup.report("check")["problems"]
    note = (
        "topic 'Taxes' is not taken over: a topic is one of the contact's, and the document "
        "has none"
    )
    assert note in row(setup.report("check"), 10)["notes"]
    assert await setup.migrate() == 0, setup.messages
    assert by_title(setup, "Document 10")["topic_id"] is None
    assert await setup.run("check") == 0
    assert row(setup.report("check"), 10)["status"] == "same"


async def test_a_value_changed_in_lekto_stays(setup: Setup) -> None:
    assert await setup.migrate() == 0
    first = by_title(setup, "Document 10")
    chosen = first["contact_id"] = str(uuid4())  # by a person
    setup.edit("correspondents", "ACME Energy", "{to: contact, name: Unused}")
    assert await setup.run("check") == 0
    differences = row(setup.report("check"), 10)["differences"]
    assert [(d["what"], d["action"]) for d in differences] == [("contact_id", "kept")]
    assert await setup.run("run") == 0
    assert first["contact_id"] == chosen
    assert "kept: contact_id" in (row(setup.report("run"), 10)["reason"] or "")


async def test_documents_migrated_before_get_the_date_they_came_in(setup: Setup) -> None:
    """A migration before the plan sent no `created_at`: Lekto took the moment of the upload,
    and the state file knows nothing of what was set."""
    assert await setup.migrate() == 0
    first = by_title(setup, "Document 10")
    upload = "2026-10-10T08:00:00+00:00"
    first["created_at"] = "2026-10-10T08:00:00.400000+00:00"
    receive = first["_log"][0]
    receive["started_at"] = upload
    del receive["output"]["imported"]["created_at"]
    state = sqlite3.connect(setup.directory / "state.sqlite")
    state.execute("UPDATE documents SET applied = NULL")
    state.commit()
    state.close()
    assert await setup.run("run") == 0
    assert datetime.fromisoformat(first["created_at"]) == datetime(2024, 4, 2, 7, 30, tzinfo=UTC)
    assert any("created_at" in body for _, body in setup.lekto.aligned)


async def test_a_review_holds_the_documents_of_an_object(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    setup.edit("correspondents", "ACME Energy", "{review: Resolve the contact in Lekto}")
    assert await setup.migrate() == 0
    first = by_title(setup, "Document 10")
    assert first["lane"] == "yellow" and first["contact_id"] is None
    upload = next(u for u in setup.lekto.uploads if u["filename"] == "scan-10.pdf")
    assert json.loads(upload["metadata"])["review"] == [
        {"reason": "Resolve the contact in Lekto", "field": "contact"}
    ]
    assert "Resolve the contact in Lekto" in (row(setup.report("run"), 10)["reason"] or "")


async def test_the_selection_takes_only_some_documents(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    _, document = plans.load(setup.plan_path)
    document["documents"] = plans.yaml().load("include: {tags: [tax/2024]}\nexclude: {id: [11]}")
    plans.dump(document, setup.plan_path)
    assert await setup.migrate() == 0
    assert [d["title"] for d in setup.lekto.documents.values()] == ["Document 10"]
    assert await setup.run("check") == 0
    assert setup.report("check")["document_results"] == {"same": 1, "not selected": 9}


async def test_a_document_deleted_in_lekto_is_reported_or_uploaded_again(setup: Setup) -> None:
    assert await setup.migrate() == 0
    gone = by_title(setup, "Document 12")
    del setup.lekto.documents[gone["id"]]
    assert await setup.run("check") == 0
    assert row(setup.report("check"), 12)["status"] == "deleted in Lekto"
    assert await setup.run("run") == 0
    assert setup.report("run")["totals"]["deleted"] == 1
    assert len(setup.lekto.documents) == 7
    assert await setup.run("run", reupload=True) == 0
    assert len(setup.lekto.documents) == 8


async def test_texts_lekto_read_worse_are_listed(setup: Setup) -> None:
    for document in setup.archive.documents:
        document["content"] = "word " * 100
    setup.lekto.texts["scan-12.pdf"] = "few words only"
    setup.lekto.advice["scan-13.pdf"] = "poor_page"
    assert await setup.migrate() == 0
    assert await setup.run("check") == 0
    texts = {t["id"]: t for t in setup.report("check")["texts"]}
    assert set(texts) == {12, 13}
    assert (texts[12]["words_paperless"], texts[12]["words_lekto"]) == (100, 3)
    assert texts[13]["advice"] == "poor_page"


async def test_the_download_checks_the_files(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    setup.archive.documents[0]["versions"] = [{"id": 10, "is_root": True, "checksum": "0" * 64}]
    setup.archive.files[11] = b"not a pdf"
    assert await setup.run("check", download=True) == 1
    files = {f["id"]: f for f in setup.report("check")["files"]}
    assert "checksum" in files[10]["problem"] and "would not take" in files[11]["problem"]
    assert len(setup.paperless.downloads) == 8


async def test_no_key_ends_up_in_a_file(setup: Setup) -> None:
    assert await setup.migrate() == 0
    assert await setup.run("check") == 0
    for path in setup.directory.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            assert PAPERLESS_KEY.encode() not in data and fake_lekto.TOKEN.encode() not in data, (
                path
            )


async def test_a_state_belongs_to_one_source_and_target(setup: Setup) -> None:
    assert await setup.migrate() == 0
    assert await setup.run("run", lekto_url="http://elsewhere") == 2


async def test_a_wrong_or_read_only_key_cannot_write(setup: Setup) -> None:
    assert await setup.run("plan", paperless_token="wrong") == 2
    assert await setup.run("plan") == 0
    assert await setup.run("prepare", lekto_token="wrong") == 2
    setup.lekto.scope = "read"
    assert await setup.run("prepare") == 2
    assert await setup.run("check") == 0  # reading is enough for a cold run
    setup.lekto.scope = "read_write"
    setup.lekto.role = "user"
    assert await setup.run("run") == 2


@pytest.mark.parametrize(
    ("api_version", "said"),
    [
        ("0.1", "update Lekto"),
        # Before 0.16 Lekto named none: its answer is no `Me` of pylekto's, `GET /version` is 404.
        (None, f"Lekto names no API version, this client speaks the API {API_VERSION}"),
    ],
)
async def test_an_older_lekto_stops_every_command(
    setup: Setup, capsys: pytest.CaptureFixture[str], api_version: str | None, said: str
) -> None:
    """A migration writes too much to guess what an older API lacks."""
    assert await setup.run("plan") == 0
    setup.lekto.api_version = api_version
    for command in ("plan", "check", "prepare", "run"):
        assert await setup.run(command) == 2
        assert said in capsys.readouterr().err
    assert setup.lekto.writes() == []


@pytest.mark.parametrize("api_version", ["0.99", "1.0"])
async def test_a_newer_lekto_is_warned_about_and_migrated(setup: Setup, api_version: str) -> None:
    """The client of an earlier release, or Lekto's own tests between a change of its API and the
    pylekto release that speaks it (released before Lekto's), run this client against it."""
    setup.lekto.api_version = api_version
    for command in ("plan", "prepare", "run", "check"):
        assert await setup.run(command) == 0
    warning = f"warning: Lekto speaks the API {api_version}, this client speaks the API"
    said = [m for m in setup.messages if m.startswith(warning)]
    assert len(said) == 4 and said[0].endswith(": use the client of that Lekto; going on")
    assert len(setup.lekto.documents) == 8


# --- interruption and failures ----------------------------------------------------------------


async def test_a_stopped_run_continues_where_it_stopped(setup: Setup) -> None:
    assert await setup.run("plan") == 0 and await setup.run("prepare") == 0
    stop = asyncio.Event()

    def after(count: int) -> None:
        if count == 3:
            stop.set()

    setup.lekto.after_upload = after
    assert await setup.run("run", stop=stop, concurrency=1) == 130
    stopped = len(setup.lekto.documents)
    assert 3 <= stopped < 8
    setup.lekto.after_upload = None
    assert await setup.run("run") == 0
    sent = [u["filename"] for u in setup.lekto.uploads]
    assert len(sent) == len(set(sent)) == 8  # nothing twice


async def test_an_upload_in_progress_is_waited_for_after_the_restart(setup: Setup) -> None:
    assert await setup.run("plan") == 0 and await setup.run("prepare") == 0
    setup.lekto.ticks = -1  # the pipeline never finishes
    assert await setup.run("run", pipeline_timeout=0.0) == 1
    rows = (
        sqlite3.connect(setup.directory / "state.sqlite")
        .execute("SELECT status, count(*) FROM documents GROUP BY status")
        .fetchall()
    )
    assert dict(rows) == {"uploaded": 8, "skipped": 2}
    setup.lekto.ticks = 1
    assert await setup.run("run") == 0
    assert len(setup.lekto.uploads) == 8  # waiting again, not uploading again
    assert setup.report("run")["document_results"] == {"done": 8, "skipped": 2}


async def test_a_server_error_is_repeated_and_a_refusal_is_reported(setup: Setup) -> None:
    setup.lekto.errors["scan-10.pdf"] = (503, 2)
    setup.lekto.errors["scan-11.pdf"] = (422, 99)
    assert await setup.migrate() == 1
    assert len(setup.lekto.documents) == 7
    failed = [d for d in setup.report("run")["documents"] if d["status"] == "failed"]
    assert [d["id"] for d in failed] == [11] and "422" in failed[0]["reason"]
    setup.lekto.errors.clear()
    sent = len(setup.lekto.uploads)
    assert await setup.run("run") == 0
    assert len(setup.lekto.uploads) == sent + 1 and len(setup.lekto.documents) == 8


async def test_paperless_errors_that_may_pass_are_repeated(setup: Setup) -> None:
    setup.paperless.unavailable = 2  # Paperless restarts while the plan reads it
    assert await setup.run("plan") == 0
    setup.paperless.errors[10] = (502, 2)
    setup.paperless.errors[11] = (503, 99)
    setup.paperless.errors[12] = (404, 99)
    assert await setup.migrate() == 1
    failed = {
        d["id"]: d["reason"] for d in setup.report("run")["documents"] if d["status"] == "failed"
    }
    assert failed == {
        11: "download of document 11: HTTP 503",
        12: "download of document 12: HTTP 404",
    }
    downloads = Counter(
        int(path.split("/")[3]) for method, path in setup.paperless.requests if "download" in path
    )
    assert (downloads[10], downloads[11], downloads[12]) == (3, 4, 1)  # a 404 is not repeated
    setup.paperless.errors.clear()
    assert await setup.run("run") == 0
    assert len(setup.lekto.documents) == 8


async def test_the_check_names_every_note_of_a_file_and_the_first_of_a_copy_by_id(
    setup: Setup,
) -> None:
    """A note does not hide another, and which copy comes first does not depend on which
    download ends first (MI-K06)."""
    assert await setup.migrate() == 0
    twelve = setup.archive.documents[2]
    setup.archive.documents += [
        {**twelve, "id": 30, "title": "Said to be a photo", "mime_type": "image/jpeg"},
        {**twelve, "id": 40, "title": "New", "versions": []},
        {**twelve, "id": 41, "title": "New again", "versions": []},
    ]
    setup.archive.files[30] = setup.archive.files[12]
    setup.archive.files[40] = setup.archive.files[41] = setup.archive.files[12] + b"\n%new"
    setup.paperless.errors[40] = (502, 1)  # its download ends after 41's
    assert await setup.run("check", download=True) == 0
    files = {f["id"]: f for f in setup.report("check")["files"]}
    assert "the file is application/pdf, Paperless says image/jpeg" in files[30]["note"]
    assert "Lekto has the file already" in files[30]["note"]
    assert 40 not in files
    assert files[41]["note"] == "the same file as document 40"


async def test_a_duplicate_is_mapped_not_counted_as_an_error(setup: Setup) -> None:
    assert await setup.migrate() == 0
    existing = by_title(setup, "Document 12")
    setup.archive.documents.append(
        {**setup.archive.documents[2], "id": 30, "title": "Same file again"}
    )
    setup.archive.files[30] = setup.archive.files[12]
    assert await setup.run("run") == 0
    found = row(setup.report("run"), 30)
    assert found["status"] == "duplicate" and found["lekto_id"] == existing["id"]
    assert len(setup.lekto.documents) == 8


async def test_the_same_file_is_a_duplicate_wherever_it_lies(setup: Setup) -> None:
    """Every file exists once per installation: a copy is a duplicate also for a user who
    cannot see the document that holds it."""
    assert await setup.migrate() == 0
    twelve = setup.archive.documents[2]  # erika's, in her personal space
    setup.archive.documents += [
        {**twelve, "id": 30, "title": "Erika's copy"},
        {**twelve, "id": 31, "title": "Bob's copy", "owner": 3},
    ]
    setup.archive.files[30] = setup.archive.files[31] = setup.archive.files[12]
    assert await setup.run("check", download=True) == 0
    files = {f["id"]: f for f in setup.report("check")["files"]}
    assert "Lekto has the file already" in files[30]["note"]
    assert "Lekto has the file already" in files[31]["note"]
    assert await setup.run("run") == 0
    results = {d["id"]: d["status"] for d in setup.report("run")["documents"]}
    assert (results[30], results[31]) == ("duplicate", "duplicate")


async def test_a_copy_of_another_users_document_leaves_it_as_it_is(setup: Setup) -> None:
    """johndoe may change erika's document 13 in Paperless and has a copy of his own: Lekto
    finds the file in the space he edits, and that document stays erika's, where it is."""
    assert await setup.migrate() == 0
    thirteen = next(d for d in setup.archive.documents if d["id"] == 13)
    original = row(setup.report("run"), 13)["lekto_id"]
    before = dict(setup.lekto.documents[original])
    setup.archive.documents.append(
        {**thirteen, "id": 30, "title": "John's copy", "owner": 1, "permissions": {}}
    )
    setup.archive.files[30] = setup.archive.files[13]
    assert await setup.run("run") == 0
    copy = row(setup.report("run"), 30)
    assert copy["status"] == "duplicate" and copy["lekto_id"] == original
    assert "Paperless document 13" in copy["reason"]
    after = setup.lekto.documents[original]
    assert (after["title"], after["space_id"]) == (before["title"], before["space_id"])
    writes = len(setup.lekto.writes())
    assert await setup.run("run") == 0  # the next run leaves it alone too
    assert len(setup.lekto.writes()) == writes
    assert await setup.run("check") == 0
    checked = row(setup.report("check"), 30)
    assert checked["status"] == "not aligned" and "Paperless document 13" in checked["reason"]


async def test_a_new_state_file_finds_what_is_there(setup: Setup) -> None:
    assert await setup.migrate() == 0
    count = len(setup.lekto.documents)
    other = setup.directory / "other.sqlite"
    assert await setup.run("prepare", state=other) == 0
    assert await setup.run("run", state=other) == 0
    assert len(setup.lekto.documents) == count
    assert setup.report("run")["document_results"] == {"duplicate": 8, "skipped": 2}


async def test_a_file_lekto_refuses_is_reported_as_not_taken_over(setup: Setup) -> None:
    setup.archive.files[10] = b"not a pdf"
    assert await setup.migrate() == 0
    found = row(setup.report("run"), 10)
    assert found["status"] == "skipped" and "unsupported" in found["reason"]


async def test_documents_that_are_not_green_are_reported_with_the_reason(setup: Setup) -> None:
    setup.lekto.lanes["scan-12.pdf"] = "red"
    assert await setup.migrate() == 0
    report = setup.report("run")
    assert report["lanes"] == {"green": 7, "red": 1}
    assert row(report, 12)["reason"] == "parse: no text recognised"
    assert "Documents in yellow or red" in (setup.directory / "reports" / "run.md").read_text()


async def test_only_the_first_selected_documents_with_a_limit(setup: Setup) -> None:
    assert await setup.migrate(limit=3) == 0
    assert sorted(d["title"] for d in setup.lekto.documents.values()) == [
        "Document 10",
        "Document 11",
        "Document 12",
    ]
    assert await setup.migrate() == 0
    assert len(setup.lekto.documents) == 8


async def test_a_group_of_the_same_name_is_no_tag(setup: Setup) -> None:
    """Lekto's names are unique per scope: a contact group named like a Paperless tag stays a
    group, and the tag becomes a document tag of its own."""
    id = str(uuid4())
    setup.lekto.tags[id] = {"id": id, "name": "tax", "scope": "contact"}
    assert await setup.migrate() == 0
    tags = [t for t in setup.lekto.tags.values() if t["name"] == "tax"]
    assert sorted(t.get("scope", "document") for t in tags) == ["contact", "document"]


async def test_reviews_go_with_their_codes(setup: Setup) -> None:
    assert await setup.run("plan") == 0
    setup.edit("tags", "tax", "{to: tag, name: tax, create: true, review: true}")
    assert await setup.migrate() == 0, setup.messages
    reviews = [
        review
        for upload in setup.lekto.uploads
        for review in json.loads(upload.get("metadata", "{}")).get("review", [])
    ]
    assert {(review["code"], review["params"]["name"]) for review in reviews} == {
        ("paperless_tag_review", "tax")
    }
