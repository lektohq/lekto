"""What the tests of the language model's signal, the judge, the fields node and the signals
without a model share: a seeded world, a fake model and its answers, the steps, documents and
contacts stored directly."""

import itertools
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

from lekto.adapters.outbound.memory import FakeLanguageModel, FakeTextLocator
from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.core.domain.classification import FieldCheck, checks_from_json
from lekto.core.domain.documents import Document, DocumentChanges
from lekto.core.domain.fields import FieldDefinition, FieldType
from lekto.core.domain.json_value import JsonObject, JsonValue
from lekto.core.domain.master_data import Contact, DocumentType, Tag
from lekto.core.domain.pipeline import (
    Node,
    NodeResult,
    NodeRun,
    Outcome,
)
from lekto.core.domain.users import User
from lekto.core.ports.llm import StructuredRequest
from lekto.core.services.classification.nodes import (
    ClassificationPolicy,
    FieldsNode,
    JudgeNode,
    LlmSignal,
    ModelFactsResult,
)
from lekto.core.services.classification.prompts import FACTS_SCHEMA
from lekto.core.services.classification.signals import (
    FactsResult,
    FactsSignal,
)
from lekto.core.services.objects import (
    text_key,
)
from lekto.core.services.pipeline import MetadataResult
from lekto.core.services.rules.nodes import ApplyRulesNode
from tests import builders
from tests.builders import NOW
from tests.unit.services.support import World

INVOICE = """\
# Stadtwerke Musterstadt GmbH
Postfach 12 34, 12345 Musterstadt

Herrn Max Nord, Musterweg 1, 12345 Musterstadt

Musterstadt, 31.03.2026

## Rechnung Nr. R-2026-0815

Stromverbrauch vom 01.01.2026 bis 31.03.2026

| Position | Betrag |
| --- | --- |
| Arbeitspreis | 70,76 € |
| Gesamtbetrag | 84,20 € |

Zahlbar bis 15.04.2026.
"""
IBAN = "DE89 3704 0044 0532 0130 00"


@dataclass
class Seeded:
    contacts: dict[str, Contact]
    types: dict[str, DocumentType]
    tags: dict[str, Tag]
    fields: dict[str, FieldDefinition]


async def seed(world: World, contacts: tuple[str, ...] = ()) -> Seeded:
    names = contacts or ("Stadtwerke Musterstadt GmbH", "Stadtwerke Beispielstadt", "AOK Bayern")
    seeded = Seeded(
        contacts={name: Contact.create(name=name, now=NOW) for name in names},
        types={name: DocumentType.create(name=name, now=NOW) for name in ("Rechnung", "Vertrag")},
        tags={name: Tag.create(name=name, now=NOW) for name in ("Strom", "Versicherung")},
        fields={},
    )
    invoice = seeded.types["Rechnung"].id
    for name, data_type, scope in [
        ("Rechnungsbetrag", FieldType.AMOUNT, [invoice]),
        ("Rechnungsnummer", FieldType.TEXT, [invoice]),
        ("Fällig am", FieldType.DATE, [invoice]),
        ("Bezahlt", FieldType.BOOLEAN, None),
    ]:
        # Bound to the invoice, the fields are required for it; the global one is optional.
        seeded.fields[name] = FieldDefinition.create(
            name=name,
            data_type=data_type,
            document_type_ids=scope,
            required_types=scope or (),
            now=NOW,
        )
    async with world.uow() as uow:
        for contact in seeded.contacts.values():
            await uow.contacts.add(contact)
        for kind in seeded.types.values():
            await uow.document_types.add(kind)
        for tag in seeded.tags.values():
            await uow.tags.add(tag)
        for field in seeded.fields.values():
            await uow.fields.add(field)
        await uow.commit()
    return seeded


FIELDS: list[JsonValue] = [
    # Keys by name: a1 Bezahlt, a2 Fällig am, a3 Rechnungsbetrag, a4 Rechnungsnummer.
    {"key": "a2", "value": "15.04.2026", "evidence": "Zahlbar bis 15.04.2026."},
    {"key": "a3", "value": "84,20 €", "evidence": "Gesamtbetrag | 84,20 €"},
    {"key": "a4", "value": "R-2026-0815", "evidence": "Rechnung Nr. R-2026-0815"},
]


def proposal(**changes: Any) -> JsonObject:
    """The language model's answer to the signal's request."""
    answer: JsonObject = {
        "sender": {"value": "Stadtwerke Musterstadt GmbH", "evidence": None},
        "recipient": "Max Nord",
        "document_type": "Rechnung",
        "new_document_type": None,
        "topic": None,
        "tags": ["Strom"],
        "new_tags": [],
        "document_date": {"value": "2026-03-31", "evidence": "Musterstadt, 31.03.2026"},
        "title": "Stromrechnung März 2026",
        "language": "de",
        "fields": FIELDS,
    }
    return answer | changes


