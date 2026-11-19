"""The instance itself: its stable id (`.knowledge/open/instance-id-fas.md`)."""

from typing import Protocol
from uuid import UUID

from lekto.core.domain.releases import UpdateCheck


class InstanceRepository(Protocol):
    async def id(self) -> UUID:
        """The instance's id: random, made once (revision 0083), kept in the database, so that a
        restore keeps it. Made here in this unit if it is missing; units that make it at the
        same time get the same one."""
        ...

    async def update_check(self) -> UpdateCheck | None:
        """The last look at the releases; None if there was none yet."""
        ...

    async def record_update_check(self, check: UpdateCheck) -> None:
        """Keep `check` as the last look at the releases."""
        ...
