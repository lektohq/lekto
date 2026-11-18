"""Applying a rule to existing documents: the preview and the background job."""

import threading
from types import SimpleNamespace

import pytest

from lekto.core.domain import evidence, rule_conditions
from lekto.core.domain.documents import DocumentChanges
from lekto.core.domain.errors import NotFoundError, ValidationError
from lekto.core.domain.ids import DocumentId, new_id
from lekto.core.domain.pipeline import RULES_APPLY, Lane
from lekto.core.domain.progress import ProgressStatus
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.rules import (
    Condition,
    ConditionField,
    ForceReview,
    Operator,
    Rule,
    SetSpace,
    SetTitle,
)
from lekto.core.domain.spaces import SpaceRole
from lekto.core.domain.users import User
from lekto.core.services.rules import retroactive, running
from lekto.core.services.rules.retroactive import BATCH
from lekto.core.services.rules.running import Prepared, prepare
from tests import builders
from tests.unit.services.rules_support import (
    MAX_DOCUMENTS,
    Classifies,
    RuleWorld,
    add_tags,
    all_of,
    channel_api,
    contact_is,
    definition,
    incoming_pdf,
    rule_world,
    text_matches,
)
from tests.unit.services.support import World

NOT_AVAILABLE = because(ReasonCode.SKIP_NOT_AVAILABLE)


async def run_jobs(r: RuleWorld) -> int:
    return await builders.drain(r.applications)


async def test_the_preview_lists_changes_and_the_job_applies_the_pinned_version(
    world: World,
) -> None:
    r = await rule_world(world)
    owner, other = await world.user(), await world.user()
    tax = await r.tag("tax")
    first = await r.arrive(owner, filename="First.pdf")
    second = await r.arrive(owner, filename="Second.pdf")
    third = await r.arrive(owner, filename="Third.pdf")
    for document, title in ((first, "Mine 1"), (second, "Mine 2")):
        await r.documents.change_metadata(owner.id, document.id, DocumentChanges(title=title))
    await r.arrive(other)
    await r.pipeline().receive(owner.id, incoming_pdf(), filename="Busy.pdf")  # processing
    rule = await r.personal_rule(
        owner,
        definition(
            "Tax",
            channel_api(),
            add_tags(tax.id),
            SetTitle("Tax {{ filename }}"),
            ForceReview("check"),
        ),
    )

    preview = await r.applications.preview(owner.id, rule.id)

    assert preview.next_cursor is None
    assert preview.looked_at == 3
    assert (await r.applications.preview(owner.id, rule.id, limit=1)).looked_at == 1
    items = {item.document.id: item for item in preview.items}
    assert set(items) == {first.id, second.id, third.id}
    assert [effect.field for effect in items[first.id].effects] == ["tags"]
    assert [conflict.field for conflict in items[first.id].conflicts] == ["title"]
    assert [(note.field, note.kind) for note in items[first.id].notes] == [("review", "skipped")]
    assert [effect.field for effect in items[third.id].effects] == ["tags", "title"]
    assert items[third.id].conflicts == ()

    application = await r.applications.start(
        owner.id,
        rule.id,
        version=1,
        documents=[first.id, second.id, third.id],
        accept_conflicts=[first.id],
    )
    # A new version meanwhile does not change what the application does.
    await r.rules.change(
        owner.id, rule.id, definition("Tax v2", channel_api(), SetTitle("V2 {{ filename }}"))
    )
    assert await run_jobs(r) == 1

    done = await r.applications.get(owner.id, application.id)
    assert (done.status, done.applied, done.unchanged, done.skipped) == (
        ProgressStatus.DONE,
        3,
        0,
        [],
    )
    titles = [(await r.stored(document)).title for document in (first, second, third)]
    assert titles == ["Tax First", "Mine 2", "Tax Third"]  # the conflict only where accepted
    for document in (first, second, third):
        stored = await r.stored(document)
        assert (stored.tag_ids, stored.lane) == ({tax.id}, Lane.GREEN)  # no forced review
    (entry,) = await r.rule_entries(first, RULES_APPLY)
    assert entry.result.input == {
        "trigger": "apply",
        "actor": str(owner.id),
        "application_id": str(application.id),
        "rules": [{"id": str(rule.id), "version": 1}],
    }


