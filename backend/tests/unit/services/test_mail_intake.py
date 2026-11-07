"""Fetching mail: a job per mailbox, what each mail brings in by the mailbox's fallback, what is
not fetched twice, and what shows at the mailbox."""

from dataclasses import replace
from datetime import timedelta
from email.message import EmailMessage
from typing import Any

import pytest

from lekto.adapters.outbound.memory.mail_server import MemoryMailSession
from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.core.domain.condition_tree import Group
from lekto.core.domain.documents import Channel
from lekto.core.domain.errors import PermissionDeniedError, ValidationError
from lekto.core.domain.events import MailboxFetched
from lekto.core.domain.identifiers import Identifier, IdentifierKind
from lekto.core.domain.ids import DocumentTypeId, new_id
from lekto.core.domain.jobs import JobState
from lekto.core.domain.mail import (
    Fallback,
    FetchStart,
    MailAction,
    Mailbox,
    MailboxChanges,
    MailLogin,
    MailSecurity,
    MailStep,
)
from lekto.core.domain.mail_intake import MailOutcome, MailParts, OriginRole, mail_limit
from lekto.core.domain.mail_rules import (
    MailCondition,
    MailField,
    MailOperator,
    MailRule,
    MailRuleChanges,
)
from lekto.core.domain.mail_traits import FlagColor, Importance, MailMarks
from lekto.core.domain.master_data import DocumentType
from lekto.core.domain.pipeline import Node
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.rules import Condition, ConditionField, Operator, RuleScope
from lekto.core.domain.spaces import SpaceRole
from lekto.core.domain.users import Role, User
from lekto.core.services._push_queue import PUSH_JOB
from lekto.core.services.classification.signals import FactsResult, FactsSignal, sender_line
from lekto.core.services.mail_intake import (
    FETCH_JOB,
    LEASE,
    MAX_PER_RUN,
    MailIntakeService,
    fetch_key,
)
from lekto.core.services.mail_rules import Decider
from lekto.core.services.objects import text_key
from lekto.core.services.pipeline import PipelineService
from lekto.core.services.relating import relate
from lekto.core.services.rules.management import RuleService
from lekto.core.services.rules.nodes import ApplyRulesNode
from tests import mails
from tests.builders import TEMPLATES, drain, incoming
from tests.mails import LOGIN
from tests.unit.services.rules_support import add_tags, all_of, definition
from tests.unit.services.support import World

LATER = timedelta(minutes=1)


async def _setup(
    world: World, *, everything: bool = True, **changes: object
) -> tuple[User, User, Mailbox]:
    admin, person = await world.user(role=Role.ADMIN), await world.user()
    world.mail_server.add_account(LOGIN)
    settings = MailboxChanges(
        fallback=Fallback.EVERYTHING if everything else Fallback.NOTHING,
        fallback_user_id=person.id if everything else None,
        **changes,  # type: ignore[arg-type]
    )
    mailbox = await world.mailboxes.create(
        admin.id,
        name="Household",
        host=LOGIN.host,
        port=LOGIN.port,
        security=LOGIN.security,
        username=LOGIN.username,
        password=LOGIN.password,
        changes=settings,
    )
    return admin, person, mailbox


def _deliver(
    world: World,
    data: bytes,
    *,
    folder: str = "INBOX",
    seen: bool = False,
    flags: frozenset[str] = frozenset(),
) -> int:
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    return account.deliver(
        folder, data, arrived_at=world.clock.now() + LATER, seen=seen, flags=flags
    )


async def _fetch(world: World, service: MailIntakeService) -> None:
    world.clock.advance(2 * LATER)
    await drain(service)


async def test_everything_for_a_person_makes_documents_of_a_mail(world: World) -> None:
    _, person, mailbox = await _setup(world)
    service = world.mail_intake()
    _deliver(world, mails.rich_mail())
    await _fetch(world, service)

    documents = await world.documents.list_visible(person.id)
    assert len(documents) == 3  # the PDF, the mail's own text, the attached mail
    assert {document.channel for document in documents} == {Channel.MAIL}
    assert sorted(document.media_type for document in documents) == [
        "application/pdf",
        "message/rfc822",
        "message/rfc822",
    ]
    async with world.uow() as uow:
        (record,) = await uow.mail_records.recent(mailbox.id, limit=5)
        origins = await uow.mail_origins.of_record(record.id)
        stored = await uow.mailboxes.get(mailbox.id)
        queued = await uow.jobs.find(
            now=world.clock.now(), states=[JobState.PLANNED], kind=FETCH_JOB, limit=5
        )
    assert (record.outcome, record.documents, record.subject) == (
        MailOutcome.TAKEN,
        3,
        "Ihre Rechnung über 123,45 €",
    )
    assert [(origin.letter, origin.role) for origin in origins] == [
        (0, OriginRole.COVER),
        (0, OriginRole.ATTACHMENT),
        (1, OriginRole.COVER),
    ]
    assert origins[1].filename == "Rechnung 4711.pdf"
    assert origins[0].outer and origins[2].forwarded_by[0].address == "rechnung@stadtwerke.example"
    assert (stored.status.mails, stored.status.documents, stored.status.error) == (1, 3, None)
    assert stored.status.last_success_at is not None
    assert [job.dedup_key for job in queued] == [fetch_key(mailbox.id)]
    assert queued[0].run_at > world.clock.now()

    await _fetch(world, service)  # nothing new
    assert len(await world.documents.list_visible(person.id)) == 3


