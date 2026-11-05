"""What a rule's conditions demand of a document before its text is read (`prefilter`)."""

from datetime import UTC, datetime

from lekto.core.domain.ids import ContactId, DocumentTypeId, FieldId, new_id
from lekto.core.domain.master_data import Tag, TagScope
from lekto.core.domain.rules import Condition, ConditionField, Group, Operator
from lekto.core.domain.tag_tree import TagTree
from lekto.core.ports.repository import DocumentFilter
from lekto.core.services.rules.prefilter import prefilter

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
BASE = DocumentFilter()
ACME, BANK = ContactId(new_id()), ContactId(new_id())
INVOICE = DocumentTypeId(new_id())

BILLS = Tag.create(name="Bills", now=NOW)
POWER = Tag.create(name="Power", now=NOW, parent_id=BILLS.id)
SAVINGS = Tag.create(name="Savings", now=NOW, scope=TagScope.TOPIC)
TREE = TagTree.of([BILLS, POWER, SAVINGS])


def ask(field: ConditionField, op: Operator, value: object = None) -> Condition:
    return Condition(field=field, op=op, value=value)  # type: ignore[arg-type]


def contact(*ids: ContactId) -> Condition:
    if len(ids) == 1:
        return ask(ConditionField.CONTACT, Operator.IS, str(ids[0]))
    return ask(ConditionField.CONTACT, Operator.IN, [str(id) for id in ids])


TEXT = ask(ConditionField.TEXT, Operator.CONTAINS, "Securities")


def all_of(*items: Condition | Group[Condition], negate: bool = False) -> Group[Condition]:
    return Group(mode="all", items=items, negate=negate)


def any_of(*items: Condition | Group[Condition]) -> Group[Condition]:
    return Group(mode="any", items=items)


def test_contact_type_topic_tags_and_a_field_narrow_the_documents() -> None:
    field = FieldId(new_id())
    wanted = prefilter(
        all_of(
            contact(ACME),
            ask(ConditionField.DOCUMENT_TYPE, Operator.IS, str(INVOICE)),
            ask(ConditionField.TAGS, Operator.CONTAINS, str(BILLS.id)),
            ask(ConditionField.TOPIC, Operator.IS, str(SAVINGS.id)),
            Condition(field=ConditionField.FIELD, op=Operator.PRESENT, field_id=field),
            TEXT,
        ),
        TREE,
        BASE,
    )
    assert wanted == DocumentFilter(
        contacts=frozenset({ACME}),
        document_types=frozenset({INVOICE}),
        tags=(frozenset({BILLS.id, POWER.id}),),  # a tag matches the ones below it
        topics=frozenset({SAVINGS.id}),
        field=field,
    )


def test_only_what_must_hold_narrows() -> None:
    for group in (
        all_of(contact(ACME), negate=True),
        any_of(contact(ACME), TEXT),
        any_of(contact(ACME), ask(ConditionField.DOCUMENT_TYPE, Operator.IS, str(INVOICE))),
        all_of(ask(ConditionField.CONTACT, Operator.MISSING)),
        all_of(ask(ConditionField.TAGS, Operator.PRESENT)),
        all_of(TEXT, all_of(contact(ACME), negate=True)),
        all_of(
            Condition(field=ConditionField.FIELD, op=Operator.MISSING, field_id=FieldId(new_id()))
        ),
    ):
        assert prefilter(group, TREE, BASE) == BASE, group


def test_nested_all_groups_and_one_field_in_an_any_group_narrow() -> None:
    assert prefilter(all_of(TEXT, all_of(contact(ACME))), TREE, BASE) == DocumentFilter(
        contacts=frozenset({ACME})
    )
    assert prefilter(all_of(any_of(contact(ACME), contact(BANK))), TREE, BASE) == DocumentFilter(
        contacts=frozenset({ACME, BANK})
    )


def test_it_keeps_what_the_base_asks_and_finds_when_nothing_can_hold() -> None:
    base = DocumentFilter(contacts=frozenset({ACME, BANK}))
    assert prefilter(all_of(contact(ACME)), TREE, base) == DocumentFilter(
        contacts=frozenset({ACME})
    )
    assert prefilter(all_of(contact(ACME), contact(BANK)), TREE, BASE) is None
