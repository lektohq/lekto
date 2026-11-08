"""`LEKTO_DB_SSLMODE` reaches the connections: the Postgres of the devcontainer and CI speaks
no TLS, so a mode that does not insist connects and one that does is refused."""

import pytest
from sqlalchemy import text

from lekto.adapters.outbound.sql import Database
from lekto.composition.database import tls_of
from lekto.composition.settings import Settings


def _database(settings: Settings, mode: str) -> Database:
    assert settings.db_host and settings.db_name and settings.db_user and settings.db_password
    return Database.postgres(
        host=settings.db_host,
        port=settings.db_port,
        name=settings.db_name,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        tls=tls_of(mode, None),
    )


@pytest.mark.parametrize("mode", ["disable", "prefer"])
async def test_a_mode_that_does_not_insist_connects(postgres_settings: Settings, mode: str) -> None:
    database = _database(postgres_settings, mode)
    try:
        async with database.engine.connect() as connection:
            assert (await connection.execute(text("SELECT 1"))).scalar() == 1
        listener = await database.connect_raw()
        await listener.close()
    finally:
        await database.dispose()


@pytest.mark.parametrize("mode", ["require", "verify-full"])
async def test_a_mode_that_insists_is_refused_without_tls(
    postgres_settings: Settings, mode: str
) -> None:
    database = _database(postgres_settings, mode)
    try:
        with pytest.raises(Exception, match=r"(?i)ssl|tls"):
            async with database.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        with pytest.raises(Exception, match=r"(?i)ssl|tls"):
            await database.connect_raw()
    finally:
        await database.dispose()
