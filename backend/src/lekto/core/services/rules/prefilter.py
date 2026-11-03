"""What a rule's conditions demand of a document, as a `DocumentFilter` the repository answers.

A dry run (`retroactive.RuleApplicationService.preview`) plays the rule on every document it
looks at, and reading each text is what takes the time. The filter leaves out the documents the
rule cannot hit before any text is read. It holds only what a hit must have, so it never drops
one: a condition counts only where it is a must (in `all` groups up from the root, none of them
negated, or an `any` group whose conditions all ask the same field), and only where the
repository asks it as the condition does (contact, document type, their groups, topic, tags, a
field's value). Everything else (text, patterns, facts, dates, relations, negations, `missing`)
stays for the rule to decide, as before.
"""

from collections.abc import Iterable
from dataclasses import replace
from uuid import UUID

from lekto.core.domain.ids import ContactId, DocumentTypeId, FieldId, TagId
from lekto.core.domain.rules import Condition, ConditionField, Group, Operator
from lekto.core.domain.tag_tree import TagTree
from lekto.core.ports.repository import DocumentFilter

_REFERENCES = frozenset({ConditionField.CONTACT, ConditionField.DOCUMENT_TYPE})
_HELD = frozenset(
    {
        ConditionField.TAGS,
        ConditionField.CONTACT_GROUP,
        ConditionField.DOCUMENT_TYPE_GROUP,
        ConditionField.TOPIC,
    }
)
_ASKING = frozenset({Operator.IS, Operator.IN, Operator.CONTAINS})
"""Operators that ask for one of the values (for tags, groups and topics: or one below it)."""

type Must = list[Condition]
"""Conditions one of which must hold: one condition, or those of an `any` group."""


def prefilter(group: Group, tree: TagTree, base: DocumentFilter) -> DocumentFilter | None:
    """`base` narrowed by what `group` demands of every document it holds for; None when no
    document can meet it (two contacts at once)."""
    found: DocumentFilter | None = base
    for must in _musts(group):
        if found is None:
            break
        found = _narrow(found, must, tree)
    return found


def _musts(group: Group) -> list[Must]:
    if group.negate:
        return []
    if group.mode == "any":
        conditions = [item for item in group.items if isinstance(item, Condition)]
        if len(conditions) == len(group.items) and _alike(conditions):
            return [conditions]
        return []
    found: list[Must] = []
    for item in group.items:
        if isinstance(item, Group):
            found.extend(_musts(item))
        elif _usable(item):
            found.append([item])
    return found


def _usable(condition: Condition) -> bool:
    if condition.field in _REFERENCES or condition.field in _HELD:
        return condition.op in _ASKING and bool(condition.values)
    # Every operator but `missing` needs a value of the field.
    return condition.field is ConditionField.FIELD and condition.op is not Operator.MISSING


def _alike(conditions: list[Condition]) -> bool:
    """Whether an `any` group's conditions give one must: all ask one contact, type, group,
    topic or tags field for values."""
    fields = {condition.field for condition in conditions}
    return (
        len(fields) == 1
        and fields <= _REFERENCES | _HELD
        and all(_usable(condition) for condition in conditions)
    )


def _narrow(found: DocumentFilter, must: Must, tree: TagTree) -> DocumentFilter | None:
    field = must[0].field
    if field is ConditionField.FIELD:
        # The filter takes one field; a second one stays for the rule.
        if found.field is not None or must[0].field_id is None:
            return found
        return replace(found, field=FieldId(must[0].field_id))
    ids = frozenset(id for condition in must for id in _ids(condition.values))
    match field:
        case ConditionField.CONTACT:
            contacts = _within(found.contacts, frozenset(ContactId(id) for id in ids))
            return None if not contacts else replace(found, contacts=contacts)
        case ConditionField.DOCUMENT_TYPE:
            types = _within(found.document_types, frozenset(DocumentTypeId(id) for id in ids))
            return None if not types else replace(found, document_types=types)
        case ConditionField.TOPIC:
            topics = _within(found.topics, _below(ids, tree))
            return None if not topics else replace(found, topics=topics)
        case ConditionField.TAGS:
            return replace(found, tags=(*found.tags, _below(ids, tree)))
        case ConditionField.CONTACT_GROUP:
            return replace(found, contact_groups=(*found.contact_groups, _below(ids, tree)))
        case ConditionField.DOCUMENT_TYPE_GROUP:
            groups = (*found.document_type_groups, _below(ids, tree))
            return replace(found, document_type_groups=groups)
    return found


def _ids(values: Iterable[object]) -> list[UUID]:
    return [UUID(str(value)) for value in values]


def _below(ids: Iterable[UUID], tree: TagTree) -> frozenset[TagId]:
    """The tags (groups, topics) and those below them: what a condition on them matches."""
    return tree.with_descendants(TagId(id) for id in ids)


def _within[T](current: frozenset[T] | None, wanted: frozenset[T]) -> frozenset[T]:
    return wanted if current is None else current & wanted
