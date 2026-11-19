"""In-memory identity repositories, on the tables of the in-memory unit of work."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from lekto.adapters.outbound.memory.database import Table
from lekto.adapters.outbound.memory.rows import MemoryRepository, MemoryRows, _copy
from lekto.core.domain.identity import (
    ApiToken,
    Credential,
    ExternalIdentity,
    KnownDevice,
    LoginFailures,
    Session,
    ThrottleRule,
    failure_id,
)
from lekto.core.domain.ids import (
    ApiTokenId,
    ExternalIdentityId,
    KnownDeviceId,
    SessionId,
    UserId,
)

if TYPE_CHECKING:
    from lekto.adapters.outbound.memory.unit_of_work import MemoryUnitOfWork


class MemoryCredentialRepository(MemoryRepository[UserId, Credential]):
    async def remove(self, user: UserId) -> None:
        self._remove_rows([row for row in self._all() if row.user_id == user])


class MemorySessionRepository(MemoryRows[SessionId, Session]):
    async def find_by_token(self, token_hash: str) -> Session | None:
        return next((_copy(row) for row in self._all() if row.token_hash == token_hash), None)

    async def touch(self, id: SessionId, last_seen_at: datetime) -> None:
        self._touch(id, "last_seen_at", last_seen_at)

    async def remove(self, id: SessionId) -> None:
        self._remove_rows([row for row in self._all() if row.id == id])

    async def remove_for_user(self, user: UserId, *, keep: SessionId | None = None) -> int:
        return self._remove_rows(
            [row for row in self._all() if row.user_id == user and row.id != keep]
        )

    async def purge(self, *, now: datetime, idle_before: datetime) -> int:
        return self._remove_rows(
            [row for row in self._all() if row.expires_at <= now or row.last_seen_at <= idle_before]
        )


class MemoryApiTokenRepository(MemoryRows[ApiTokenId, ApiToken]):
    async def find_by_token(self, token_hash: str) -> ApiToken | None:
        return next((_copy(row) for row in self._all() if row.token_hash == token_hash), None)

    async def list_for(self, user: UserId) -> list[ApiToken]:
        rows = [row for row in self._all() if row.user_id == user]
        return [_copy(row) for row in sorted(rows, key=lambda row: (row.created_at, row.id))]

    async def touch(self, id: ApiTokenId, last_used_at: datetime) -> None:
        self._touch(id, "last_used_at", last_used_at)

    async def remove(self, id: ApiTokenId) -> None:
        self._remove_rows([row for row in self._all() if row.id == id])

    async def remove_for_user(self, user: UserId) -> int:
        return self._remove_rows([row for row in self._all() if row.user_id == user])


class MemoryKnownDeviceRepository(MemoryRows[KnownDeviceId, KnownDevice]):
    async def find_by_token(self, token_hash: str) -> KnownDevice | None:
        return next((_copy(row) for row in self._all() if row.token_hash == token_hash), None)

    async def renew(self, id: KnownDeviceId, expires_at: datetime) -> None:
        self._touch(id, "expires_at", expires_at)

    async def remove_for_user(self, user: UserId) -> int:
        return self._remove_rows([row for row in self._all() if row.user_id == user])

    async def keep_newest(self, user: UserId, count: int) -> int:
        rows = sorted(
            (row for row in self._all() if row.user_id == user),
            key=lambda row: (row.created_at, row.id),
            reverse=True,
        )
        return self._remove_rows(rows[count:])

    async def purge(self, *, now: datetime) -> int:
        return self._remove_rows([row for row in self._all() if row.expires_at <= now])


class MemoryExternalIdentityRepository:
    def __init__(self, uow: "MemoryUnitOfWork", table: Table[ExternalIdentity]) -> None:
        self._rows = MemoryRows[ExternalIdentityId, ExternalIdentity](uow, table)

    async def add(self, identity: ExternalIdentity) -> None:
        await self._rows.add(identity)

    async def find(self, issuer: str, subject: str) -> ExternalIdentity | None:
        return next(
            (
                _copy(row)
                for row in self._rows._all()
                if row.issuer == issuer and row.subject == subject
            ),
            None,
        )

    async def list_for(self, user: UserId) -> list[ExternalIdentity]:
        rows = [row for row in self._rows._all() if row.user_id == user]
        return [_copy(row) for row in sorted(rows, key=lambda row: (row.created_at, row.id))]

    async def remove_for_user(self, user: UserId) -> int:
        return self._rows._remove_rows([row for row in self._rows._all() if row.user_id == user])


class MemoryLoginFailureRepository:
    """Atomic, since nothing in a call waits for anything else."""

    def __init__(self, uow: "MemoryUnitOfWork", table: Table[LoginFailures]) -> None:
        self._rows = MemoryRows[UUID, LoginFailures](uow, table)

    async def find(self, key: str) -> LoginFailures | None:
        return await self._rows.find(failure_id(key))

    async def reserve(self, key: str, rule: ThrottleRule, now: datetime) -> timedelta | None:
        """Count an attempt before it is checked, and block as if it fails: so attempts that
        arrive together cannot all pass. If blocked, count nothing and return how long."""
        failures = await self.find(key)
        new = failures is None
        if failures is None:
            failures = LoginFailures(key=key, failures=0, first_failure_at=now)
        elif failures.blocked_until is not None and failures.blocked_until > now:
            return failures.blocked_until - now
        if now - failures.first_failure_at >= rule.window:
            failures.failures, failures.first_failure_at = 0, now
        failures.failures += 1
        block = rule.block(failures.failures)
        failures.blocked_until = None if block is None else now + block
        await (self._rows.add if new else self._rows._replace)(failures)
        return None

    async def release(self, key: str, rule: ThrottleRule) -> None:
        """Take back a reserved attempt that did not fail."""
        failures = await self.find(key)
        if failures is not None:
            failures.failures = max(0, failures.failures - 1)
            if rule.block(failures.failures) is None:
                failures.blocked_until = None
            await self._rows._replace(failures)

    async def remove(self, key: str) -> None:
        self._rows._remove_rows([row for row in self._rows._all() if row.key == key])

    async def purge(self, *, before: datetime) -> int:
        return self._rows._remove_rows(
            [
                row
                for row in self._rows._all()
                if row.first_failure_at < before
                and (row.blocked_until is None or row.blocked_until < before)
            ]
        )
