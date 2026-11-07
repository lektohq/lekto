"""Notifications on a person's devices (web push; web/DESIGN.md, "App").

A device belongs to its owner alone: nobody else, admins included, learns that it exists
(NotFoundError). A browser's address at its push service is one device: subscribing again (after
another person signed in there) moves it to whoever subscribes. Each delivery is recorded on the
device: a push service that no longer knows it (404, 410) or failures in a row
(`GIVE_UP_AFTER`) make Lekto forget it. Without a VAPID key the server sends nothing and takes no
device (`push_off`). Devices are settings: no events.
"""

import logging
from dataclasses import replace
from datetime import timedelta
from uuid import UUID

from lekto.core.domain.errors import ConcurrencyError, ConflictError, NotFoundError
from lekto.core.domain.events import DomainEvent, ReviewRequired
from lekto.core.domain.ids import PushDeviceId, UserId, new_id
from lekto.core.domain.inbox import InboxTab
from lekto.core.domain.jobs import Job
from lekto.core.domain.json_value import JsonObject
from lekto.core.domain.pipeline import Lane
from lekto.core.domain.push import (
    ADMIN_KINDS,
    GIVE_UP_AFTER,
    MAX_DEVICES,
    PushDevice,
    PushKind,
    PushMessage,
    PushPreferences,
)
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.clock import Clock
from lekto.core.ports.push import PushOutcome, PushResult, PushSender
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._jobs import JobRunner
from lekto.core.services._push_queue import PUSH_JOB, queue_push
from lekto.core.services.inbox import InboxService, in_inbox

log = logging.getLogger(__name__)

SUBSCRIBER = "push"
"""The name of the event bus subscription that notes documents coming to wait."""

LEASE = timedelta(minutes=2)
TITLES = 3
"""Titles of documents a notification names at most."""


