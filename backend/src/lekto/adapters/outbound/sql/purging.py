"""Deleting what a `purge` removes in batches: a migration leaves more than a million done jobs
and as many events, and one statement for them all could outlast `COMMAND_TIMEOUT` on slow
hardware; the cleanup then failed again at every interval (SQ-K07). A statement removes at most
`PURGE_BATCH` rows, all of them in the caller's transaction."""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import ColumnElement, CursorResult, Executable, Table, delete, select, tuple_

PURGE_BATCH = 10_000
"""Rows one statement of a purge removes at most: some ten milliseconds of a fast database, a
second or so of a slow one."""

type Execute = Callable[[Executable], Awaitable[CursorResult[Any]]]


async def delete_in_batches(execute: Execute, table: Table, *where: ColumnElement[bool]) -> int:
    """Delete the rows of `table` that match `where` with `execute`, `PURGE_BATCH` at a time
    (chosen by the primary key); how many were deleted."""
    keys = list(table.primary_key.columns)
    key = keys[0] if len(keys) == 1 else tuple_(*keys)
    deleted = 0
    while True:
        # Not correlated with the DELETE: the batch is chosen from the table itself.
        chosen = select(*keys).where(*where).limit(PURGE_BATCH).correlate(None)
        count = int((await execute(delete(table).where(key.in_(chosen)))).rowcount)
        deleted += count
        if count < PURGE_BATCH:
            return deleted
