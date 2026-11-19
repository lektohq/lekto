"""The worker looks for a newer Lekto shortly after it starts and then every hour; the last look
is kept with the instance (`.knowledge/open/update-notifier-fas.md`)."""

import logging
from datetime import timedelta

import pytest

from lekto.adapters.outbound.memory.releases import FakeReleaseFeed
from lekto.core.domain.releases import Release
from lekto.core.domain.rights import Actor
from lekto.core.services.updates import FIRST_LOOK, UpdateService
from tests import builders
from tests.unit.services.support import World

HOUR = timedelta(hours=1)


def release(version: str) -> Release:
    return Release(
        version=version,
        published_at=builders.NOW - HOUR,
        url=f"https://github.com/lektohq/lekto/releases/tag/v{version}",
    )


def service(world: World, feed: FakeReleaseFeed | None, running: str = "0.15.6") -> UpdateService:
    return UpdateService(world.uow, world.clock, feed, running=running)


async def test_it_looks_shortly_after_the_start_and_then_every_hour(world: World) -> None:
    feed = FakeReleaseFeed([release("0.15.6"), release("0.16.0")])
    updates = service(world, feed)
    user = Actor((await world.user()).id)
    assert (await updates.status(user)).checked_at is None

    await updates.schedule()
    await updates.schedule()  # once queued, not twice
    assert await builders.drain(updates) == 0  # not at once
    world.clock.advance(FIRST_LOOK)
    assert await builders.drain(updates) == 1
    status = await updates.status(user)
    assert status.checking and status.update_available
    assert status.latest == release("0.16.0")
    assert status.checked_at == builders.NOW + FIRST_LOOK

    feed.releases_given.append(release("0.17.0"))
    world.clock.advance(HOUR - timedelta(seconds=1))
    assert await builders.drain(updates) == 0
    world.clock.advance(timedelta(seconds=1))
    assert await builders.drain(updates) == 1
    assert (await updates.status(user)).latest == release("0.17.0")
    assert feed.asked == 2


async def test_a_failed_look_keeps_the_last_and_comes_again(
    world: World, caplog: pytest.LogCaptureFixture
) -> None:
    feed = FakeReleaseFeed([release("0.16.0")])
    updates = service(world, feed)
    user = Actor((await world.user()).id)
    await updates.schedule()
    world.clock.advance(FIRST_LOOK)
    await builders.drain(updates)
    first = await updates.status(user)

    feed.error = "cannot connect"
    world.clock.advance(HOUR)
    with caplog.at_level(logging.WARNING):
        assert await builders.drain(updates) == 1
    assert "cannot look for a newer Lekto" in caplog.text
    assert await updates.status(user) == first

    feed.error = None
    world.clock.advance(HOUR)
    assert await builders.drain(updates) == 1  # the next look as planned
    assert feed.asked == 3


async def test_turned_off_or_in_development_it_never_looks(world: World) -> None:
    feed = FakeReleaseFeed([release("0.16.0")])
    user = Actor((await world.user()).id)
    for updates in (service(world, None), service(world, feed, running="0.0.0.dev0")):
        await updates.schedule()
        world.clock.advance(FIRST_LOOK)
        assert await builders.drain(updates) == 0
        status = await updates.status(user)
        assert not status.checking and not status.update_available
    assert feed.asked == 0


async def test_once_updated_the_latest_is_no_news(world: World) -> None:
    feed = FakeReleaseFeed([release("0.16.0")])
    await service(world, feed).schedule()
    world.clock.advance(FIRST_LOOK)
    await builders.drain(service(world, feed))
    user = Actor((await world.user()).id)
    status = await service(world, feed, running="0.16.0").status(user)
    assert status.latest == release("0.16.0") and not status.update_available