class PushService:
    job_kinds = (PUSH_JOB,)
    """The kinds of jobs `run_next_job` runs."""

    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        sender: PushSender | None,
        inbox: InboxService,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._sender = sender
        self._inbox = inbox
        self._jobs = JobRunner(uow, clock)

    # --- what a person wants ----------------------------------------------------------------

    async def preferences(self, actor: UserId) -> PushPreferences:
        async with self._uow() as uow:
            return await uow.push_preferences.find(actor) or PushPreferences(id=actor)

    async def set_preferences(
        self, actor: UserId, *, kinds: frozenset[PushKind], titles: bool
    ) -> PushPreferences:
        async with self._uow() as uow:
            preferences = await uow.push_preferences.find(actor) or PushPreferences(id=actor)
            preferences = replace(preferences, kinds=kinds, titles=titles)
            await uow.push_preferences.save(preferences)
            await uow.commit()
        return preferences

    # --- what causes a notification ---------------------------------------------------------

    async def on_event(self, event: DomainEvent) -> None:
        """The event bus subscriber: a document came to wait (yellow or red) for its editors;
        each who has a device and wants it notes the document for their next notification."""
        if self._sender is None or not isinstance(event, ReviewRequired):
            return
        async with self._uow() as uow:
            document = await uow.documents.find(event.document_id)
            space = None if document is None else await uow.spaces.find(document.space_id)
            if document is None or space is None:
                return
            queued: list[UserId] = []
            for editor in sorted(space.editors):
                user = await uow.users.find(editor)
                if user is None or not user.active:
                    continue
                if not await uow.push_devices.list_for(editor):
                    continue
                preferences = await uow.push_preferences.find(editor) or PushPreferences(id=editor)
                if not preferences.wants(PushKind.WAITING):
                    continue
                preferences.note_waiting(document.id)
                await uow.push_preferences.save(preferences)
                queued.append(editor)
            await queue_push(uow, self._clock.now(), queued, PushKind.WAITING)
            await uow.commit()

    # --- sending ------------------------------------------------------------------------------

    async def run_next_job(self) -> bool:
        """Claim and send a due notification; False if none was due."""
        return await self._jobs.run_next([PUSH_JOB], LEASE, self._run)

    async def _run(self, job: Job) -> None:
        try:
            user = UserId(UUID(str(job.payload["user_id"])))
            kind = PushKind(str(job.payload["kind"]))
            params = job.payload.get("params") or {}
            assert isinstance(params, dict)
        except (KeyError, ValueError, AssertionError) as error:
            await self._jobs.invalid(job, error)
            return
        message = await self._message(user, kind, params)
        sent = 0 if message is None else await self.send_to(user, message)
        await self._jobs.end(job, result={"sent": sent})

    async def _message(
        self, user: UserId, kind: PushKind, params: JsonObject
    ) -> PushMessage | None:
        """What to tell `user` now, None if nothing (switched off, gone meanwhile)."""
        async with self._uow() as uow:
            person = await uow.users.find(user)
            preferences = await uow.push_preferences.find(user) or PushPreferences(id=user)
            if person is None or not person.active or not preferences.wants(kind):
                return None
            if kind in ADMIN_KINDS and not person.is_admin:
                return None
            if kind is not PushKind.WAITING:
                return _notice(kind, params)
            pending = preferences.pending
            if pending:
                preferences.pending = ()
                await uow.push_preferences.save(preferences)
            documents = [d for d in [await uow.documents.find(id) for id in pending] if d]
            waiting = await in_inbox(uow, user, documents, all_users=False)
            still = [
                document
                for document in reversed(documents)
                if document.id in waiting and document.lane in (Lane.YELLOW, Lane.RED)
            ]
            await uow.commit()
        if not still:
            return None
        summary = await self._inbox.summary(user)
        count = summary.counts.get(InboxTab.REVIEW, 0) + summary.counts.get(InboxTab.INTERVENE, 0)
        one = still[0].id if len(still) == 1 else None
        return PushMessage(
            kind=PushKind.WAITING,
            params={
                "count": max(count, len(still)),
                "new": len(still),
                "titles": [d.title for d in still[:TITLES]] if preferences.titles else [],
            },
            url=f"/ui/documents/{one}" if one is not None else "/ui/inbox",
            badge=summary.open,
            tag="lekto-waiting",
            topic="waiting",
        )

    @property
    def enabled(self) -> bool:
        return self._sender is not None

    @property
    def public_key(self) -> str | None:
        """The key browsers subscribe with; None without push."""
        return None if self._sender is None else self._sender.public_key

    async def register(
        self,
        actor: UserId,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
        name: str,
        locale: str,
    ) -> PushDevice:
        """Take a browser's subscription for `actor`; the same address again replaces it."""
        self._sender_or_off()
        now = self._clock.now()
        device = PushDevice(
            id=PushDeviceId(new_id()),
            user_id=actor,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            name=name,
            locale=locale,
            created_at=now,
        )
        async with self._uow() as uow:
            known = await uow.push_devices.find_by_endpoint(endpoint)
            if known is not None:
                device = replace(
                    device,
                    id=known.id,
                    created_at=known.created_at,
                    version=known.version,
                )
                await uow.push_devices.update(device)
            else:
                if len(await uow.push_devices.list_for(actor)) >= MAX_DEVICES:
                    raise ConflictError(because(ReasonCode.PUSH_DEVICES_LIMIT))
                await uow.push_devices.add(device)
            await uow.commit()
        log.info("push device registered", extra={"user_id": str(actor)})
        return device

    async def devices(self, actor: UserId) -> list[PushDevice]:
        async with self._uow() as uow:
            return await uow.push_devices.list_for(actor)

    async def remove(self, actor: UserId, id: PushDeviceId) -> None:
        async with self._uow() as uow:
            await self._own(uow, actor, id)
            await uow.push_devices.remove(id)
            await uow.commit()

    async def test(self, actor: UserId, id: PushDeviceId) -> PushResult:
        """Send the device a test notification now."""
        self._sender_or_off()
        async with self._uow() as uow:
            device = await self._own(uow, actor, id)
        message = PushMessage(
            kind=PushKind.TEST, url="/ui/settings?tab=notifications", tag="lekto-test"
        )
        return await self.deliver(device, message)

    async def send_to(self, user: UserId, message: PushMessage) -> int:
        """Send `message` to every device of `user`; how many push services took it."""
        if self._sender is None:
            return 0
        async with self._uow() as uow:
            devices = await uow.push_devices.list_for(user)
        delivered = 0
        for device in devices:
            result = await self.deliver(device, message)
            delivered += result.outcome is PushOutcome.DELIVERED
        return delivered

    async def deliver(self, device: PushDevice, message: PushMessage) -> PushResult:
        """Send once and record the outcome on the device."""
        sender = self._sender_or_off()
        result = await sender.send(device, message)
        try:
            async with self._uow() as uow:
                current = await uow.push_devices.find(device.id)
                if current is None:
                    return result
                if result.outcome is PushOutcome.DELIVERED:
                    current.last_success_at = self._clock.now()
                    current.failures = 0
                    await uow.push_devices.update(current)
                elif result.outcome is PushOutcome.GONE or current.failures + 1 >= GIVE_UP_AFTER:
                    await uow.push_devices.remove(current.id)
                    log.info("push device forgotten", extra={"status": result.status_code})
                else:
                    current.failures += 1
                    await uow.push_devices.update(current)
                await uow.commit()
        except (ConcurrencyError, NotFoundError):
            pass  # Changed or removed meanwhile: the next delivery records again.
        return result

    def _sender_or_off(self) -> PushSender:
        if self._sender is None:
            raise ConflictError(because(ReasonCode.PUSH_OFF))
        return self._sender

    @staticmethod
    async def _own(uow: UnitOfWork, actor: UserId, id: PushDeviceId) -> PushDevice:
        device = await uow.push_devices.find(id)
        if device is None or device.user_id != actor:
            raise NotFoundError("push device", id)
        return device


def _notice(kind: PushKind, params: JsonObject) -> PushMessage:
    """A notification about one thing: a mailbox, a webhook, jobs."""
    match kind:
        case PushKind.MAILBOX_FAILED:
            url = f"/ui/system/mailboxes/{params.get('mailbox_id', '')}"
        case PushKind.WEBHOOK_DISABLED:
            url = f"/ui/webhooks/{params.get('webhook_id', '')}"
        case PushKind.JOB_FAILED:
            url = "/ui/system?tab=jobs"
        case _:
            url = "/ui/"
    return PushMessage(
        kind=kind, params=params, url=url, tag=f"lekto-{kind.value}", topic=kind.value
    )
