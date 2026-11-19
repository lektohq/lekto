"""The limits REST and MCP take from the core, which the core checks itself (RA-03, RB-09)."""

import pytest

from lekto.core.domain.bulk import BulkAction, BulkKind
from lekto.core.domain.documents import MAX_TAGS
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.fields import (
    MAX_CHOICES,
    MAX_FIELD_POSITION,
    FieldDefinition,
    FieldType,
)
from lekto.core.domain.identifiers import MAX_IDENTIFIER_VALUE, IdentifierKind, normalise_identifier
from lekto.core.domain.ids import TagId, new_id
from lekto.core.domain.imports import ImportedMetadata
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.rules import MAX_STEP_NAME, STEP_NAME
from lekto.core.domain.webhooks import MAX_HEADER_NAME, validate_header_names
from tests.builders import NOW


def tags(count: int) -> frozenset[TagId]:
    return frozenset(TagId(new_id()) for _ in range(count))


def test_an_identifier_s_value_has_at_most_its_length() -> None:
    """Checked before the kind: the longest value is refused only as no contract number."""
    longest = "1" * MAX_IDENTIFIER_VALUE
    with pytest.raises(ValidationError) as caught:
        normalise_identifier(IdentifierKind.CONTRACT_NUMBER, longest)
    assert caught.value.reason.code is not ReasonCode.INPUT_TOO_LONG
    with pytest.raises(ValidationError) as caught:
        normalise_identifier(IdentifierKind.CONTRACT_NUMBER, longest + "1")
    assert caught.value.reason.code is ReasonCode.INPUT_TOO_LONG


def test_tags_in_bulk_and_in_an_import_have_their_limit() -> None:
    BulkAction(kind=BulkKind.CHANGE_TAGS, add=tags(MAX_TAGS), remove=tags(MAX_TAGS))
    with pytest.raises(ValidationError):
        BulkAction(kind=BulkKind.CHANGE_TAGS, add=tags(MAX_TAGS + 1))
    with pytest.raises(ValidationError):
        BulkAction(kind=BulkKind.CHANGE_TAGS, remove=tags(MAX_TAGS + 1))
    ImportedMetadata(tag_ids=tags(MAX_TAGS))
    with pytest.raises(ValidationError):
        ImportedMetadata(tag_ids=tags(MAX_TAGS + 1))


def test_a_field_has_at_most_its_choices_and_lies_within_its_positions() -> None:
    def field(choices: int = 1, position: int = 0) -> FieldDefinition:
        return FieldDefinition.create(
            name="Plan",
            data_type=FieldType.CHOICE,
            now=NOW,
            choices=[f"choice {n}" for n in range(choices)],
            position=position,
        )

    field(MAX_CHOICES, -MAX_FIELD_POSITION)
    field(position=MAX_FIELD_POSITION).place(-MAX_FIELD_POSITION)
    with pytest.raises(ValidationError):
        field(MAX_CHOICES + 1)
    for position in (MAX_FIELD_POSITION + 1, -MAX_FIELD_POSITION - 1):
        with pytest.raises(ValidationError):
            field(position=position)


def test_names_of_steps_and_headers_have_their_length() -> None:
    assert STEP_NAME.fullmatch("s" * MAX_STEP_NAME)
    assert not STEP_NAME.fullmatch("s" * (MAX_STEP_NAME + 1))
    assert validate_header_names(["X" * MAX_HEADER_NAME]) == ("X" * MAX_HEADER_NAME,)
    with pytest.raises(ValidationError):
        validate_header_names(["X" * (MAX_HEADER_NAME + 1)])
