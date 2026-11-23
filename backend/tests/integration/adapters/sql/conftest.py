"""Postgres for the SQL adapter tests: a database of its own per test session, migrated once
with the real migrations and emptied before every test. Skips if Postgres is not configured or
not reachable; the CI checks that the Postgres run did not skip."""

import asyncio
import secrets
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text

from lekto.adapters.outbound.sql import Database, migrate
from lekto.adapters.outbound.sql.tables import metadata
from lekto.composition.settings import Settings
from tests.integration.services import create_database, drop_database, postgres
from tests.sql_fixtures import event_bus_factory, uow_factory, wakeup_factory

__all__ = ["event_bus_factory", "uow_factory", "wakeup_factory"]


@pytest.fixture
def new_database_names(postgres_settings: Settings) -> Iterator[Callable[[], str]]:
    """Names of databases that do not exist yet; they are dropped after the test."""
    names: list[str] = []

    def new_name() -> str:
        names.append(f"{postgres_settings.db_name}_test_{secrets.token_hex(4)}")
        return names[-1]

    yield new_name
    for name in names:
        asyncio.run(drop_database(postgres_settings, name))


@pytest.fixture(scope="session")
def test_database_name(postgres_settings: Settings) -> Iterator[str]:
    name = f"{postgres_settings.db_name}_test_{secrets.token_hex(4)}"

    async def create() -> None:
        await create_database(postgres_settings, name)
        database = postgres(postgres_settings, name)
        try:
            await migrate(database)
        finally:
            await database.dispose()

    asyncio.run(create())
    yield name
    asyncio.run(drop_database(postgres_settings, name))


@pytest.fixture
async def database(postgres_settings: Settings, test_database_name: str) -> AsyncIterator[Database]:
    database = postgres(postgres_settings, test_database_name)
    names = ", ".join(table.name for table in metadata.sorted_tables)
    async with database.engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield database
    await database.dispose()


@pytest.fixture
async def empty_database(
    postgres_settings: Settings, new_database_names: Callable[[], str]
) -> AsyncIterator[Database]:
    async with _new_database(postgres_settings, new_database_names()) as database:
        yield database


@pytest.fixture
async def model_database(
    postgres_settings: Settings, new_database_names: Callable[[], str]
) -> AsyncIterator[Database]:
    async with _new_database(postgres_settings, new_database_names()) as database:
        yield database


@asynccontextmanager
async def _new_database(settings: Settings, name: str) -> AsyncIterator[Database]:
    """A database created empty (`new_database_names` drops it)."""
    await create_database(settings, name)
    database = postgres(settings, name)
    try:
        yield database
    finally:
        await database.dispose()
