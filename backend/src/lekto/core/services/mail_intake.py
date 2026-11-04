"""Fetching mail: a job per mailbox that looks into its folders, takes what is new and plans
the next fetch (umsetzungsplan "Eingangskanal Mail").

Each mailbox has one job (`fetch_key`): it runs, then queues the next after the mailbox's
interval; "Jetzt abrufen" brings the waiting one forward (`fetch_now`). A fetch signs in once,
looks into each folder for the mails its start allows (since setup, from a day, unread) that
were not fetched before (by the folder's UIDVALIDITY and UID, by Message-ID across folders and
mailboxes), reads each with `BODY.PEEK` (nothing marked) and records what became of it. At most
`MAX_PER_RUN` mails a run; with more, the next run comes at once.

What a mail brings in, the mailbox's fallback decides until the mail rules come (PR 4):
nothing, or everything for one person into their personal space. Of each letter of the mail
(`mail_intake.letters`) the readable attachments come first, then the letter's text as its
`.eml`; each becomes a document through `PipelineService.receive` with the channel `mail`, its
origin kept beside it. An attachment Lekto has already is not taken again; the cover letter
refers to it where the person reads it. A failure of the server ends the fetch and shows at
the mailbox; a mail that cannot be taken is recorded as failed and the fetch goes on.
"""

import asyncio
import logging
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from lekto.core.domain.documents import Channel
from lekto.core.domain.errors import (
    DomainError,
    DuplicateDocumentError,
    UnprocessableDocumentError,
    ValidationError,
)
from lekto.core.domain.ids import DocumentId, MailboxId, MailRecordId, UserId, new_id
from lekto.core.domain.jobs import Job
from lekto.core.domain.mail import (
    Fallback,
    FetchStart,
    MailAction,
    Mailbox,
    MailboxStatus,
    MailLogin,
    password_context,
)
from lekto.core.domain.mail_intake import (
    Letter,
    MailDecision,
    MailOrigin,
    MailOutcome,
    MailParts,
    MailRecord,
    OriginRole,
    letters,
    mail_limit,
    taken_names,
)
from lekto.core.domain.mail_message import MailMessage, read_mail
from lekto.core.domain.mail_rules import MailRule, first_match, mail_facts
from lekto.core.domain.permissions import can_file_into
from lekto.core.domain.reasons import Action, Reason, ReasonCode, because
from lekto.core.ports.clock import Clock
from lekto.core.ports.identity import DecryptionError, SecretCipher
from lekto.core.ports.mail_server import (
    MailInfo,
    MailSearch,
    MailServer,
    MailServerError,
    MailSession,
)
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._access import load_actor, readable_document, require_admin
from lekto.core.services._jobs import JobRunner, retrying
from lekto.core.services.pipeline import IncomingFile, PipelineService

log = logging.getLogger(__name__)

FETCH_JOB = "mail.fetch"
"""Job kind of a mailbox's fetch; payload: `{"mailbox_id": ...}`."""
LEASE = timedelta(minutes=30)
MAX_PER_RUN = 50
STORE_ATTEMPTS = 5


def fetch_key(id: MailboxId) -> str:
    """The dedup key of a mailbox's one job."""
    return f"mail:{id}"


async def schedule_fetch(uow: UnitOfWork, mailbox: Mailbox, run_at: datetime) -> None:
    """Queue the mailbox's fetch at `run_at`, or bring the queued one forward to it."""
    if not await uow.jobs.hasten(fetch_key(mailbox.id), run_at=run_at):
        await uow.jobs.enqueue(
            FETCH_JOB,
            {"mailbox_id": str(mailbox.id)},
            run_at=run_at,
            dedup_key=fetch_key(mailbox.id),
        )


@dataclass
class _Count:
    mails: int = 0
    documents: int = 0
    more: bool = False  # mails were left for the next run
    skipped: Reason | None = None  # the latest mail left out, too large


