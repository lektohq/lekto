"""What an error of the database tells: not the values of the statement, which may be private
(a token's hash, an alias, an IBAN), in no message, chain or traceback (SQ-05)."""

import traceback
from dataclasses import replace

import pytest
import sqlalchemy as sa

from lekto.adapters.outbound.sql import Database
from lekto.core.domain.errors import ConflictError
from lekto.core.domain.ids import SessionId, new_id
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from tests.contracts.identity import a_session
from tests.contracts.unit_of_work import a_user


async def test_a_conflict_carries_no_values(uow_factory: UnitOfWorkFactory) -> None:
    session = a_session(await a_user(uow_factory))
    async with uow_factory() as uow:
        await uow.sessions.add(session)
        await uow.commit()
    twin = replace(session, id=SessionId(new_id()))  # the same token's hash
    with pytest.raises(ConflictError) as raised:
        async with uow_factory() as uow:
            await uow.sessions.add(twin)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__
    told = "".join(traceback.format_exception(raised.value))
    assert session.token_hash not in told


async def test_another_error_of_the_database_hides_its_parameters(database: Database) -> None:
    with pytest.raises(sa.exc.DBAPIError) as raised:
        async with database.writing() as connection:
            await connection.execute(
                sa.text("INSERT INTO nowhere VALUES (:x)"), {"x": "IBAN-12345"}
            )
    assert "IBAN-12345" not in str(raised.value)
