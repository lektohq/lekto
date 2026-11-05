"""Fetching mail: a job per mailbox, what each mail brings in by the mailbox's fallback, what is
not fetched twice, and what shows at the mailbox."""

from dataclasses import replace
from datetime import timedelta
from email.message import EmailMessage
from typing import Any

import pytest

from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.core.domain.condition_tree import Group
from lekto.core.domain.documents import Channel
from lekto.core.domain.errors import PermissionDeniedError, ValidationError
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
from lekto.core.services.classification.signals import FactsResult, FactsSignal, sender_line
from lekto.core.services.mail_intake import (
    FETCH_JOB,
    MAX_PER_RUN,
    MailIntakeService,
    fetch_key,
)
from lekto.core.services.mail_rules import Decider
from lekto.core.services.objects import text_key
from lekto.core.services.relating import relate
from lekto.core.services.rules.management import RuleService
from lekto.core.services.rules.nodes import ApplyRulesNode
from tests import mails
from tests.builders import TEMPLATES, drain, incoming
from tests.unit.services.rules_support import add_tags, all_of, definition
from tests.unit.services.support import World

LOGIN = MailLogin(
    host="imap.example.test",
    port=993,
    security=MailSecurity.TLS,
    username="household@example.test",
    password="right",
)
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
        outcomes = sorted(
            [record.outcome for record in await uow.mail_records.recent(first.id, limit=5)]
            + [record.outcome for record in await uow.mail_records.recent(second.id, limit=5)]
        )
    assert outcomes in (
        [MailOutcome.KNOWN, MailOutcome.TAKEN],
        [MailOutcome.KNOWN, MailOutcome.NO_RULE],
    )


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
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
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
    assert (by_subject["Unser Newsletter"].decider, by_subject["Unser Newsletter"].rule) == (
        Decider.OTHER,
        "Newsletter",
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
