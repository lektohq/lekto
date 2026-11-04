"""Fetching mail: a job per mailbox, what each mail brings in by the mailbox's fallback, what is
not fetched twice, and what shows at the mailbox."""

from datetime import timedelta
from email.message import EmailMessage

import pytest

from lekto.core.domain.documents import Channel
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.identifiers import Identifier, IdentifierKind
from lekto.core.domain.jobs import JobState
from lekto.core.domain.mail import (
    Fallback,
    FetchStart,
    Mailbox,
    MailboxChanges,
    MailLogin,
    MailSecurity,
)
from lekto.core.domain.mail_intake import MailOutcome, OriginRole
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.users import Role, User
from lekto.core.services.classification.signals import FactsResult, FactsSignal, sender_line
from lekto.core.services.mail_intake import FETCH_JOB, MailIntakeService, fetch_key
from lekto.core.services.objects import text_key
from lekto.core.services.relating import relate
from tests import mails
from tests.builders import drain, incoming
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


def _deliver(world: World, data: bytes, *, folder: str = "INBOX", seen: bool = False) -> int:
    account = world.mail_server.servers[(LOGIN.host, LOGIN.port)][LOGIN.username]
    return account.deliver(folder, data, arrived_at=world.clock.now() + LATER, seen=seen)


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


async def test_a_mail_too_large_is_recorded(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _, person, mailbox = await _setup(world)
    monkeypatch.setattr("lekto.core.services.mail_intake.MAX_MAIL_SIZE", 10)
    _deliver(world, mails.plain_mail())
    await _fetch(world, world.mail_intake())
    async with world.uow() as uow:
        (record,) = await uow.mail_records.recent(mailbox.id, limit=5)
    assert record.outcome is MailOutcome.TOO_LARGE
    assert await world.documents.list_visible(person.id) == []


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