async def test_what_apple_mail_sends_inline_becomes_a_document(world: World) -> None:
    """Apple Mail sends a PDF `inline` with a file name (Tobi, 06.11.2026): it is taken as an
    attachment beside the mail's text; the logo the HTML embeds is not."""
    _, person, _ = await _setup(world)
    _deliver(world, mails.apple_mail())
    await _fetch(world, world.mail_intake())
    documents = await world.documents.list_visible(person.id)
    assert sorted(document.original_filename for document in documents) == [
        "Ein Test mit Anhang.eml",
        "Foto.png",
        "Rechnung.pdf",
    ]


async def test_nothing_without_a_rule(world: World) -> None:
    _, person, mailbox = await _setup(world, everything=False)
    _deliver(world, mails.plain_mail())
    await _fetch(world, world.mail_intake())
    assert await world.documents.list_visible(person.id) == []
    async with world.uow() as uow:
        (record,) = await uow.mail_records.recent(mailbox.id, limit=5)
    assert record.outcome is MailOutcome.NO_RULE


async def test_a_forward_is_unwrapped_and_a_known_attachment_related(world: World) -> None:
    _, person, mailbox = await _setup(world)
    pipeline = world.pipeline()
    existing = await pipeline.receive(person.id, incoming(mails.PDF), filename="schon.pdf")
    inner = EmailMessage()
    inner["From"] = "Stadtwerke <rechnung@stadtwerke.example>"
    inner["Subject"] = "Rechnung"
    inner["Date"] = "Wed, 04 Nov 2026 08:00:00 +0000"
    inner.set_content("Anbei.")
    inner.add_attachment(mails.PDF, maintype="application", subtype="pdf", filename="r.pdf")
    outer = EmailMessage()
    outer["From"] = "Ben <ben@example.test>"
    outer["Subject"] = "Fwd: Rechnung"
    outer["Date"] = "Wed, 04 Nov 2026 09:00:00 +0000"
    outer.set_content("")
    outer.add_attachment(inner)
    _deliver(world, bytes(outer))
    await _fetch(world, world.mail_intake(pipeline))
    async with world.uow() as uow:
        (record,) = await uow.mail_records.recent(mailbox.id, limit=5)
        (origin,) = await uow.mail_origins.of_record(record.id)
    assert origin.role is OriginRole.COVER and origin.subject == "Rechnung"
    assert [item.address for item in origin.forwarded_by] == ["ben@example.test"]
    assert origin.related == (existing.id,)
    assert record.documents == 1


async def test_a_mail_is_fetched_once_across_mailboxes(world: World) -> None:
    admin, _, first = await _setup(world)
    other = MailLogin(
        host="imap.other.test", port=993, security=MailSecurity.TLS, username="x", password="y"
    )
    world.mail_server.add_account(other).deliver(
        "INBOX", mails.plain_mail(), arrived_at=world.clock.now() + LATER
    )
    _deliver(world, mails.plain_mail())
    second = await world.mailboxes.create(
        admin.id,
        name="Other",
        host=other.host,
        port=other.port,
        security=other.security,
        username=other.username,
        password=other.password,
    )
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        (of_first,) = await uow.mail_records.recent(first.id, limit=5)
        (of_second,) = await uow.mail_records.recent(second.id, limit=5)
    # The first mailbox's job was queued first and runs first: it takes the mail, the other
    # mailbox knows its Message-ID then.
    assert (of_first.outcome, of_second.outcome) == (MailOutcome.TAKEN, MailOutcome.KNOWN)


async def test_the_start_of_a_mailbox(world: World) -> None:
    _, person, _ = await _setup(world, start=FetchStart.UNREAD)
    _deliver(world, mails.plain_mail("Gelesen"), seen=True)
    _deliver(world, mails.plain_mail("Neu"))
    await _fetch(world, world.mail_intake())
    documents = await world.documents.list_visible(person.id)
    assert [document.original_filename for document in documents] == ["Neu.eml"]


async def test_a_mail_before_the_setup_is_left(world: World) -> None:
    _, person, _ = await _setup(world)
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    account.deliver("INBOX", mails.plain_mail(), arrived_at=world.clock.now() - timedelta(hours=1))
    await _fetch(world, world.mail_intake())
    assert await world.documents.list_visible(person.id) == []


async def test_mails_before_the_setup_leave_the_room_to_the_new_ones(world: World) -> None:
    """More mails of the day before the setup than a run takes: they are not recorded, so they
    come back every run; they must not fill the run, nor make it repeat at once."""
    _, person, mailbox = await _setup(world)
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    earlier = world.clock.now() - timedelta(hours=1)
    for number in range(MAX_PER_RUN + 10):
        account.deliver("INBOX", mails.plain_mail(f"Alt {number}"), arrived_at=earlier)
    _deliver(world, mails.plain_mail("Neu"))
    service = world.mail_intake()
    world.clock.advance(2 * LATER)
    assert await service.run_next_job()
    names = [
        document.original_filename for document in await world.documents.list_visible(person.id)
    ]
    assert names == ["Neu.eml"]
    async with world.uow() as uow:
        (job,) = await uow.jobs.find(
            now=world.clock.now(), states=[JobState.PLANNED], kind=FETCH_JOB, limit=5
        )
    assert job.run_at == world.clock.now() + mailbox.interval  # not at once


