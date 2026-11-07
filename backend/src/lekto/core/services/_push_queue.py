"""Queueing a notification (web push), for every service that has something to tell: the push
service sends it (`services.push`)."""

from collections.abc import Iterable
from datetime import datetime, timedelta

from lekto.core.domain.ids import UserId
from lekto.core.domain.json_value import JsonObject
from lekto.core.domain.push import PushKind
from lekto.core.ports.unit_of_work import UnitOfWork

PUSH_JOB = "push.send"
"""A notification for one person and one kind, sent `PUSH_DELAY` after what caused it."""

PUSH_DELAY = timedelta(seconds=60)
"""The quiet before a notification: what comes meanwhile goes into the same one (Tobi,
06.11.2026)."""


async def queue_push(
    uow: UnitOfWork,
    now: datetime,
    users: Iterable[UserId],
    kind: PushKind,
    params: JsonObject | None = None,
) -> None:
    """Queue a notification of `kind` for each of `users`, due after the quiet; one queued for
    the same person and kind takes it in (the first one's `params` stay)."""
    for user in users:
        await uow.jobs.enqueue(
            PUSH_JOB,
            {"user_id": str(user), "kind": kind.value, "params": params or {}},
            run_at=now + PUSH_DELAY,
            coalesce_key=f"push:{kind.value}:{user}",
        )


async def active_admins(uow: UnitOfWork) -> list[UserId]:
    """Whom notifications about mailboxes and jobs go to."""
    return [user.id for user in await uow.users.list_all() if user.is_active_admin]
