"""What the repositories store: entities with an identifier, and a version where they change."""

from typing import Protocol
from uuid import UUID


class Identified[K: UUID](Protocol):
    """What a repository keeps by its `id`."""

    @property
    def id(self) -> K: ...


class Entity[K: UUID](Identified[K], Protocol):
    """An entity that changes: `version` counts its updates for optimistic locking (an update
    checks it and raises it by one). What is only ever inserted (the records of fetched mails,
    the origins of documents) is `Identified` alone (Tobi, 05.11.2026)."""

    version: int