async def test_a_mail_too_large_is_left_out_and_shows_at_the_mailbox(world: World) -> None:
    _, person, mailbox = await _setup(world)
    _deliver(world, mails.plain_mail("Fotos", "x" * (1024 * 1024 + 10)))
    _deliver(world, mails.plain_mail("Klein"))
    await _fetch(world, world.mail_intake(max_attachment=1))  # limit: 1 MB and a byte
    async with world.uow() as uow:
        records = {
            record.subject: record for record in await uow.mail_records.recent(mailbox.id, limit=5)
        }
        stored = await uow.mailboxes.get(mailbox.id)
    large = records["Fotos"]
    assert large.outcome is MailOutcome.TOO_LARGE
    assert large.reason is not None and large.reason.code is ReasonCode.MAIL_TOO_LARGE
    assert large.reason.params == {"subject": "Fotos", "size": 2, "max": 2}
    # Named by its header lines alone, fetched without the rest.
    assert large.sender == "Stadtwerke Musterstadt <rechnung@stadtwerke.example>"
    assert large.message_id is not None and large.sent_at is not None
    assert stored.status.skipped == large.reason and stored.status.skipped_at is not None
    assert stored.status.error is None  # the fetch itself went well
    names = [
        document.original_filename for document in await world.documents.list_visible(person.id)
    ]
    assert names == ["Klein.eml"]


def test_a_mail_may_carry_an_attachment_as_large_as_an_upload() -> None:
    upload = 100 * 1024 * 1024
    assert mail_limit(upload) == upload * 4 // 3 + 1024 * 1024


async def test_a_refused_login_shows_at_the_mailbox(world: World) -> None:
    admin, _, mailbox = await _setup(world)
    await world.mailboxes.change(admin.id, mailbox.id, MailboxChanges(), password="wrong")
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        stored = await uow.mailboxes.get(mailbox.id)
    assert stored.status.error is not None
    assert stored.status.error.code is ReasonCode.MAIL_LOGIN_FAILED
    assert stored.status.last_success_at is None and stored.status.last_attempt_at is not None
    # The admins hear of it once: a fetch that fails again tells nobody.
    notices = [j for j in world.database.jobs.values() if j.kind == PUSH_JOB]
    assert [(j.payload["user_id"], j.payload["kind"]) for j in notices] == [
        (str(admin.id), "mailbox_failed")
    ]
    world.clock.advance(timedelta(hours=1))
    await _fetch(world, world.mail_intake())
    assert len([j for j in world.database.jobs.values() if j.kind == PUSH_JOB]) == 1


async def test_a_paused_mailbox_is_not_fetched(world: World) -> None:
    admin, person, mailbox = await _setup(world)
    await world.mailboxes.change(admin.id, mailbox.id, MailboxChanges(enabled=False))
    _deliver(world, mails.plain_mail())
    service = world.mail_intake()
    await _fetch(world, service)
    assert await world.documents.list_visible(person.id) == []
    with pytest.raises(ValidationError):
        await service.fetch_now(admin.id, mailbox.id)


async def test_fetch_now_brings_the_next_fetch_forward(world: World) -> None:
    admin, person, mailbox = await _setup(world)
    service = world.mail_intake()
    await _fetch(world, service)  # the first fetch; the next is due after the interval
    _deliver(world, mails.plain_mail("Später"))
    world.clock.advance(2 * LATER)
    assert await drain(service) == 0
    await service.fetch_now(admin.id, mailbox.id)
    assert await drain(service) == 1
    names = [
        document.original_filename for document in await world.documents.list_visible(person.id)
    ]
    assert names == ["Später.eml"]


async def test_the_documents_of_a_mail_relate_and_stay_related(world: World) -> None:
    _, _, mailbox = await _setup(world)
    _deliver(world, mails.rich_mail())
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        (record,) = await uow.mail_records.recent(mailbox.id, limit=5)
        cover, pdf, inner = (
            item.document_id for item in await uow.mail_origins.of_record(record.id)
        )
        made = await relate(uow, await uow.documents.get(cover), world.clock.now())
        await uow.commit()
    assert {frozenset(relation.key) for relation in made.made} == {
        frozenset((cover, pdf)),
        frozenset((cover, inner)),
    }
    assert {relation.evidence["kind"] for relation in made.made} == {"mail"}
    async with world.uow() as uow:
        again = await relate(uow, await uow.documents.get(pdf), world.clock.now())
        await uow.commit()
    assert again.dropped == ()


async def test_an_attachment_counts_its_sender_as_evidence(world: World) -> None:
    admin = await world.user(role=Role.ADMIN)
    domain = Identifier.parse(IdentifierKind.EMAIL_DOMAIN, "stadtwerke.example")
    utility = await world.master_data.create_contact(admin.id, "Stadtwerke", identifiers=[domain])
    _, _, mailbox = await _setup(world)
    _deliver(world, mails.rich_mail())
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        (record,) = await uow.mail_records.recent(mailbox.id, limit=5)
        origins = await uow.mail_origins.of_record(record.id)
        attachment = await uow.documents.get(origins[1].document_id)
    assert origins[1].role is OriginRole.ATTACHMENT
    await world.object_store.put(
        text_key(attachment.id), b"Rechnung 4711", content_type="text/plain; charset=utf-8"
    )
    found = await FactsSignal(world.uow, world.object_store).run(attachment)
    assert isinstance(found, FactsResult)
    identifiers = found.result.output["identifiers"]
    assert isinstance(identifiers, list)
    assert {item["contact_id"] for item in identifiers if isinstance(item, dict)} == {
        str(utility.id)
    }
    assert sender_line(None) == ""


