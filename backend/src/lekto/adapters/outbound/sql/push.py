"""The devices of web push in SQL."""

from typing import Any

from sqlalchemy import Row, delete, select

from lekto.adapters.outbound.sql import tables as t
from lekto.adapters.outbound.sql.repositories import SqlRepository, Values
from lekto.core.domain.ids import PushDeviceId, UserId
from lekto.core.domain.push import PushDevice


class SqlPushDeviceRepository(SqlRepository[PushDeviceId, PushDevice]):
    kind = "push device"
    table = t.push_devices

    async def find_by_endpoint(self, endpoint: str) -> PushDevice | None:
        found = await self._load(self.table.c.endpoint == endpoint)
        return found[0] if found else None

    async def list_for(self, user: UserId) -> list[PushDevice]:
        rows = await self._tx.read(
            select(self.table)
            .where(self.table.c.user_id == user)
            .order_by(self.table.c.created_at, self.table.c.id)
        )
        return await self._entities(rows.all())

    async def remove_for_user(self, user: UserId) -> int:
        result = await self._tx.write(delete(self.table).where(self.table.c.user_id == user))
        return result.rowcount

    def _values(self, entity: PushDevice) -> Values:
        return {
            "id": entity.id,
            "user_id": entity.user_id,
            "endpoint": entity.endpoint,
            "p256dh": entity.p256dh,
            "auth": entity.auth,
            "name": entity.name,
            "locale": entity.locale,
            "created_at": entity.created_at,
            "last_success_at": entity.last_success_at,
            "failures": entity.failures,
            "version": entity.version,
        }

    def _entity(self, row: Row[Any]) -> PushDevice:
        return PushDevice(
            id=PushDeviceId(row.id),
            user_id=UserId(row.user_id),
            endpoint=row.endpoint,
            p256dh=row.p256dh,
            auth=row.auth,
            name=row.name,
            locale=row.locale,
            created_at=row.created_at,
            last_success_at=row.last_success_at,
            failures=row.failures,
            version=row.version,
        )
