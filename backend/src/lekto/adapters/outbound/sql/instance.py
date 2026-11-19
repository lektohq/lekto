"""The instance's id in its table of one row (`tables.instance`, revision 0083)."""

import uuid
from uuid import UUID

from sqlalchemy import select

from lekto.adapters.outbound.sql import tables as t
from lekto.adapters.outbound.sql.transaction import Transaction

_KEY = 1


class SqlInstanceRepository:
    def __init__(self, transaction: Transaction) -> None:
        self._tx = transaction

    async def id(self) -> UUID:
        found = await self._read()
        if found is not None:
            return found
        # Missing (removed by hand): made now; one made meanwhile by another unit wins.
        statement = self._tx.database.insert(t.instance).values(key=_KEY, id=uuid.uuid4())
        await self._tx.write(statement.on_conflict_do_nothing(index_elements=[t.instance.c.key]))
        made = await self._read()
        assert made is not None
        return made

    async def _read(self) -> UUID | None:
        row = (await self._tx.read(select(t.instance.c.id).where(t.instance.c.key == _KEY))).first()
        return None if row is None else UUID(str(row.id))