async def _rule(world: World, admin: User, mailbox: Mailbox, **changes: Any) -> MailRule:
    values: dict[str, Any] = {"name": "Strom"}
    values.update(changes)
    return await world.mail_rules.create(admin.id, mailbox.id, MailRuleChanges(**values))


async def test_a_rule_on_the_marks_and_importance_of_a_mail(world: World) -> None:
    """Flag, keyword and importance decide; the record, the origin and the mailbox keep them."""
    admin, person, mailbox = await _setup(world, everything=False)
    await _rule(
        world,
        admin,
        mailbox,
        conditions=Group(
            mode="all",
            items=(
                MailCondition(MailField.FLAG, MailOperator.IS, "green"),
                MailCondition(MailField.KEYWORD, MailOperator.CONTAINS, "lekto"),
                Group(
                    mode="all",
                    items=(MailCondition(MailField.IMPORTANCE, MailOperator.IS, "low"),),
                    negate=True,
                ),
            ),
        ),
        user_id=person.id,
    )
    urgent = mails.plain_mail("Dringend").replace(b"Subject:", b"Importance: high\r\nSubject:", 1)
    green = frozenset({"\\Flagged", "$MailFlagBit0", "$MailFlagBit1", "Lekto"})
    _deliver(world, urgent, flags=green)
    _deliver(world, mails.plain_mail("Blau"), flags=frozenset({"\\Flagged", "$MailFlagBit2"}))
    await _fetch(world, world.mail_intake())

    (document,) = await world.documents.list_visible(person.id)
    assert document.original_filename == "Dringend.eml"
    async with world.uow() as uow:
        records = {r.subject: r for r in await uow.mail_records.recent(mailbox.id, limit=5)}
        origin = await uow.mail_origins.find(document.id)
        stored = await uow.mailboxes.get(mailbox.id)
    taken = records["Dringend"]
    assert (taken.importance, taken.marks) == (
        Importance.HIGH,
        MailMarks(keywords=("Lekto",), flag=FlagColor.GREEN),
    )
    assert records["Blau"].outcome is MailOutcome.NO_RULE
    assert origin is not None and (origin.importance, origin.marks) == (
        taken.importance,
        taken.marks,
    )
    assert (stored.status.keywords, stored.status.own_keywords) == (("Lekto",), True)


async def test_the_steps_on_a_mail_go_in_order_and_a_refused_one_shows(world: World) -> None:
    """Read, flag and keyword before the move, which the mail keeps; a server that stores no
    keywords of Lekto's own refuses the keyword and the flag's colour (Apple Mail's keywords),
    the mailbox says so, and the next steps go on."""
    admin, person, mailbox = await _setup(world, everything=False)
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    account.add_folders("Erledigt")
    steps = (
        MailStep(MailAction.READ),
        MailStep(MailAction.FLAG, "blue"),
        MailStep(MailAction.ADD_KEYWORD, "Lekto"),
        MailStep(MailAction.MOVE, "Erledigt"),
    )
    await _rule(world, admin, mailbox, user_id=person.id, after=steps)
    account.own_keywords = False
    _deliver(world, mails.plain_mail("Zweite"))
    await _fetch(world, world.mail_intake())
    (moved,) = account.boxes["Erledigt"].mails  # moved all the same, with its marks
    assert account.boxes["INBOX"].mails == []
    assert moved.seen and moved.flags == {"\\Flagged"}  # its colour is a keyword too
    async with world.uow() as uow:
        stored = await uow.mailboxes.get(mailbox.id)
    failed = stored.status.step_failed
    assert failed is not None and failed.code is ReasonCode.MAIL_STEP_FAILED
    assert (failed.params["step"], failed.params["subject"]) == ("mail_step:add_keyword", "Zweite")
    assert stored.status.step_failed_at is not None