async def test_the_dry_run_looks_only_at_documents_the_conditions_leave(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = await rule_world(world)
    owner = await world.user()
    acme, bank = await r.contact("ACME"), await r.contact("Bank")
    depot = await r.tag("depot")
    arrived = {}
    for name, contact, text in (
        ("a1", acme, "Securities account statement"),
        ("a2", acme, "Current account statement"),
        ("b1", bank, "Securities account statement"),
        ("n1", None, "Securities account statement"),
    ):
        document = await r.arrive(owner, text=text, filename=f"{name}.pdf")
        contact_id = None if contact is None else contact.id
        await r.documents.change_metadata(
            owner.id, document.id, DocumentChanges(contact_id=contact_id)
        )
        arrived[name] = document.id
    securities = Condition(field=ConditionField.TEXT, op=Operator.CONTAINS, value="Securities")
    rule = await r.personal_rule(
        owner, definition("Depot", all_of(contact_is(acme.id), securities), add_tags(depot.id))
    )

    preview = await r.applications.preview(owner.id, rule.id)
    assert (preview.total, preview.looked_at) == (2, 2)
    assert [item.document.id for item in preview.items] == [arrived["a1"]]

    # Without the filter the dry run looks at every document and finds the same.
    monkeypatch.setattr(retroactive, "prefilter", lambda group, tree, base: base)
    unfiltered = await r.applications.preview(owner.id, rule.id)
    assert (unfiltered.total, unfiltered.looked_at) == (4, 4)
    assert [item.document.id for item in unfiltered.items] == [arrived["a1"]]


async def test_a_dry_run_counts_only_the_documents_the_caller_may_edit(world: World) -> None:
    """A global rule, applied by someone who only reads a shared space: its documents are
    neither listed nor counted (SC-10)."""
    r = await rule_world(world)
    owner, reader = await world.user(), await world.user()
    tax = await r.tag("tax")
    shared = await world.spaces.create(owner.id, "Haushalt")
    await world.spaces.set_member(owner.id, shared.id, reader.id, SpaceRole.READ)
    for _ in range(3):
        await r.arrive(owner, space=shared.id)
    mine = await r.arrive(reader)
    rule = await r.global_rule(definition("Tax", channel_api(), add_tags(tax.id)))

    preview = await r.applications.preview(reader.id, rule.id)

    assert [item.document.id for item in preview.items] == [mine.id]
    assert (preview.looked_at, preview.total) == (1, 1)


async def test_a_dry_run_whose_conditions_no_document_meets_looks_at_none(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    acme, bank = await r.contact("ACME"), await r.contact("Bank")
    seen = await r.tag("seen")
    await r.arrive(owner)
    rule = await r.personal_rule(
        owner,
        definition("Both", all_of(contact_is(acme.id), contact_is(bank.id)), add_tags(seen.id)),
    )
    preview = await r.applications.preview(owner.id, rule.id)
    assert (preview.items, preview.next_cursor, preview.looked_at, preview.total) == (
        (),
        None,
        0,
        0,
    )


async def test_the_job_checks_the_rights_again_and_a_global_rule_moves_nothing(
    world: World,
) -> None:
    r = await rule_world(world)
    owner, editor = await world.user(), await world.user()
    seen = await r.tag("seen")
    shared = await world.spaces.create(owner.id, "Shared")
    readable = await world.spaces.create(owner.id, "Readable")
    await world.spaces.set_member(owner.id, shared.id, editor.id, SpaceRole.EDIT)
    await world.spaces.set_member(owner.id, readable.id, editor.id, SpaceRole.READ)
    in_shared = await r.arrive(owner, space=shared.id)
    await r.arrive(owner, space=readable.id)
    private = await r.arrive(owner)
    own = await r.arrive(editor)
    rule = await r.global_rule(
        definition("Audit", channel_api(), add_tags(seen.id), ForceReview("audit"))
    )

    # A global rule: by anyone, on the documents they may write to.
    preview = await r.applications.preview(editor.id, rule.id)
    assert {item.document.id for item in preview.items} == {in_shared.id, own.id}

    application = await r.applications.start(
        editor.id, rule.id, version=1, documents=[in_shared.id, own.id, private.id]
    )
    await world.spaces.set_member(owner.id, shared.id, editor.id, SpaceRole.READ)
    await run_jobs(r)

    done = await r.applications.get(editor.id, application.id)
    assert (done.status, done.applied) == (ProgressStatus.DONE, 1)
    assert done.skipped == [(in_shared.id, NOT_AVAILABLE), (private.id, NOT_AVAILABLE)]
    assert (await r.stored(in_shared)).tag_ids == set()
    assert (await r.stored(private)).tag_ids == set()
    changed = await r.stored(own)
    assert (changed.tag_ids, changed.lane, changed.space_id) == (
        {seen.id},
        Lane.GREEN,
        own.space_id,
    )


async def test_a_user_rule_is_applied_by_its_owner_to_their_own_documents(world: World) -> None:
    r = await rule_world(world)
    owner, colleague = await world.user(), await world.user()
    tax = await r.tag("tax")
    office = await world.spaces.create(colleague.id, "Office")
    await world.spaces.set_member(colleague.id, office.id, owner.id, SpaceRole.EDIT)
    theirs = await r.arrive(colleague, space=office.id)
    mine = await r.arrive(owner)
    rule = await r.personal_rule(owner, definition("Tax", channel_api(), add_tags(tax.id)))

    preview = await r.applications.preview(owner.id, rule.id)
    assert [item.document.id for item in preview.items] == [mine.id]
    application = await r.applications.start(
        owner.id, rule.id, version=1, documents=[theirs.id, mine.id]
    )
    await run_jobs(r)

    done = await r.applications.get(owner.id, application.id)
    assert (done.applied, done.skipped) == (1, [(theirs.id, NOT_AVAILABLE)])
    assert (await r.stored(theirs)).tag_ids == set()

    # Nobody else applies it or reads the application, but admins do (Tobi, 08.10.2026):
    # on the documents of the rule's owner only.
    with pytest.raises(NotFoundError):
        await r.applications.preview(colleague.id, rule.id)
    with pytest.raises(NotFoundError):
        await r.applications.get(colleague.id, application.id)
    assert (await r.applications.get(r.admin.id, application.id)).id == application.id
    assert [
        item.document.id for item in (await r.applications.preview(r.admin.id, rule.id)).items
    ] == []
    by_admin = await r.applications.start(
        r.admin.id, rule.id, version=1, documents=[theirs.id, mine.id]
    )
    await run_jobs(r)
    done = await r.applications.get(r.admin.id, by_admin.id)
    assert (done.applied, done.unchanged, done.skipped) == (0, 1, [(theirs.id, NOT_AVAILABLE)])

    with pytest.raises(NotFoundError):
        await r.applications.start(owner.id, rule.id, version=2, documents=[mine.id])
    too_many = [DocumentId(new_id()) for _ in range(MAX_DOCUMENTS + 1)]
    with pytest.raises(ValidationError):
        await r.applications.start(owner.id, rule.id, version=1, documents=too_many)


async def test_a_long_application_continues_in_a_new_job(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    tax = await r.tag("tax")
    documents = [await r.arrive(owner) for _ in range(BATCH + 1)]
    rule = await r.personal_rule(owner, definition("Tax", channel_api(), add_tags(tax.id)))
    application = await r.applications.start(
        owner.id, rule.id, version=1, documents=[document.id for document in documents]
    )

    assert await r.applications.run_next_job()
    progress = await r.applications.get(owner.id, application.id)
    assert (progress.status, progress.position, progress.finished_at) == (
        ProgressStatus.RUNNING,
        BATCH,
        None,
    )

    assert await run_jobs(r) == 1
    done = await r.applications.get(owner.id, application.id)
    assert (done.status, done.applied) == (ProgressStatus.DONE, BATCH + 1)
    for document in documents:
        assert (await r.stored(document)).tag_ids == {tax.id}


async def test_an_application_ends_when_its_rule_is_deleted(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    tax = await r.tag("tax")
    document = await r.arrive(owner)
    rule = await r.personal_rule(owner, definition("Tax", channel_api(), add_tags(tax.id)))
    application = await r.applications.start(owner.id, rule.id, version=1, documents=[document.id])
    await r.rules.delete(owner.id, rule.id)

    await run_jobs(r)

    done = await r.applications.get(owner.id, application.id)
    assert (done.status, done.error) == (ProgressStatus.FAILED, "the rule or its user is gone")
    assert (await r.stored(document)).tag_ids == set()
    with pytest.raises(NotFoundError):
        await r.applications.preview(owner.id, rule.id)


async def test_filing_on_an_unconfirmed_contact_is_a_conflict_until_accepted(
    world: World,
) -> None:
    r = await rule_world(world)
    owner, reader = await world.user(), await world.user()
    acme = await r.contact("ACME")
    shared = await world.spaces.create(owner.id, "Shared")
    await world.spaces.set_member(owner.id, shared.id, reader.id, SpaceRole.READ)
    # The model set the contact; no person confirmed it.
    document = await r.arrive(owner, classify=Classifies(contact=acme.id))
    rule = await r.personal_rule(
        owner, definition("ACME", contact_is(acme.id), SetSpace(shared.id))
    )

    (item,) = (await r.applications.preview(owner.id, rule.id)).items
    assert item.effects == ()
    assert [(note.field, note.kind) for note in item.conflicts] == [("space", "conflict")]

    await r.applications.start(owner.id, rule.id, version=1, documents=[document.id])
    await run_jobs(r)
    assert (await r.stored(document)).space_id == document.space_id

    await r.applications.start(
        owner.id, rule.id, version=1, documents=[document.id], accept_conflicts=[document.id]
    )
    await run_jobs(r)
    assert (await r.stored(document)).space_id == shared.id


async def test_a_worker_overtaken_applies_what_it_prepared_to_no_other_document(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another worker took the application over (the lease ran out) and went on while the
    first prepared a document: the first applies nothing to the next one (SC-04)."""
    r = await rule_world(world)
    owner = await world.user()
    tax = await r.tag("tax")
    invoice = await r.arrive(owner, text="# Rechnung")
    others = [await r.arrive(owner, text="# Strom") for _ in range(2)]
    rule = await r.personal_rule(owner, definition("Tax", text_matches("Rech"), add_tags(tax.id)))
    application = await r.applications.start(
        owner.id, rule.id, version=1, documents=[invoice.id, *(item.id for item in others)]
    )
    real, calls = prepare, 0

    async def overtaken(*args: object, **kwargs: object) -> Prepared:
        nonlocal calls
        calls += 1
        prepared = await real(*args, **kwargs)  # type: ignore[arg-type]
        if calls == 1:
            await r.applications._next_document(application.id)  # the other worker
        return prepared

    monkeypatch.setattr(retroactive, "prepare", overtaken)
    await r.applications._next_document(application.id)
    await run_jobs(r)

    assert (await r.stored(invoice)).tag_ids == {tax.id}
    for item in others:
        assert (await r.stored(item)).tag_ids == set()
    done = await r.applications.get(owner.id, application.id)
    assert (done.status, done.applied) == (ProgressStatus.DONE, 1)


async def test_the_text_is_read_for_the_rules_outside_the_event_loop(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cutting and folding a long text take a while: done once per document in a worker
    thread, not again for each condition in the event loop (SC-05)."""
    folds: list[int] = []
    cuts: list[int] = []
    fold, cut = evidence.fold_umlauts, rule_conditions.pattern_text

    def folding(text: str) -> str:
        if len(text) > 100:  # the document's text, not a condition's value
            folds.append(threading.get_ident())
        return fold(text)

    def cutting(markdown: str, limit: int) -> str:
        cuts.append(threading.get_ident())
        return cut(markdown, limit)

    monkeypatch.setattr(evidence, "fold_umlauts", folding)
    monkeypatch.setattr(running, "pattern_text", cutting)
    r = await rule_world(world)
    owner = await world.user()
    tax = await r.tag("tax")
    await r.arrive(owner, text="# Gebuehr\n" + "Zeile mit Inhalt\n" * 20)
    contains = [
        Condition(field=ConditionField.TEXT, op=Operator.CONTAINS, value=value)
        for value in ("Gebühr", "Prüfung", "Übersicht")
    ]
    rule = await r.personal_rule(owner, definition("Fee", all_of(*contains), add_tags(tax.id)))
    folds.clear()
    cuts.clear()

    preview = await r.applications.preview(owner.id, rule.id)

    assert preview.looked_at == 1
    assert len(folds) == 1 and len(cuts) == 1
    assert threading.get_ident() not in folds + cuts


def slow_patterns(r: RuleWorld, monkeypatch: pytest.MonkeyPatch, page: float) -> None:
    """Each pattern takes 0.06 s of a clock of its own; a page of the dry run has `page`."""
    now = [0.0]
    search = r.matcher.search

    async def slow(pattern: str, text: str, *, case_sensitive: bool) -> bool:
        now[0] += 0.06
        return await search(pattern, text, case_sensitive=case_sensitive)

    r.matcher.search = slow  # type: ignore[method-assign]
    monkeypatch.setattr(running, "time", SimpleNamespace(monotonic=lambda: now[0]))
    monkeypatch.setattr(retroactive, "PREVIEW_BUDGET", page)


async def pages(r: RuleWorld, owner: User, rule: Rule) -> list[list[DocumentId]]:
    """The dry run page by page: the documents each shows."""
    shown: list[list[DocumentId]] = []
    before = None
    while True:
        preview = await r.applications.preview(owner.id, rule.id, before=before)
        shown.append([item.document.id for item in preview.items])
        if preview.next_cursor is None:
            return shown
        before = preview.next_cursor


async def test_the_first_document_of_a_page_has_the_time_of_one(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shorter than two patterns, the page's time judged each document on half of them: none
    was shown (SC-12)."""
    r = await rule_world(world)
    owner = await world.user()
    tax = await r.tag("tax")
    documents = [await r.arrive(owner, text="# Strom Rechnung") for _ in range(3)]
    rule = await r.personal_rule(
        owner,
        definition("Tax", all_of(text_matches("Strom"), text_matches("Rech")), add_tags(tax.id)),
    )
    slow_patterns(r, monkeypatch, page=0.05)
    assert await pages(r, owner, rule) == [[item.id] for item in reversed(documents)]


async def test_a_document_the_page_s_time_cuts_short_comes_first_on_the_next(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not judged on half its patterns, and not left behind (SC-12)."""
    r = await rule_world(world)
    owner = await world.user()
    tax = await r.tag("tax")
    invoice = await r.arrive(owner, text="# Strom Rechnung")
    await r.arrive(owner)  # no text: no patterns, no time
    rule = await r.personal_rule(
        owner,
        definition("Tax", all_of(text_matches("Strom"), text_matches("Rech")), add_tags(tax.id)),
    )
    slow_patterns(r, monkeypatch, page=0.05)
    assert await pages(r, owner, rule) == [[], [invoice.id]]


async def test_an_unexpected_error_ends_the_application(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    tax = await r.tag("tax")
    document = await r.arrive(owner, text="# Rechnung")
    rule = await r.personal_rule(owner, definition("Tax", text_matches("Rech"), add_tags(tax.id)))

    async def broken(pattern: str, text: str, *, case_sensitive: bool) -> bool:
        raise RuntimeError("broken")

    r.matcher.search = broken  # type: ignore[method-assign]
    application = await r.applications.start(owner.id, rule.id, version=1, documents=[document.id])

    assert await r.applications.run_next_job()
    assert not await r.applications.run_next_job()
    done = await r.applications.get(owner.id, application.id)
    assert (done.status, done.error) == (ProgressStatus.FAILED, "stopped by an internal error")
    assert (await r.stored(document)).tag_ids == set()


async def test_applying_a_rule_moves_nothing_where_the_person_could_not_move_it(
    world: World,
) -> None:
    """An admin's global rule or a co-editor's rule files, applied by an editor, only into a
    space the editor may file into, accepted or not."""
    r = await rule_world(world)
    editor, colleague, outsider = await world.user(), await world.user(), await world.user()
    home = await world.personal_space(editor)
    await world.spaces.set_member(editor.id, home.id, colleague.id, SpaceRole.EDIT)
    closed = await world.spaces.create(colleague.id, "Closed")
    elsewhere = await world.spaces.create(r.admin.id, "Elsewhere")
    await world.spaces.set_member(r.admin.id, elsewhere.id, outsider.id, SpaceRole.READ)
    document = await r.arrive(editor)
    rules = [
        await r.global_rule(definition("Global", channel_api(), SetSpace(elsewhere.id))),
        await r.space_rule(
            colleague, home.id, definition("Colleague", channel_api(), SetSpace(closed.id))
        ),
    ]
    for rule in rules:
        assert (await r.applications.preview(editor.id, rule.id)).items == ()
        await r.applications.start(
            editor.id, rule.id, version=1, documents=[document.id], accept_conflicts=[document.id]
        )
        await run_jobs(r)
        assert (await r.stored(document)).space_id == home.id
    # The colleague, who edits both, applies their own rule.
    (item,) = (await r.applications.preview(colleague.id, rules[1].id)).items
    assert [effect.field for effect in item.effects] == ["space"]
    await r.applications.start(colleague.id, rules[1].id, version=1, documents=[document.id])
    await run_jobs(r)
    assert (await r.stored(document)).space_id == closed.id
