"""The configured database: SQLite or Postgres, per `LEKTO_DB_TYPE`."""

import asyncio
import logging
import ssl
import time
from pathlib import Path

from lekto.adapters.outbound.sql import Database, SchemaState, migrate, schema_state
from lekto.adapters.outbound.sql.database import Tls
from lekto.composition.settings import Settings


def open_database(settings: Settings, *, read_only: bool = False) -> Database:
    """The configured database; `read_only` opens a SQLite file read-only (the schema check,
    which must not write while another process migrates)."""
    if settings.db_type == "sqlite":
        return Database.sqlite(settings.db_sqlite_path, read_only=read_only)
    # Settings guarantee these for postgres.
    assert settings.db_host and settings.db_name and settings.db_user and settings.db_password
    return Database.postgres(
        host=settings.db_host,
        port=settings.db_port,
        name=settings.db_name,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        tls=tls_of(settings.db_sslmode, settings.db_sslrootcert),
    )


def tls_of(mode: str | None, root_certificate: Path | None) -> Tls:
    """How Postgres connections use TLS, by `LEKTO_DB_SSLMODE` (libpq's modes). Unset leaves
    asyncpg's default, which honours `PGSSLMODE`. The checking modes trust the root certificate
    given, else the system's."""
    match mode:
        case None:
            return None
        case "disable":
            return False
        case "verify-ca" | "verify-full":
            context = ssl.create_default_context(
                cafile=None if root_certificate is None else str(root_certificate)
            )
            # verify-ca: a certificate of a trusted authority, for any host name.
            context.check_hostname = mode == "verify-full"
            return context
        case _:
            return mode  # allow, prefer, require: asyncpg checks no certificate


async def migrate_database(settings: Settings) -> None:
    """Bring the configured database to the newest schema."""
    database = open_database(settings)
    try:
        await migrate(database)
    finally:
        await database.dispose()


# Seconds between two looks at the schema, and between two messages while waiting.
SCHEMA_POLL_INTERVAL = 2.0
SCHEMA_REPORT_INTERVAL = 60.0

log = logging.getLogger(__name__)


async def check_schema(settings: Settings, *, wait: float = 0) -> SchemaState:
    """The schema's state; with `wait` seconds, keep looking while it is `outdated` or the
    database is not reachable yet (the API of another container may still be migrating). A
    database that is `newer` than this version never becomes right and is returned at once.
    It only reads: a SQLite file is opened read-only (`Database.sqlite`)."""
    database = open_database(settings, read_only=True)
    deadline = time.monotonic() + wait
    next_report = 0.0
    try:
        while True:
            problem: str | None = None
            try:
                state = await schema_state(database)
            except Exception as error:
                state, problem = "outdated", f"database not reachable: {error!r}"
            if state != "outdated" or time.monotonic() >= deadline:
                if problem:
                    log.error(problem)
                return state
            if time.monotonic() >= next_report:
                log.warning(problem or "waiting for the database schema to be migrated")
                next_report = time.monotonic() + SCHEMA_REPORT_INTERVAL
            await asyncio.sleep(SCHEMA_POLL_INTERVAL)
    finally:
        await database.dispose()