class MailIntakeService:
    job_kinds = (FETCH_JOB,)
    """The kinds of jobs `run_next_job` runs."""

    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        cipher: SecretCipher,
        server: MailServer,
        pipeline: PipelineService,
        *,
        max_attachment: int,
    ) -> None:
        """`max_attachment`: the largest file taken from a mail, as an upload
        (`LEKTO_UPLOAD_MAX_SIZE`)."""
        self._uow = uow
        self._clock = clock
        self._cipher = cipher
        self._server = server
        self._pipeline = pipeline
        self._max_attachment = max_attachment
        self._max_mail = mail_limit(max_attachment)
        self._jobs = JobRunner(uow, clock)

    async def schedule(self) -> None:
        """Make sure every enabled mailbox has its job (at the worker's start)."""
        async with self._uow() as uow:
            for mailbox in await uow.mailboxes.list_all():
                if mailbox.enabled and not await uow.jobs.hasten(
                    fetch_key(mailbox.id), run_at=self._clock.now() + mailbox.interval
                ):
                    await schedule_fetch(uow, mailbox, self._clock.now())
            await uow.commit()

    async def fetch_now(self, actor: UserId, id: MailboxId) -> None:
        """Fetch the mailbox as soon as a worker can (admins). ValidationError if it is paused."""
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            mailbox = await uow.mailboxes.get(id)
            if not mailbox.enabled:
                raise ValidationError(because(ReasonCode.MAILBOX_PAUSED))
            await schedule_fetch(uow, mailbox, self._clock.now())
            await uow.commit()

    async def origin(self, actor: UserId, id: DocumentId) -> MailOrigin | None:
        """Where the document came from if a mail brought it. NotFoundError if the caller does
        not read the document."""
        async with self._uow() as uow:
            user = await load_actor(uow, actor)
            await readable_document(uow, user, id)
            return await uow.mail_origins.find(id)

    async def run_next_job(self) -> bool:
        return await self._jobs.run_next(self.job_kinds, LEASE, self._run)

    async def _run(self, job: Job) -> None:
        try:
            id = MailboxId(UUID(str(job.payload["mailbox_id"])))
        except (KeyError, ValueError) as invalid:
            await self._jobs.invalid(job, invalid)
            return
        async with self._uow() as uow:
            mailbox = await uow.mailboxes.find(id)
        if mailbox is None or not mailbox.enabled:
            await self._jobs.end(job)  # deleted or paused: no next fetch until it is enabled
            return
        started = self._clock.now()
        count = _Count()
        error: Reason | None = None
        try:
            login = self._login(mailbox)
            async with self._server.session(login) as session:
                for folder in mailbox.folders:
                    await self._folder(session, mailbox, folder, count)
        except DecryptionError:
            error = because(ReasonCode.MAIL_PASSWORD_UNREADABLE)
        except MailServerError as failure:
            error = failure.reason
        if error is not None:
            log.info("fetching mail failed", extra={"mailbox_id": str(id), "reason": error.text})
        await self._finish(job, id, started, count, error)

    def _login(self, mailbox: Mailbox) -> MailLogin:
        """Raises DecryptionError."""
        password = self._cipher.decrypt(
            mailbox.encrypted_password, context=password_context(mailbox.id)
        ).decode()
        return MailLogin(
            host=mailbox.host,
            port=mailbox.port,
            security=mailbox.security,
            username=mailbox.username,
            password=password,
        )

    async def _finish(
        self, job: Job, id: MailboxId, started: datetime, count: _Count, error: Reason | None
    ) -> None:
        """Record what the fetch found at the mailbox, end the job and queue the next one."""

        async def store() -> None:
            now = self._clock.now()
            async with self._uow() as uow:
                mailbox = await uow.mailboxes.find(id)
                if mailbox is not None:
                    status = mailbox.status
                    mailbox.record(
                        MailboxStatus(
                            last_attempt_at=started,
                            last_success_at=status.last_success_at if error else started,
                            error=error,
                            mails=status.mails + count.mails,
                            documents=status.documents + count.documents,
                            skipped_at=started if count.skipped else status.skipped_at,
                            skipped=count.skipped or status.skipped,
                        )
                    )
                    await uow.mailboxes.update(mailbox)
                await uow.jobs.complete(
                    job, now=now, result={"mails": count.mails, "documents": count.documents}
                )
                if mailbox is not None and mailbox.enabled:
                    await schedule_fetch(
                        uow,
                        mailbox,
                        now if count.more and error is None else now + mailbox.interval,
                    )
                await uow.commit()

        await retrying(store, attempts=STORE_ATTEMPTS, backoff=True)

    async def _folder(
        self, session: MailSession, mailbox: Mailbox, folder: str, count: _Count
    ) -> None:
        search = _search(mailbox)
        found = await session.search(folder, search)
        async with self._uow() as uow:
            known = await uow.mail_records.known_uids(mailbox.id, folder, found.uidvalidity)
        new = [uid for uid in found.uids if uid not in known]
        room = MAX_PER_RUN - count.mails
        if len(new) > room:
            count.more = True
            new = new[:room]
        for info in await session.info(folder, new):
            if mailbox.start is FetchStart.SINCE_SETUP and info.arrived_at < mailbox.created_at:
                continue  # the same day, before the mailbox was set up
            count.mails += 1
            count.documents += await self._mail(
                session, mailbox, folder, found.uidvalidity, info, count
            )

    async def _mail(
        self,
        session: MailSession,
        mailbox: Mailbox,
        folder: str,
        uidvalidity: int,
        info: MailInfo,
        count: _Count,
    ) -> int:
        """Take one mail; the number of documents it made."""
        record = MailRecord(
            id=MailRecordId(new_id()),
            mailbox_id=mailbox.id,
            folder=folder,
            uidvalidity=uidvalidity,
            uid=info.uid,
            message_id=None,
            sender="",
            subject="",
            sent_at=None,
            arrived_at=info.arrived_at,
            size=info.size,
            outcome=MailOutcome.TOO_LARGE,
            fetched_at=self._clock.now(),
        )
        if info.size > self._max_mail:
            record = _named(record, await session.head(folder, info.uid))
            reason = because(
                ReasonCode.MAIL_TOO_LARGE,
                subject=record.subject,
                size=_megabytes(info.size),
                max=_megabytes(self._max_mail),
            )
            log.warning(
                "a mail too large to fetch",
                extra={"mailbox_id": str(mailbox.id), "size": info.size},
            )
            count.skipped = reason
            await self._keep(replace(record, reason=reason))
            return 0
        data = await session.fetch(folder, info.uid)
        if data is None:
            return 0  # gone meanwhile: looked at next time, if it comes back
        try:
            message = read_mail(data)
        except UnprocessableDocumentError as error:
            await self._keep(replace(record, outcome=MailOutcome.FAILED, reason=error.reason))
            return 0
        facts = mail_facts(message, folder)
        record = replace(
            record,
            message_id=message.message_id,
            sender=", ".join(address.shown for address in message.sender),
            subject=message.subject,
            sent_at=message.date,
            senders=facts.senders,
            recipients=facts.recipients,
            attachments=taken_names(message),
        )
        if message.message_id is not None:
            async with self._uow() as uow:
                if await uow.mail_records.has_message(message.message_id):
                    await self._keep(replace(record, outcome=MailOutcome.KNOWN))
                    return 0
        decision = await self._decide(mailbox, message, folder)
        if decision is None:
            await self._keep(replace(record, outcome=MailOutcome.NO_RULE))
            return 0
        try:
            made = await self._take(mailbox, record, message, decision)
        except DomainError as error:
            log.warning(
                "a mail could not be taken",
                extra={"mailbox_id": str(mailbox.id), "reason": error.reason.text},
            )
            await self._keep(
                replace(record, outcome=MailOutcome.FAILED, reason=error.reason, rule=decision.rule)
            )
            return 0
        outcome = MailOutcome.TAKEN if made else MailOutcome.NOTHING
        await self._keep(replace(record, outcome=outcome, rule=decision.rule, documents=made))
        await self._after(session, folder, info.uid, decision)
        return made

    async def _decide(
        self, mailbox: Mailbox, message: MailMessage, folder: str
    ) -> MailDecision | None:
        """The first of the mailbox's rules that matches, else the mailbox's fallback; None
        for nothing. A rule whose person, space or type is gone or out of reach is paused with
        the reason, and the next one asked."""
        facts = mail_facts(message, folder)
        async with self._uow() as uow:
            rules = await uow.mail_rules.of_mailbox(mailbox.id)
        while (rule := first_match(rules, facts)) is not None:
            problem = await self._unfit(rule)
            if problem is None:
                return rule.decision()
            await self._pause(rule, problem)
            rules = [item for item in rules if item.id != rule.id]
        if mailbox.fallback is not Fallback.EVERYTHING or mailbox.fallback_user_id is None:
            return None
        async with self._uow() as uow:
            person = await uow.users.find(mailbox.fallback_user_id)
        if person is None or not person.active:
            return None
        return MailDecision(user_id=person.id, body_type_id=mailbox.body_type_id)

    async def _unfit(self, rule: MailRule) -> Reason | None:
        """Why the rule cannot take a mail now; None if it can."""
        if rule.user_id is None:
            return None
        async with self._uow() as uow:
            person = await uow.users.find(rule.user_id)
            if person is None or not person.active:
                return because(ReasonCode.MAIL_RULE_PERSON_GONE)
            if rule.space_id is not None:
                space = await uow.spaces.find(rule.space_id)
                if space is None or not can_file_into(person, space):
                    return because(ReasonCode.MAIL_RULE_SPACE_UNREACHABLE)
            if rule.text_type_id is not None and (
                await uow.document_types.find(rule.text_type_id) is None
            ):
                return because(ReasonCode.MAIL_RULE_TYPE_GONE)
        return None

    async def _pause(self, rule: MailRule, reason: Reason) -> None:
        async def store() -> None:
            async with self._uow() as uow:
                current = await uow.mail_rules.find(rule.id)
                if current is not None and current.enabled:
                    current.pause(reason, now=self._clock.now())
                    await uow.mail_rules.update(current)
                    await uow.commit()

        log.info("a mail rule paused", extra={"rule_id": str(rule.id), "reason": reason.text})
        await retrying(store, attempts=STORE_ATTEMPTS, backoff=True)

    async def _take(
        self, mailbox: Mailbox, record: MailRecord, message: MailMessage, decision: MailDecision
    ) -> int:
        made = 0
        if decision.user_id is None or decision.parts is MailParts.NOTHING:
            return made
        with tempfile.TemporaryDirectory(prefix="lekto-mail-") as work:
            folder = Path(work)
            for number, letter in enumerate(letters(message)):
                origin = self._origin(mailbox, record, letter, number, decision)
                related: list[DocumentId] = []
                if decision.parts in (MailParts.ALL, MailParts.ATTACHMENTS):
                    for index, part in enumerate(letter.taken):
                        if len(part.data) > self._max_attachment:
                            continue
                        name = part.filename or f"attachment-{index + 1}"
                        found = await self._receive(folder, part.data, name, decision)
                        if found is None:
                            continue
                        document, new = found
                        if new:
                            await self._keep_origin(
                                replace(
                                    origin,
                                    document_id=document,
                                    role=OriginRole.ATTACHMENT,
                                    filename=name,
                                )
                            )
                            made += 1
                        else:
                            related.append(document)
                if decision.parts in (MailParts.ALL, MailParts.TEXT):
                    name = f"{_stem(letter.message.subject)}.eml"
                    found = await self._receive(folder, letter.message.raw, name, decision)
                    if found is not None and found[1]:
                        await self._keep_origin(
                            replace(
                                origin,
                                document_id=found[0],
                                role=OriginRole.COVER,
                                filename=name,
                                related=tuple(related),
                                body_type_id=decision.body_type_id,
                            )
                        )
                        made += 1
        return made

    def _origin(
        self,
        mailbox: Mailbox,
        record: MailRecord,
        letter: Letter,
        number: int,
        decision: MailDecision,
    ) -> MailOrigin:
        message = letter.message
        return MailOrigin(
            document_id=DocumentId(new_id()),
            record_id=record.id,
            mailbox_id=mailbox.id,
            mailbox=mailbox.name,
            rule=decision.rule,
            role=OriginRole.COVER,
            letter=number,
            outer=letter.outer,
            message_id=message.message_id,
            sender=message.sender,
            to=message.to,
            cc=message.cc,
            subject=message.subject,
            sent_at=message.date,
            arrived_at=record.arrived_at,
            forwarded_by=letter.forwarded_by,
        )

    async def _receive(
        self, folder: Path, data: bytes, name: str, decision: MailDecision
    ) -> tuple[DocumentId, bool] | None:
        """The document made of `data`, and whether it is new; for a file Lekto has already the
        one the person reads (None where they read it not)."""
        assert decision.user_id is not None, "a decision that takes names its person"
        path = folder / new_id().hex
        await asyncio.to_thread(path.write_bytes, data)
        file = await asyncio.to_thread(IncomingFile.of, path)
        try:
            document = await self._pipeline.receive(
                decision.user_id,
                file,
                filename=name,
                space=decision.space_id,
                channel=Channel.MAIL,
            )
        except DuplicateDocumentError as duplicate:
            existing = duplicate.existing
            return None if existing is None else (DocumentId(existing), False)
        finally:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        return document.id, True

    async def _keep(self, record: MailRecord) -> None:
        async with self._uow() as uow:
            await uow.mail_records.add(record)
            await uow.commit()

    async def _keep_origin(self, origin: MailOrigin) -> None:
        async with self._uow() as uow:
            await uow.mail_origins.add(origin)
            await uow.commit()

    async def _after(
        self, session: MailSession, folder: str, uid: int, decision: MailDecision
    ) -> None:
        """What the decision does to the mail on the server; a failure there is logged only."""
        try:
            if decision.after is MailAction.READ:
                await session.mark_read(folder, uid)
            elif decision.after is MailAction.TRASH:
                await session.trash(folder, uid)
            elif decision.after is MailAction.MOVE and decision.move_to:
                await session.move(folder, uid, decision.move_to)
        except MailServerError as error:
            log.warning("the action on a mail failed", extra={"reason": error.reason.text})


def _named(record: MailRecord, head: bytes | None) -> MailRecord:
    """The record with the sender, subject and Message-ID of the mail's header lines."""
    if not head:
        return record
    try:
        message = read_mail(head)
    except UnprocessableDocumentError:
        return record
    return replace(
        record,
        message_id=message.message_id,
        sender=", ".join(address.shown for address in message.sender),
        subject=message.subject,
        sent_at=message.date,
    )


def _megabytes(size: int) -> int:
    """Whole megabytes, rounded up."""
    return -(-size // (1024 * 1024))


def _search(mailbox: Mailbox) -> MailSearch:
    if mailbox.start is FetchStart.UNREAD:
        return MailSearch(unseen=True)
    if mailbox.start is FetchStart.SINCE_DATE:
        return MailSearch(since=mailbox.since)
    return MailSearch(since=mailbox.created_at.date())


def _stem(subject: str) -> str:
    """A file name of a subject: no separators, at most 100 characters."""
    cleaned = "".join("_" if char in '/\\:*?"<>|' else char for char in subject).strip(" .")
    return cleaned[:100] or "Mail"
