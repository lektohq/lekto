"""Notifications (web push; Tobi, 06.11.2026): a document that comes to wait is told after a
quiet, many in one; what a person switched off is not told; a job given up reaches the admins."""

import itertools

from lekto.adapters.outbound.memory import FakePushSender
from lekto.adapters.outbound.memory.push import FAKE_PUBLIC_KEY
from lekto.core.domain.documents import Document
from lekto.core.domain.events import ReviewRequired
from lekto.core.domain.jobs import Job
from lekto.core.domain.pipeline import Node
from lekto.core.domain.push import PushKind, PushMessage
from lekto.core.domain.users import Role, User
from lekto.core.services._jobs import JobRunner
from lekto.core.services._push_queue import PUSH_DELAY, PUSH_JOB
from lekto.core.services.push import PushService
from tests import builders
from tests.builders import UNCERTAIN, Returns, incoming
from tests.contracts.push import AUTH
from tests.unit.services.support import World

_numbers = itertools.count()


def push(world: World, sender: FakePushSender) -> PushService:
    return PushService(world.uow, world.clock, sender, world.inbox, links=builders.LINKS)


async def with_device(world: World, service: PushService, user: User, number: int = 0) -> None:
    await service.register(
        user.id,
        endpoint=f"https://web.push.apple.com/device-{user.username}-{number}",
        p256dh=FAKE_PUBLIC_KEY,
        auth=AUTH,
        name="iPhone",
        locale="de",
    )


async def waiting(world: World, service: PushService, owner: User) -> Document:
    """A document of `owner` that comes to wait (yellow); the push service hears of it."""
    pipeline = world.pipeline({Node.JUDGE: Returns(UNCERTAIN)})
    content = f"%PDF-1.7 {next(_numbers)}".encode()
    received = await pipeline.receive(owner.id, incoming(content), filename="a.pdf")
    await world.drain(pipeline)
    for event in world.events():
        if isinstance(event, ReviewRequired) and event.document_id == received.id:
            await service.on_event(event)
    return await world.documents.get(owner.id, received.id)


async def told(world: World, service: PushService, sender: FakePushSender) -> list[PushMessage]:
    """Run what is due after the quiet; the messages sent meanwhile."""
    before = len(sender.sent)
    world.clock.advance(PUSH_DELAY)
    while await service.run_next_job():
        pass
    return [message for _, message in sender.sent[before:]]


async def test_a_document_that_comes_to_wait_is_told_after_the_quiet(world: World) -> None:
    sender = FakePushSender()
    service = push(world, sender)
    owner = await world.user()
    await with_device(world, service, owner)
    document = await waiting(world, service, owner)
    assert not await service.run_next_job()  # the quiet first
    (message,) = await told(world, service, sender)
    assert message.kind is PushKind.WAITING
    assert message.params == {"count": 1, "new": 1, "titles": [document.title]}
    assert message.url == f"/ui/documents/{document.id}"
    assert message.badge == 1
    assert await told(world, service, sender) == []  # nothing new since


async def test_many_go_into_one_and_titles_can_stay_off_the_screen(world: World) -> None:
    sender = FakePushSender()
    service = push(world, sender)
    owner = await world.user()
    await with_device(world, service, owner)
    await service.set_preferences(owner.id, kinds=frozenset({PushKind.WAITING}), titles=False)
    for _ in range(4):
        await waiting(world, service, owner)
    (message,) = await told(world, service, sender)
    assert message.params == {"count": 4, "new": 4, "titles": []}
    assert message.url == "/ui/inbox"


async def test_nobody_is_told_who_switched_it_off_or_has_no_device(world: World) -> None:
    sender = FakePushSender()
    service = push(world, sender)
    quiet, deviceless = await world.user(), await world.user()
    await with_device(world, service, quiet)
    await service.set_preferences(quiet.id, kinds=frozenset(), titles=True)
    await waiting(world, service, quiet)
    await waiting(world, service, deviceless)
    assert await told(world, service, sender) == []
    assert [j for j in world.database.jobs.values() if j.kind == PUSH_JOB] == []


async def test_a_document_confirmed_meanwhile_is_not_told(world: World) -> None:
    sender = FakePushSender()
    service = push(world, sender)
    owner = await world.user()
    await with_device(world, service, owner)
    document = await waiting(world, service, owner)
    await world.inbox.mark_seen(owner.id, document.id)
    await world.documents.delete(owner.id, document.id)
    assert await told(world, service, sender) == []


async def test_a_given_up_job_reaches_the_admins_but_not_a_notifications_own(
    world: World,
) -> None:
    admin = await world.user(role=Role.ADMIN)
    await world.user()
    runner = JobRunner(world.uow, world.clock)

    async def give_up(kind: str) -> None:
        async with world.uow() as uow:
            await uow.jobs.enqueue(kind, {}, run_at=world.clock.now())
            await uow.commit()

        async def fail(job: Job) -> None:
            await runner.again(job, "broken", None)

        assert await runner.run_next([kind], PUSH_DELAY, fail)

    await give_up("logo")
    await give_up(PUSH_JOB)
    notices = [
        (j.payload["user_id"], j.payload["kind"], j.payload["params"])
        for j in world.database.jobs.values()
        if j.kind == PUSH_JOB and j.payload.get("kind") == "job_failed"
    ]
    assert notices == [(str(admin.id), "job_failed", {"kind": "logo"})]


async def test_a_notice_names_what_it_is_about(world: World) -> None:
    sender = FakePushSender()
    service = push(world, sender)
    admin = await world.user(role=Role.ADMIN)
    await with_device(world, service, admin)
    async with world.uow() as uow:
        from lekto.core.services._push_queue import queue_push

        await queue_push(
            uow,
            world.clock.now(),
            [admin.id],
            PushKind.MAILBOX_FAILED,
            {"mailbox_id": "m-1", "name": "Rechnungen"},
        )
        await uow.commit()
    (message,) = await told(world, service, sender)
    assert (message.kind, message.params, message.url) == (
        PushKind.MAILBOX_FAILED,
        {"mailbox_id": "m-1", "name": "Rechnungen"},
        "/ui/system/mailboxes/m-1",
    )
