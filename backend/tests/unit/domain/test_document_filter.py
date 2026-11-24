"""The filter of a query of documents (`ports.repository.DocumentFilter`)."""

import pytest

from lekto.core.ports.repository import DocumentFilter


def test_the_ids_are_id_references() -> None:
    """As `id_reference` makes them: SQL asks `LIKE '%…'`, where `%` and `_` match anything,
    and the memory adapter `endswith` (SQ-K05)."""
    assert DocumentFilter(ids=frozenset({"a1b2c3d4", "0" * 32})).ids
    for wrong in ("%", "a1b2_3d4", "A1B2C3D4", "a1b2-c3d4", "a1b2", "x" * 32):
        with pytest.raises(ValueError, match="id"):
            DocumentFilter(ids=frozenset({wrong}))
