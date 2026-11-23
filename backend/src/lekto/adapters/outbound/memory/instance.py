"""The instance's id, kept with the in-memory database."""

import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from uuid import UUID

from lekto.adapters.outbound.memory.database import Table
from lekto.core.domain.releases import UpdateCheck

if TYPE_CHECKING:
    from lekto.adapters.outbound.memory.unit_of_work import MemoryUnitOfWork


@dataclass
class InstanceRow:
    """The one row of the instance, keyed by its id."""

    id: UUID
    update_check: UpdateCheck | None = None


INSTANCE: Table[InstanceRow] = Table("instance", lambda _: ["the instance"])


class MemoryInstanceRepository:
    def __init__(self, uow: MemoryUnitOfWork) -> None:
        self._uow = uow

    async def id(self) -> UUID:
        rows = self._uow._rows(INSTANCE)
        if rows:
            return rows[0].id
        row = InstanceRow(uuid.uuid4())
        self._uow._write(INSTANCE, row.id, row)
        return row.id

    async def update_check(self) -> UpdateCheck | None:
        rows = self._uow._rows(INSTANCE)
        return rows[0].update_check if rows else None

    async def record_update_check(self, check: UpdateCheck) -> None:
        id = await self.id()
        row = next(row for row in self._uow._rows(INSTANCE) if row.id == id)
        self._uow._write(INSTANCE, id, replace(row, update_check=check))