async def test_a_rule_switched_on_later_takes_the_mails_no_rule_took(world: World) -> None:
    """Tobi, 06.11.2026: mails no rule took wait; a rule switched on afterwards takes those it
    matches at the next fetch, which switching it on brings forward. A mail gone from its folder
    no longer waits; the fallback never takes a waiting mail."""
    admin, person, mailbox = await _setup(world, everything=False)
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    _deliver(world, mails.plain_mail("Ihre Rechnung"))
    _deliver(world, mails.plain_mail("Unser Newsletter"))
    gone = _deliver(world, mails.plain_mail("Rechnung, gelöscht"))
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        assert len(await uow.mail_records.waiting(mailbox.id)) == 3
    inbox = account.boxes["INBOX"]
    inbox.mails = [mail for mail in inbox.mails if mail.uid != gone]  # deleted by the person

    rule = await _rule(
        world,
        admin,
        mailbox,
        conditions=Group(
            mode="all",
            items=(MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Rechnung"),),
        ),
        user_id=person.id,
        after=(MailStep(MailAction.READ),),
        enabled=False,
    )
    world.clock.advance(LATER)
    await world.mail_rules.change(admin.id, rule.id, MailRuleChanges(enabled=True))
    await drain(world.mail_intake())  # switching it on brought the fetch forward to now
    fetched = [event for event in world.events() if isinstance(event, MailboxFetched)]
    assert [(e.mailbox_id, e.mails, e.later) for e in fetched[-1:]] == [(mailbox.id, 0, 1)]

    (document,) = await world.documents.list_visible(person.id)
    assert document.original_filename == "Ihre Rechnung.eml"
    async with world.uow() as uow:
        records = {r.subject: r for r in await uow.mail_records.recent(mailbox.id, limit=9)}
        origin = await uow.mail_origins.find(document.id)
    taken = records["Ihre Rechnung"]
    assert (taken.outcome, taken.rule, taken.rule_id, taken.documents) == (
        MailOutcome.TAKEN,
        "Strom",
        rule.id,
        1,
    )
    assert taken.later and [item.step.action for item in taken.steps] == [MailAction.READ]
    assert origin is not None and origin.rule == "Strom"
    assert next(mail for mail in inbox.mails if mail.uid == taken.uid).seen
    assert records["Rechnung, gelöscht"].gone_at is not None
    assert records["Unser Newsletter"].waiting

    await world.mailboxes.change(
        admin.id,
        mailbox.id,
        MailboxChanges(fallback=Fallback.EVERYTHING, fallback_user_id=person.id),
    )
    intake = world.mail_intake()
    await intake.fetch_now(admin.id, mailbox.id)
    await drain(intake)
    assert len(await world.documents.list_visible(person.id)) == 1  # not the fallback's
    async with world.uow() as uow:
        assert [r.subject for r in await uow.mail_records.waiting(mailbox.id)] == [
            "Unser Newsletter"
        ]


async def test_the_dry_run_names_the_mails_waiting_for_a_rule(world: World) -> None:
    admin, person, mailbox = await _setup(world, everything=False)
    _deliver(world, mails.plain_mail("Ihre Rechnung"))
    await _fetch(world, world.mail_intake())
    draft = MailRuleChanges(
        name="Rechnungen",
        conditions=Group(
            mode="all",
            items=(MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Rechnung"),),
        ),
        user_id=person.id,
    )
    (item,) = await world.mail_rules.dry_run(admin.id, mailbox.id, draft)
    assert (item.waiting, item.decider, item.matches) == (True, Decider.RULE, True)


async def test_the_first_matching_rule_takes_a_mail(world: World) -> None:
    admin, person, mailbox = await _setup(world, everything=False)
    household = await world.spaces.create(admin.id, "Haushalt", members={person.id: SpaceRole.EDIT})
    letter = DocumentType.create(name="E-Mail", now=world.clock.now())
    async with world.uow() as uow:
        await uow.document_types.add(letter)
        await uow.commit()
    await _rule(
        world,
        admin,
        mailbox,
        name="Newsletter",
        priority=2,
        conditions=Group(
            mode="all",
            items=(MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Newsletter"),),
        ),
        parts=MailParts.NOTHING,
        after=(MailStep(MailAction.TRASH),),
    )
    await _rule(
        world,
        admin,
        mailbox,
        priority=1,
        conditions=Group(
            mode="all",
            items=(MailCondition(MailField.SENDER, MailOperator.ENDS_WITH, "@stadtwerke.example"),),
        ),
        user_id=person.id,
        space_id=household.id,
        text_type_id=letter.id,
        after=(MailStep(MailAction.READ),),
    )
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    account.add_folders("Trash")
    _deliver(world, mails.plain_mail("Unser Newsletter"))
    _deliver(world, mails.plain_mail("Ihre Rechnung"))
    await _fetch(world, world.mail_intake())

    (document,) = await world.documents.list_visible(person.id)
    assert (document.original_filename, document.space_id) == ("Ihre Rechnung.eml", household.id)
    async with world.uow() as uow:
        records = sorted(await uow.mail_records.recent(mailbox.id, limit=5), key=lambda r: r.uid)
        origin = await uow.mail_origins.find(document.id)
    assert [(record.outcome, record.rule) for record in records] == [
        (MailOutcome.NOTHING, "Newsletter"),
        (MailOutcome.TAKEN, "Strom"),
    ]
    assert origin is not None and (origin.rule, origin.body_type_id) == ("Strom", letter.id)
    assert [mail.seen for mail in account.boxes["INBOX"].mails] == [True]  # read; the other gone
    assert len(account.boxes["Trash"].mails) == 1


async def test_a_rule_whose_person_is_gone_pauses_and_the_fallback_takes(world: World) -> None:
    admin, person, mailbox = await _setup(world)
    other = await world.user()
    rule = await _rule(world, admin, mailbox, user_id=other.id)
    await world.users.update(admin.id, other.id, active=False)
    _deliver(world, mails.plain_mail())
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        stored = await uow.mail_rules.get(rule.id)
    assert not stored.enabled
    assert stored.disabled_reason is not None
    assert stored.disabled_reason.code is ReasonCode.MAIL_RULE_PERSON_GONE
    assert len(await world.documents.list_visible(person.id)) == 1  # by the fallback


async def test_only_admins_set_up_mail_rules_that_fit(world: World) -> None:
    admin, person, mailbox = await _setup(world)
    user = await world.user()
    with pytest.raises(PermissionDeniedError):
        await world.mail_rules.list_rules(user.id)
    with pytest.raises(PermissionDeniedError):
        await _rule(world, user, mailbox, user_id=person.id)
    stranger = await world.spaces.create(admin.id, "Fremd")
    with pytest.raises(ValidationError):
        await _rule(world, admin, mailbox, user_id=person.id, space_id=stranger.id)
    with pytest.raises(ValidationError):
        await _rule(world, admin, mailbox, user_id=person.id, text_type_id=DocumentTypeId(new_id()))
    made = await _rule(world, admin, mailbox, user_id=person.id)
    changed = await world.mail_rules.change(admin.id, made.id, MailRuleChanges(priority=7))
    assert changed.priority == 7
    assert [item.id for item in await world.mail_rules.list_rules(admin.id)] == [made.id]
    await world.mail_rules.delete(admin.id, made.id)
    assert await world.mail_rules.list_rules(admin.id) == []


async def test_the_mail_text_gets_the_type_of_its_rule(world: World) -> None:
    admin, person, mailbox = await _setup(world, everything=False)
    letter = DocumentType.create(name="E-Mail", now=world.clock.now())
    async with world.uow() as uow:
        await uow.document_types.add(letter)
        await uow.commit()
    await _rule(world, admin, mailbox, user_id=person.id, text_type_id=letter.id)
    rules = ApplyRulesNode(
        world.uow, world.object_store, RegexPatternMatcher(0.2), TEMPLATES, max_text=200_000
    )
    pipeline = world.pipeline({Node.APPLY_RULES: rules})
    _deliver(world, mails.rich_mail())
    await _fetch(world, world.mail_intake(pipeline))
    await world.drain(pipeline)
    documents = {
        document.media_type: document for document in await world.documents.list_visible(person.id)
    }
    assert documents["message/rfc822"].document_type_id == letter.id
    assert documents["application/pdf"].document_type_id is None  # an attachment: not the text


async def test_a_dry_run_over_the_latest_mails(world: World) -> None:
    admin, person, mailbox = await _setup(world, everything=False)
    other = await _rule(
        world,
        admin,
        mailbox,
        name="Newsletter",
        priority=3,
        conditions=Group(
            mode="all",
            items=(MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Newsletter"),),
        ),
        parts=MailParts.NOTHING,
    )
    _deliver(world, mails.plain_mail("Unser Newsletter"))
    _deliver(world, mails.rich_mail())
    _deliver(world, mails.plain_mail("Etwas anderes"))
    await _fetch(world, world.mail_intake())
    draft = MailRuleChanges(
        name="Mit Anhängen",
        priority=2,
        conditions=Group(
            mode="all", items=(MailCondition(MailField.ATTACHMENTS, MailOperator.PRESENT),)
        ),
        user_id=person.id,
    )
    found = await world.mail_rules.dry_run(admin.id, mailbox.id, draft)
    by_subject = {item.record.subject: item for item in found}
    assert len(found) == 3
    newsletter = by_subject["Unser Newsletter"]
    assert (newsletter.decider, newsletter.rule, newsletter.rule_id) == (
        Decider.OTHER,
        "Newsletter",
        other.id,
    )
    rich = by_subject["Ihre Rechnung über 123,45 €"]
    assert (rich.matches, rich.decider) == (True, Decider.RULE)
    assert rich.record.attachments == ("Rechnung 4711.pdf",)
    assert by_subject["Etwas anderes"].decider is Decider.NOTHING
    # Editing the stored rule: the draft stands in its place.
    edited = await world.mail_rules.dry_run(
        admin.id, mailbox.id, replace(draft, priority=0), rule=other.id
    )
    assert {item.decider for item in edited} == {Decider.RULE, Decider.NOTHING}
    with pytest.raises(PermissionDeniedError):
        await world.mail_rules.dry_run(person.id, mailbox.id, draft)


async def test_a_document_rule_looks_at_the_mail_a_document_came_with(world: World) -> None:
    admin, person, mailbox = await _setup(world)
    tag = await world.master_data.create_tag(admin.id, "Strom")
    rules = RuleService(world.uow, world.clock, TEMPLATES, RegexPatternMatcher(0.2))
    await rules.create(
        admin.id,
        RuleScope.GLOBAL,
        definition(
            "Strom per Mail",
            all_of(
                Condition(
                    field=ConditionField.MAIL_SENDER,
                    op=Operator.ENDS_WITH,
                    value="@stadtwerke.example",
                ),
                Condition(field=ConditionField.MAIL_MAILBOX, op=Operator.IS, value=str(mailbox.id)),
            ),
            add_tags(tag.id),
        ),
    )
    step = ApplyRulesNode(
        world.uow, world.object_store, RegexPatternMatcher(0.2), TEMPLATES, max_text=200_000
    )
    pipeline = world.pipeline({Node.APPLY_RULES: step})
    uploaded = await pipeline.receive(person.id, incoming(b"%PDF-1.7\n%%EOF\n"), filename="a.pdf")
    _deliver(world, mails.plain_mail())
    await _fetch(world, world.mail_intake(pipeline))
    await world.drain(pipeline)
    by_channel = {
        document.channel: document for document in await world.documents.list_visible(person.id)
    }
    assert tag.id in by_channel[Channel.MAIL].tag_ids
    assert tag.id not in by_channel[Channel.API].tag_ids
    assert uploaded.id == by_channel[Channel.API].id


async def _records(world: World, mailbox: Mailbox) -> list[Any]:
    async with world.uow() as uow:
        found = await uow.mail_records.recent(mailbox.id, limit=100)
    return sorted(found, key=lambda r: (r.fetched_at, r.uid))


async def _status(world: World, mailbox: Mailbox) -> Any:
    async with world.uow() as uow:
        return (await uow.mailboxes.get(mailbox.id)).status


async def test_a_folder_whose_uidvalidity_changed_is_read_again_without_doubles(
    world: World,
) -> None:
    _, person, mailbox = await _setup(world)
    _deliver(world, mails.plain_mail())
    service = world.mail_intake()
    await _fetch(world, service)
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    account.boxes["INBOX"].uidvalidity = 99  # the server renumbered the folder
    world.clock.advance(mailbox.interval)
    await _fetch(world, service)
    records = await _records(world, mailbox)
    assert [(record.uidvalidity, record.outcome) for record in records] == [
        (1, MailOutcome.TAKEN),
        (99, MailOutcome.KNOWN),  # the same Message-ID: fetched, not taken again
    ]
    assert len(await world.documents.list_visible(person.id)) == 1


async def test_more_mails_than_a_run_takes_come_in_the_next_run_at_once(world: World) -> None:
    _, person, mailbox = await _setup(world)
    for number in range(MAX_PER_RUN + 5):
        _deliver(world, mails.plain_mail(f"Mail {number}"))
    service = world.mail_intake()
    world.clock.advance(2 * LATER)
    assert await service.run_next_job()
    assert len(await world.documents.list_visible(person.id)) == MAX_PER_RUN
    async with world.uow() as uow:
        (job,) = await uow.jobs.find(
            now=world.clock.now(), states=[JobState.DUE], kind=FETCH_JOB, limit=5
        )
    assert job.run_at == world.clock.now()  # the rest at once, not after the interval
    assert await service.run_next_job()
    assert len(await world.documents.list_visible(person.id)) == MAX_PER_RUN + 5
    assert (await _status(world, mailbox)).mails == MAX_PER_RUN + 5


async def test_an_unreadable_mail_is_recorded_as_failed_and_the_fetch_goes_on(
    world: World,
) -> None:
    _, person, mailbox = await _setup(world)
    _deliver(world, b"no header lines at all\r\n")
    _deliver(world, mails.plain_mail("Gut"))
    await _fetch(world, world.mail_intake())
    records = await _records(world, mailbox)
    assert [record.outcome for record in records] == [MailOutcome.FAILED, MailOutcome.TAKEN]
    assert records[0].reason is not None and records[0].reason.code is ReasonCode.FILE_DAMAGED
    assert [d.original_filename for d in await world.documents.list_visible(person.id)] == [
        "Gut.eml"
    ]
    status = await _status(world, mailbox)
    assert (status.mails, status.documents, status.error) == (2, 1, None)


async def test_a_mail_gone_between_the_search_and_the_fetch_is_not_counted(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, person, mailbox = await _setup(world)
    _deliver(world, mails.plain_mail())

    async def gone(self: MemoryMailSession, folder: str, uid: int) -> bytes | None:
        return None

    monkeypatch.setattr(MemoryMailSession, "fetch", gone)
    await _fetch(world, world.mail_intake())
    assert await _records(world, mailbox) == []  # looked at next time, if it comes back
    assert await world.documents.list_visible(person.id) == []
    assert (await _status(world, mailbox)).mails == 0


async def test_a_mail_that_cannot_be_taken_is_recorded_as_failed_with_its_rule(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin, person, mailbox = await _setup(world, everything=False)
    await _rule(world, admin, mailbox, user_id=person.id)
    _deliver(world, mails.plain_mail())

    async def refuse(self: PipelineService, *args: object, **kwargs: object) -> None:
        raise ValidationError("the store is full")

    monkeypatch.setattr(PipelineService, "receive", refuse)
    await _fetch(world, world.mail_intake())
    (record,) = await _records(world, mailbox)
    assert (record.outcome, record.rule, record.documents) == (MailOutcome.FAILED, "Strom", 0)
    assert record.reason is not None and "full" in record.reason.text
    assert (await _status(world, mailbox)).error is None  # the fetch itself went well


async def test_a_rule_whose_space_or_type_is_gone_pauses_with_the_reason(world: World) -> None:
    admin, person, mailbox = await _setup(world)
    household = await world.spaces.create(
        admin.id, "Haushalt", members={person.id: SpaceRole.EDIT, admin.id: SpaceRole.EDIT}
    )
    letter = DocumentType.create(name="E-Mail", now=world.clock.now())
    async with world.uow() as uow:
        await uow.document_types.add(letter)
        await uow.commit()
    spaced = await _rule(
        world, admin, mailbox, name="Space", priority=2, user_id=person.id, space_id=household.id
    )
    typed = await _rule(
        world, admin, mailbox, name="Typ", priority=1, user_id=person.id, text_type_id=letter.id
    )
    await world.spaces.remove_member(admin.id, household.id, person.id)
    await world.master_data.delete_document_type(admin.id, letter.id)
    _deliver(world, mails.plain_mail())
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        reasons = {
            rule.name: rule.disabled_reason.code if rule.disabled_reason else None
            for rule in await uow.mail_rules.of_mailbox(mailbox.id)
        }
    assert reasons == {
        spaced.name: ReasonCode.MAIL_RULE_SPACE_UNREACHABLE,
        typed.name: ReasonCode.MAIL_RULE_TYPE_GONE,
    }
    (record,) = await _records(world, mailbox)
    assert (record.outcome, record.rule) == (MailOutcome.TAKEN, None)  # by the fallback


async def test_a_deactivated_fallback_person_takes_nothing(world: World) -> None:
    admin, person, mailbox = await _setup(world)
    await world.users.update(admin.id, person.id, active=False)
    _deliver(world, mails.plain_mail())
    await _fetch(world, world.mail_intake())
    (record,) = await _records(world, mailbox)
    assert record.outcome is MailOutcome.NO_RULE


async def test_the_worker_start_queues_the_fetch_of_every_enabled_mailbox(world: World) -> None:
    admin, _, mailbox = await _setup(world)
    paused = await world.mailboxes.create(
        admin.id,
        name="Pausiert",
        host=LOGIN.host,
        port=LOGIN.port,
        security=LOGIN.security,
        username="other",
        password="x",
        changes=MailboxChanges(enabled=False),
    )
    service = world.mail_intake()
    await _fetch(world, service)  # the next fetch is queued after the interval
    async with world.uow() as uow:  # a worker that died took the queued job with it
        world.clock.advance(timedelta(hours=1))
        job = await uow.jobs.claim(now=world.clock.now(), lease=LEASE, kinds=[FETCH_JOB])
        assert job is not None
        await uow.jobs.complete(job, now=world.clock.now())
        await uow.commit()
    await service.schedule()
    async with world.uow() as uow:
        queued = await uow.jobs.find(
            now=world.clock.now(), states=[JobState.DUE, JobState.PLANNED], kind=FETCH_JOB, limit=5
        )
    assert [job.dedup_key for job in queued] == [fetch_key(mailbox.id)]  # not the paused one
    assert paused.enabled is False


async def test_the_job_of_a_deleted_mailbox_ends(world: World) -> None:
    admin, _, mailbox = await _setup(world)
    await world.mailboxes.delete(admin.id, mailbox.id)
    service = world.mail_intake()
    world.clock.advance(2 * LATER)
    assert await service.run_next_job()  # ran and ended
    async with world.uow() as uow:
        queued = await uow.jobs.find(
            now=world.clock.now(), states=[JobState.DUE, JobState.PLANNED], kind=FETCH_JOB, limit=5
        )
    assert queued == []


async def test_a_password_that_cannot_be_read_shows_at_the_mailbox(world: World) -> None:
    _, _, mailbox = await _setup(world)
    async with world.uow() as uow:
        stored = await uow.mailboxes.get(mailbox.id)
        stored.set_password(b"written with another key", now=world.clock.now())
        await uow.mailboxes.update(stored)
        await uow.commit()
    await _fetch(world, world.mail_intake())
    status = await _status(world, mailbox)
    assert status.error is not None and status.error.code is ReasonCode.MAIL_PASSWORD_UNREADABLE


async def test_a_mailbox_that_starts_from_a_day(world: World) -> None:
    _, person, _ = await _setup(
        world, start=FetchStart.SINCE_DATE, since=world.clock.now().date() - timedelta(days=7)
    )
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    account.deliver(
        "INBOX", mails.plain_mail("Alt"), arrived_at=world.clock.now() - timedelta(days=8)
    )
    account.deliver(
        "INBOX", mails.plain_mail("Neuer"), arrived_at=world.clock.now() - timedelta(days=6)
    )
    await _fetch(world, world.mail_intake())
    names = [d.original_filename for d in await world.documents.list_visible(person.id)]
    assert names == ["Neuer.eml"]


async def test_a_missing_folder_ends_the_fetch_after_the_others(world: World) -> None:
    _, person, mailbox = await _setup(world, folders=("INBOX", "Nirgends"))
    _deliver(world, mails.plain_mail())
    await _fetch(world, world.mail_intake())
    assert len(await world.documents.list_visible(person.id)) == 1  # INBOX came first
    status = await _status(world, mailbox)
    assert status.error is not None and status.error.code is ReasonCode.MAIL_FOLDER_MISSING
    assert status.error.params == {"folder": "Nirgends"}
    assert (status.mails, status.last_success_at) == (1, None)


async def test_an_attachment_larger_than_an_upload_is_left_out(world: World) -> None:
    """The mail itself fits (`mail_limit` leaves room for its head); the attachment does not."""
    _, person, mailbox = await _setup(world)
    message = EmailMessage()
    message["From"] = "a@example.test"
    message["Date"] = "Wed, 04 Nov 2026 10:00:00 +0100"
    message["Subject"] = "Fotos"
    message.set_content("Anbei.")
    message.add_attachment(
        mails.PDF + b"x" * 3000, maintype="application", subtype="pdf", filename="Gross.pdf"
    )
    _deliver(world, bytes(message))
    await _fetch(world, world.mail_intake(max_attachment=2000))
    names = [d.original_filename for d in await world.documents.list_visible(person.id)]
    assert names == ["Fotos.eml"]  # the text, without the attachment
    (record,) = await _records(world, mailbox)
    assert (record.outcome, record.documents) == (MailOutcome.TAKEN, 1)
