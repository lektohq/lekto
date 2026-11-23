import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from lekto.adapters.outbound.sql import Database, migrate
from tests.sql_fixtures import event_bus_factory, uow_factory, wakeup_factory

__all__ = ["event_bus_factory", "uow_factory", "wakeup_factory"]


@pytest.fixture(scope="session")
def sqlite_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database file migrated once with the real migrations; tests work on copies."""
    import asyncio

    path = tmp_path_factory.mktemp("sqlite") / "template.db"

    async def create() -> None:
        database = Database.sqlite(path)
        try:
            await migrate(database)
        finally:
            await database.dispose()

    asyncio.run(create())
    return path


@pytest.fixture
async def database(sqlite_template: Path, tmp_path: Path) -> AsyncIterator[Database]:
    """A fresh SQLite file in the test's directory (not `:memory:`: units of work need
    connections of their own)."""
    path = tmp_path / "lekto.db"
    shutil.copyfile(sqlite_template, path)
    database = Database.sqlite(path)
    yield database
    await database.dispose()


@pytest.fixture
async def empty_database(tmp_path: Path) -> AsyncIterator[Database]:
    async with _sqlite(tmp_path / "empty.db") as database:
        yield database


@pytest.fixture
async def model_database(tmp_path: Path) -> AsyncIterator[Database]:
    async with _sqlite(tmp_path / "model.db") as database:
        yield database


@asynccontextmanager
async def _sqlite(path: Path) -> AsyncIterator[Database]:
    """A SQLite file not migrated."""
    database = Database.sqlite(path)
    try:
        yield database
    finally:
        await database.dispose()
