"""Whether a newer Lekto is out (Tobi, 19.11.2026, `.knowledge/open/update-notifier-fas.md`).

The worker asks the release feed shortly after it starts and then every `interval` (an hour),
and keeps in the row of the instance when it asked and the newest release that was news to the
running version. A failure is a warning in the log; the next look comes as planned. Turned off
(`LEKTO_UPDATE_CHECK=false`) or in a development state it never asks.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from lekto.core.domain.errors import ConcurrencyError
from lekto.core.domain.jobs import Job
from lekto.core.domain.releases import Release, UpdateCheck, is_development, newest_for
from lekto.core.domain.releases import update_available as newer
from lekto.core.domain.rights import Actor
from lekto.core.ports.clock import Clock
from lekto.core.ports.releases import ReleaseFeed, ReleaseFeedError
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from lekto.core.services._access import load_actor
from lekto.core.services._jobs import LEASE, JobRunner, lost

log = logging.getLogger(__name__)

UPDATE_CHECK_JOB = "updates.check"
FIRST_LOOK = timedelta(minutes=1)
"""How long after the worker's start the first look comes (not in the middle of its start)."""


@dataclass(frozen=True, kw_only=True)
class UpdateStatus:
    """The running version and what the last look found."""

    running: str
    checking: bool  # whether this instance looks at all
    checked_at: datetime | None
    latest: Release | None
    update_available: bool


class UpdateService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        feed: ReleaseFeed | None,
        *,
        running: str,
        interval: timedelta = timedelta(hours=1),
    ) -> None:
        """`feed`: None when the look is turned off; `running`: the version of this Lekto."""
        self._uow = uow
        self._clock = clock
        self._feed = feed
        self._running = running
        self._interval = interval
        self._jobs = JobRunner(uow, clock)

    @property
    def job_kinds(self) -> tuple[str, ...]:
        """The kinds of jobs `run_next_job` runs: none while it does not look."""
        return (UPDATE_CHECK_JOB,) if self.checking else ()

    @property
    def checking(self) -> bool:
        """Whether this instance looks for releases: turned on, and a release itself."""
        return self._feed is not None and not is_development(self._running)

    async def schedule(self) -> None:
        """Make sure a look is queued, shortly after now unless one is queued already."""
        if not self.checking:
            return
        async with self._uow() as uow:
            run_at = self._clock.now() + FIRST_LOOK
            await uow.jobs.enqueue(UPDATE_CHECK_JOB, {}, run_at=run_at, dedup_key=UPDATE_CHECK_JOB)
            await uow.commit()

    async def run_next_job(self) -> bool:
        """Run a due look at the releases. Returns False if none was due."""
        if not self.checking:
            return False
        return await self._jobs.run_next(self.job_kinds, LEASE, self._run)

    async def _run(self, job: Job) -> None:
        assert self._feed is not None
        now = self._clock.now()
        check: UpdateCheck | None = None
        try:
            releases = await self._feed.releases()
            check = UpdateCheck(checked_at=now, latest=newest_for(self._running, releases))
        except ReleaseFeedError as error:
            log.warning("cannot look for a newer Lekto", extra={"error": str(error)})
        try:
            async with self._uow() as uow:
                if check is not None:
                    await uow.instance.record_update_check(check)
                await uow.jobs.complete(job, now=now)
                await uow.jobs.enqueue(
                    UPDATE_CHECK_JOB, {}, run_at=now + self._interval, dedup_key=UPDATE_CHECK_JOB
                )
                await uow.commit()
        except ConcurrencyError:
            lost(job)
            return
        if check is not None and check.latest is not None:
            log.info("a newer Lekto is out", extra={"version": check.latest.version})

    async def status(self, actor: Actor) -> UpdateStatus:
        """The running version and the last look, for every caller."""
        async with self._uow() as uow:
            await load_actor(uow, actor)
            last = await uow.instance.update_check()
        latest = None if last is None else last.latest
        return UpdateStatus(
            running=self._running,
            checking=self.checking,
            checked_at=None if last is None else last.checked_at,
            latest=latest,
            update_available=newer(self._running, latest),
        )
