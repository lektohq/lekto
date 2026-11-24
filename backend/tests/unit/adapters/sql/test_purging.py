"""A purge deletes in batches, so that no statement outlasts the statement timeout after a
migration left a million rows (SQ-K07)."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, event, insert, select

from lekto.adapters.outbound.sql import Database, purging
from lekto.adapters.outbound.sql.purging import delete_in_batches
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from tests.builders import NOW
from tests.contracts.event_bus import FAR_FUTURE, EventBusFactory, Recorder, publish, received
from tests.contracts.job_queue import LEASE, claim, enqueue


@pytest.fixture(autouse=True)
def small_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(purging, "PURGE_BATCH", 2)


@contextmanager
def deletes(database: Database) -> Iterator[list[int]]:
    """The rows each DELETE statement on `database` removed, in order."""
    counts: list[int] = []

    def counted(_conn: Any, cursor: Any, statement: str, *_args: Any) -> None:
        if statement.lstrip().upper().startswith("DELETE"):
            counts.append(cursor.rowcount)

    engine = database.engine.sync_engine
    event.listen(engine, "after_cursor_execute", counted)
    try:
        yield counts
    finally:
        event.remove(engine, "after_cursor_execute", counted)


async def test_done_jobs_are_purged_in_batches(
    database: Database, uow_factory: UnitOfWorkFactory
) -> None:
    for _ in range(5):
        await enqueue(uow_factory)
    claimed = [await claim(uow_factory, at=LEASE) for _ in range(5)]
    async with uow_factory() as uow:
        for job in claimed:
            assert job is not None
            await uow.jobs.complete(job, now=NOW)
        await uow.commit()

    with deletes(database) as counts:
        async with uow_factory() as uow:
            assert await uow.jobs.purge(before=NOW + LEASE) == 5
            await uow.commit()
    assert counts == [2, 2, 1]


async def test_handled_events_are_purged_in_batches(
    database: Database, uow_factory: UnitOfWorkFactory, event_bus_factory: EventBusFactory
) -> None:
    bus = event_bus_factory()
    bus.subscribe("index", Recorder())
    await bus.dispatch()  # creates the subscription
    await publish(uow_factory, *(received(n) for n in range(4)))
    await bus.dispatch()

    with deletes(database) as counts:
        assert await bus.purge(before=FAR_FUTURE) == 4
    assert counts == [2, 2, 0]


async def test_a_table_with_a_key_of_two_columns_is_purged_in_batches(
    empty_database: Database,
) -> None:
    pairs = Table(
        "pairs",
        MetaData(),
        Column("a", Integer, primary_key=True),
        Column("b", Integer, primary_key=True),
        Column("old", Integer, nullable=False),
    )
    async with empty_database.engine.begin() as connection:
        await connection.run_sync(pairs.metadata.create_all)
        rows = [{"a": a, "b": b, "old": a < 2} for a in range(3) for b in range(3)]
        await connection.execute(insert(pairs), rows)
        removed = await delete_in_batches(connection.execute, pairs, pairs.c.old == 1)
        left = (await connection.execute(select(pairs.c.a, pairs.c.b))).all()
    assert removed == 6
    assert sorted(left) == [(2, 0), (2, 1), (2, 2)]
