"""What aligning a migrated document stands on, the same for `check` and `run` (MI-09): Lekto's
tags with their parents and fields with their types, what the plan wants of a document, what
the migration set on it last, and whether a document a duplicate upload hit is this one's."""

from typing import Any

from lekto_migration.align import Alignment, align, current, foreign, uploaded
from lekto_migration.expect import Expected
from lekto_migration.lekto import Lekto
from lekto_migration.resolve import Resolved, space_of
from lekto_migration.session import Loaded
from lekto_migration.state import State


class Basis:
    def __init__(self, loaded: Loaded, state: State, target: Lekto | None) -> None:
        self._loaded = loaded
        self._state = state
        self._target = target
        directory = loaded.directory
        self._parents = {
            str(tag["id"]): tag.get("parent_id") for tag in directory.tags["document"].values()
        }
        self._types = {str(f["id"]): str(f.get("data_type")) for f in directory.fields.values()}

    def want(self, resolved: Resolved) -> dict[str, Any]:
        """What the plan wants of the document, in the space it goes to."""
        return {**resolved.values, "space_id": space_of(resolved, self._loaded.directory)}

    def foreign(
        self, item: Expected, lekto_id: str, details: dict[str, Any], resolved: Resolved
    ) -> str | None:
        """Why a document a duplicate upload of `item` hit is not to be aligned with it:
        another Paperless document's, or outside the planned space (`align.foreign`)."""
        target = space_of(resolved, self._loaded.directory)
        return foreign(self._state.claimant(lekto_id, item.id), details.get("space_id"), target)

    async def baseline(
        self, lekto_id: str, applied: dict[str, Any] | None, details: dict[str, Any]
    ) -> dict[str, Any]:
        """What the migration set last: the state's, else the upload's from the log (its
        space taken as it is now: the migration never moved documents then), else Lekto's
        values now. An error reading the log goes on (ApiError)."""
        if applied is not None:
            return applied
        if self._target is None:
            return current(details)
        log = await self._target.log(lekto_id)
        return uploaded(log, details.get("space_id")) or current(details)

    def align(self, base: dict[str, Any], details: dict[str, Any], resolved: Resolved) -> Alignment:
        """What to change of the document as Lekto has it (`details`)."""
        return align(
            base,
            current(details),
            self.want(resolved),
            parents=self._parents,
            types=self._types,
        )
