"""The instance's id in its table of one row (`tables.instance`, revision 0083)."""

import uuid
from uuid import UUID

from sqlalchemy import select, update

from lekto.adapters.outbound.sql import tables as t
from lekto.adapters.outbound.sql.transaction import Transaction
from lekto.core.domain.releases import Release, UpdateCheck
from lekto.core.ports.instance import InstanceRepository

_KEY = 1


class SqlInstanceRepository(InstanceRepository):
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

    async def update_check(self) -> UpdateCheck | None:
        table = t.instance
        row = (await self._tx.read(select(table).where(table.c.key == _KEY))).first()
        if row is None or row.update_checked_at is None:
            return None
        latest = None
        if row.latest_version is not None:
            latest = Release(
                version=row.latest_version,
                published_at=row.latest_published_at,
                url=row.latest_url,
            )
        return UpdateCheck(checked_at=row.update_checked_at, latest=latest)

    async def record_update_check(self, check: UpdateCheck) -> None:
        await self.id()  # the row, made if it is missing
        latest = check.latest
        await self._tx.write(
            update(t.instance)
            .where(t.instance.c.key == _KEY)
            .values(
                update_checked_at=check.checked_at,
                latest_version=None if latest is None else latest.version,
                latest_published_at=None if latest is None else latest.published_at,
                latest_url=None if latest is None else latest.url,
            )
        )