def extraction(**values: Any) -> JsonObject:
    """Answer of the fields node's own request, for the fields in key order: Bezahlt, Fällig
    am, Rechnungsbetrag, Rechnungsnummer (sorted by name)."""
    defaults: dict[str, Any] = {
        "a1": {"value": None, "evidence": None},
        "a2": {"value": "2026-04-15", "evidence": "Zahlbar bis 15.04.2026."},
        "a3": {
            "value": {"amount": "84.20", "currency": "EUR"},
            "evidence": "Gesamtbetrag | 84,20 €",
        },
        "a4": {"value": "R-2026-0815", "evidence": "Rechnung Nr. R-2026-0815"},
    }
    return {"fields": defaults | values}


def model(*answers: JsonObject | str, facts: JsonObject | str | None = None) -> FakeLanguageModel:
    """Answers in turn; the last one again and again. The request for the facts (`facts-3`)
    it answers with `facts`, by default with none."""
    remaining = list(answers)

    def respond(request: StructuredRequest) -> JsonObject | str:
        if request.schema_name == FACTS_SCHEMA:
            return {"facts": []} if facts is None else facts
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return FakeLanguageModel(respond)


async def document_with(
    world: World, text: str = INVOICE, type: DocumentType | None = None
) -> Document:
    owner = await world.user()
    document = builders.document(owner, await world.personal_space(owner))
    document.document_type_id = None if type is None else type.id
    async with world.uow() as uow:
        await uow.documents.add(document)
        await uow.commit()
    await world.object_store.put(
        text_key(document.id), text.encode(), content_type="text/markdown; charset=utf-8"
    )
    return document


def rules_step(world: World) -> ApplyRulesNode:
    return ApplyRulesNode(
        world.uow,
        world.object_store,
        RegexPatternMatcher(0.2),
        builders.TEMPLATES,
        max_text=200_000,
    )


def policy_with(**overrides: Any) -> ClassificationPolicy:
    return replace(builders.CLASSIFICATION, **overrides)


class ModelSignal(LlmSignal):
    """The language model's signal without a webhook to hand its request to: a result at
    once (the facts it read are kept when the pipeline stores it)."""

    async def run(self, document: Document) -> NodeResult:
        result = await super().run(document)
        if isinstance(result, ModelFactsResult):
            return result.result
        assert isinstance(result, NodeResult)
        return result


def signal_step(world: World, fake: FakeLanguageModel | None, **policy: Any) -> ModelSignal:
    return ModelSignal(world.uow, world.object_store, fake, world.clock, policy_with(**policy))


def fields_step(world: World, fake: FakeLanguageModel | None) -> FieldsNode:
    return FieldsNode(world.uow, world.object_store, fake, world.clock, builders.CLASSIFICATION)


async def record(world: World, document: Document, node: Node, result: NodeResult) -> None:
    async with world.uow() as uow:
        await uow.processing_log.append(
            NodeRun(
                document_id=document.id,
                node=node,
                run=document.processing.run,
                result=result,
                pipeline_version="test",
                started_at=NOW,
                duration=timedelta(0),
            )
        )
        await uow.commit()


async def judge(
    world: World,
    document: Document,
    fake: FakeLanguageModel | None,
    *,
    locator: FakeTextLocator | None = None,
    **policy: Any,
) -> NodeResult | MetadataResult:
    """The model's signal and the facts as the pipeline logs them, then the judge; the
    signal's result if it fails."""
    signals: list[tuple[Node, ModelSignal | FactsSignal]] = [
        (Node.SIGNAL_LLM, signal_step(world, fake, **policy)),
        (Node.SIGNAL_FACTS, FactsSignal(world.uow, world.object_store)),
    ]
    for node, signal in signals:
        ran = await signal.run(document)
        result = ran.result if isinstance(ran, FactsResult) else ran
        if result.outcome is Outcome.FAILED:
            return result
        await record(world, document, node, result)
    chosen = policy_with(**policy)
    step = JudgeNode(
        world.uow,
        world.object_store,
        world.clock,
        chosen,
        thresholds=builders.THRESHOLDS,
        locator=locator,
    )
    return await step.run(document)


def checks(result: NodeResult) -> dict[str, FieldCheck]:
    return {check.field: check for check in checks_from_json(result.output["fields"])}


def responder(
    propose: JsonObject, extract: JsonObject
) -> Callable[[StructuredRequest], JsonObject]:
    def respond(request: StructuredRequest) -> JsonObject:
        if request.schema_name == FACTS_SCHEMA:
            return {"facts": []}
        return propose if request.schema_name == "proposal" else extract

    return respond


_numbers = itertools.count()


def output(result: NodeResult | FactsResult) -> Any:
    return (result.result if isinstance(result, FactsResult) else result).output


async def stored(world: World, owner: User, text: str, contact: Contact | None = None) -> Document:
    space = await world.personal_space(owner)
    document = builders.processed(owner, space, content=f"{text} {next(_numbers)}")
    if contact is not None:
        document.apply_changes(DocumentChanges(contact_id=contact.id), {}, builders.NOW)
    async with world.uow() as uow:
        await uow.documents.add(document)
        await uow.commit()
    await world.object_store.put(text_key(document.id), text.encode(), content_type="text/md")
    return document


async def contacts(world: World, *items: Contact) -> None:
    async with world.uow() as uow:
        for item in items:
            await uow.contacts.add(item)
        await uow.commit()
