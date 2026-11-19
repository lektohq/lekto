"""The instance itself: its stable id (`.knowledge/open/instance-id-fas.md`)."""

from typing import Protocol
from uuid import UUID


class InstanceRepository(Protocol):
    async def id(self) -> UUID:
        """The instance's id: random, made once (revision 0083), kept in the database, so that a
        restore keeps it. Made here in this unit if it is missing; units that make it at the
        same time get the same one."""
        ...
