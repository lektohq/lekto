"""Changing many documents at once (`.idea/decisions/2026-10-28-bulk-actions.md`): one action on
documents a person selected in the documents list, a page of them or all the hits of a search and
filters, worked through in the background.

The selection is fixed when the person starts: the documents it names then, at most
`MAX_DOCUMENTS`. Each document then goes through the same change a person makes on one (rights,
change rules, events, decisions), one transaction each; one that cannot be changed is skipped
with its reason, and the others go on.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from lekto.core.domain.documents import MAX_TAGS
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.identity import ViaToken
from lekto.core.domain.ids import (
    BulkOperationId,
    ContactId,
    DocumentId,
    DocumentTypeId,
    SpaceId,
    TagId,
    UserId,
    new_id,
)
from lekto.core.domain.json_value import JsonObject, JsonValue, as_list, as_text
from lekto.core.domain.pipeline import Node
from lekto.core.domain.progress import Progress
from lekto.core.domain.reasons import ReasonCode, because

MAX_DOCUMENTS = 10_000
"""Documents one action changes at most."""

MAX_IDS = 500
"""Documents a selection names one by one at most (a page or a few pages)."""

_FIELDS = ("add", "remove", "contact", "document_type", "topic", "space", "node")


class BulkKind(StrEnum):
    CHANGE_TAGS = "change_tags"
    SET_CONTACT = "set_contact"
    SET_DOCUMENT_TYPE = "set_document_type"
    SET_TOPIC = "set_topic"
    MOVE = "move"
    CONFIRM = "confirm"
    REPROCESS = "reprocess"
    DELETE = "delete"


TAKES: Mapping[BulkKind, frozenset[str]] = {
    BulkKind.CHANGE_TAGS: frozenset({"add", "remove"}),
    BulkKind.SET_CONTACT: frozenset({"contact"}),
    BulkKind.SET_DOCUMENT_TYPE: frozenset({"document_type"}),
    BulkKind.SET_TOPIC: frozenset({"topic"}),
    BulkKind.MOVE: frozenset({"space"}),
    BulkKind.REPROCESS: frozenset({"node"}),
    BulkKind.CONFIRM: frozenset(),
    BulkKind.DELETE: frozenset(),
}
"""The fields of `BulkAction` each kind of action takes; any other given is a mistake."""


@dataclass(frozen=True)
class BulkAction:
    """What to do to each document: the tags to `add` and to `remove`; a contact, type or topic
    to set (None: to clear); the space to move into; the node to process again from."""

    kind: BulkKind
    add: frozenset[TagId] = frozenset()
    remove: frozenset[TagId] = frozenset()
    contact: ContactId | None = None
    document_type: DocumentTypeId | None = None
    topic: TagId | None = None
    space: SpaceId | None = None
    node: Node | None = None

    def __post_init__(self) -> None:
        given = {name for name in _FIELDS if getattr(self, name)}
        if stray := given - TAKES[self.kind]:
            raise ValidationError(f"{self.kind.value} takes no {', '.join(sorted(stray))}")
        if self.kind is BulkKind.CHANGE_TAGS and not (self.add or self.remove):
            raise ValidationError("name the tags to add or remove")
        if self.add & self.remove:
            raise ValidationError("a tag is both added and removed")
        if max(len(self.add), len(self.remove)) > MAX_TAGS:
            raise ValidationError(f"at most {MAX_TAGS} tags to add and {MAX_TAGS} to remove")
        if self.kind is BulkKind.MOVE and self.space is None:
            raise ValidationError("name the space to move into")
        if self.kind is BulkKind.REPROCESS and (self.node is None or self.node is Node.RECEIVE):
            raise ValidationError("name the step to process again from")

    def to_json(self) -> JsonObject:
        add: list[JsonValue] = [str(tag) for tag in sorted(self.add)]
        remove: list[JsonValue] = [str(tag) for tag in sorted(self.remove)]
        return {
            "kind": self.kind.value,
            "add": add,
            "remove": remove,
            "contact": None if self.contact is None else str(self.contact),
            "document_type": None if self.document_type is None else str(self.document_type),
            "topic": None if self.topic is None else str(self.topic),
            "space": None if self.space is None else str(self.space),
            "node": None if self.node is None else self.node.value,
        }

    @classmethod
    def from_json(cls, data: JsonValue) -> "BulkAction":
        if not isinstance(data, dict):
            raise ValidationError("an action is an object")

        def uuid(name: str) -> UUID | None:
            value = as_text(data.get(name))
            return None if value is None else UUID(value)

        contact, document_type, topic, space = (
            uuid(name) for name in ("contact", "document_type", "topic", "space")
        )
        node = as_text(data.get("node"))
        return cls(
            kind=BulkKind(str(data.get("kind"))),
            add=frozenset(TagId(UUID(str(tag))) for tag in as_list(data.get("add"))),
            remove=frozenset(TagId(UUID(str(tag))) for tag in as_list(data.get("remove"))),
            contact=None if contact is None else ContactId(contact),
            document_type=None if document_type is None else DocumentTypeId(document_type),
            topic=None if topic is None else TagId(topic),
            space=None if space is None else SpaceId(space),
            node=None if node is None else Node(node),
        )


@dataclass(kw_only=True)
class BulkOperation(Progress):
    """A person's action on the documents they selected, worked through in the background.
    `changed`: documents it changed; the rest as `Progress` counts them. `via`: the API token
    the person started it through, kept with each change as with one by hand."""

    id: BulkOperationId
    user_id: UserId
    action: BulkAction
    via: ViaToken | None = None
    changed: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if len(self.documents) > MAX_DOCUMENTS:
            raise ValidationError(because(ReasonCode.BULK_TOO_MANY, max=MAX_DOCUMENTS))

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        action: BulkAction,
        documents: tuple[DocumentId, ...],
        now: datetime,
        via: ViaToken | None = None,
    ) -> Self:
        return cls(
            id=BulkOperationId(new_id()),
            user_id=user_id,
            action=action,
            documents=documents,
            via=via,
            created_at=now,
        )

    def record_changed(self) -> None:
        """One more document done: the action changed it."""
        self.changed += 1
        self._next()
