"""No NUL in a text of a request (RB-08)."""

import pytest
from pydantic import ValidationError as PydanticError

from lekto.adapters.inbound.rest.schemas.master_data import TagCreate
from lekto.adapters.inbound.schemas import refuse_nul


@pytest.mark.parametrize(
    ("value", "where"),
    [
        ("a\x00b", "a text"),
        ({"name": "a\x00b"}, "name"),
        ({"items": [{"value": "ok"}, {"value": "a\x00"}]}, "items[1].value"),
        ({"a\x00": 1}, "a key"),
    ],
)
def test_a_nul_is_refused_wherever_it_stands(value: object, where: str) -> None:
    with pytest.raises(ValueError, match=rf"^{where.replace('[', r'\[')} holds a NUL"):
        refuse_nul(value)


def test_texts_without_nul_and_other_values_pass() -> None:
    refuse_nul({"name": "Muster Bäckerei", "ids": [1, 2.5, None, True], "nested": {"x": "y"}})


def test_a_body_with_a_nul_is_invalid() -> None:
    with pytest.raises(PydanticError, match="name holds a NUL"):
        TagCreate.model_validate({"name": "a\x00b"})
    assert TagCreate.model_validate({"name": "ab"}).name == "ab"
