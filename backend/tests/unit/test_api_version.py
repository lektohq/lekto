"""The version of the API rises with every change of the API (`.knowledge/open/api-version-fas.md`):
the fingerprint beside it is the OpenAPI document without its texts and examples."""

import hashlib
import json
import re
from typing import Any

from lekto.adapters.inbound.rest.version import API_VERSION, FINGERPRINT
from lekto.composition.openapi import openapi_document

TEXTS = frozenset({"description", "summary", "example", "examples", "title"})


def _shape(value: Any, *, names: bool = False) -> Any:
    """`value` without the keys that only explain (texts, examples). The keys of `properties` are
    names of fields (a field may be called `title`), kept all."""
    if isinstance(value, dict):
        return {
            key: _shape(item, names=key == "properties" and not names)
            for key, item in value.items()
            if names or key not in TEXTS
        }
    if isinstance(value, list):
        return [_shape(item) for item in value]
    return value


def fingerprint(document: dict[str, Any]) -> str:
    shape = _shape({key: item for key, item in document.items() if key != "info"})
    text = json.dumps(shape, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def test_the_version_is_major_dot_minor() -> None:
    assert re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)", API_VERSION)
    assert API_VERSION != "0.0"


def test_the_version_rises_with_the_api() -> None:
    document = openapi_document()
    assert document["info"]["version"] == API_VERSION  # type: ignore[index]
    current = fingerprint(document)
    assert current == FINGERPRINT, (
        "The API changed: raise API_VERSION in adapters/inbound/rest/version.py (during the "
        "beta MINOR, for every change; after it MAJOR for a change that breaks a client, with "
        "the label breaking-change, MINOR for one that only adds), and set "
        f'FINGERPRINT = "{current}".'
    )
