"""Every operation that needs a caller names the right an API token needs for it (`x-right`,
`.knowledge/plans/token-rights.md`); one without a mark would refuse every token."""

from typing import Any

from lekto.adapters.inbound.rest.auth import ANY, RIGHT_KEY, SESSION
from lekto.composition.openapi import openapi_document
from lekto.core.domain.rights import ADMIN_RIGHTS, TokenRight

METHODS = ("get", "post", "put", "patch", "delete")
PREFIX = "/api/v1"


def _operations() -> dict[tuple[str, str], dict[str, Any]]:
    paths: dict[str, dict[str, Any]] = openapi_document()["paths"]  # type: ignore[assignment]
    return {
        (method.upper(), path.removeprefix(PREFIX)): operation
        for path, item in paths.items()
        for method, operation in item.items()
        if method in METHODS
    }


def test_every_operation_with_a_caller_names_its_right() -> None:
    allowed = {right.value for right in TokenRight if right not in ADMIN_RIGHTS} | {SESSION, ANY}
    operations = _operations()
    assert len(operations) > 150
    callers = {
        key: operation
        for key, operation in operations.items()
        if any({"session", "token"} & set(item) for item in operation.get("security", []))
    }
    assert len(callers) > 150
    unmarked = [
        key for key, operation in callers.items() if operation.get(RIGHT_KEY) not in allowed
    ]
    assert unmarked == []


def test_the_rights_follow_the_plan_where_an_area_does_not_say_it() -> None:
    marks = {key: operation.get(RIGHT_KEY) for key, operation in _operations().items()}
    assert marks["POST", "/documents"] == "documents:upload"
    assert marks["GET", "/documents"] == "documents:read"
    assert marks["PATCH", "/documents/{id}"] == "documents:write"
    assert marks["GET", "/documents/count"] == "documents:count"
    assert marks["GET", "/inbox/summary"] == "documents:count"
    assert marks["GET", "/inbox"] == "documents:read"
    assert marks["POST", "/documents/search"] == "documents:read"
    assert marks["POST", "/documents/search/warm"] == "documents:read"
    assert marks["POST", "/documents/{id}/dry-run"] == "documents:read"
    assert marks["GET", "/events"] == "documents:read"
    assert marks["GET", "/search/status"] == "system:read"
    assert marks["POST", "/search/check"] == "system:read"
    assert marks["POST", "/search/reindex"] == "system:write"
    assert marks["GET", "/mailboxes"] == "system:read"
    assert marks["POST", "/mailboxes/{id}/fetch"] == "system:write"
    assert marks["POST", "/mail-rules/dry-run"] == "system:read"
    assert marks["GET", "/users"] == "spaces:read"
    assert marks["GET", "/users/{id}"] == "spaces:read"
    assert marks["PATCH", "/users/{id}"] == "system:write"
    assert marks["POST", "/webhooks"] == "webhooks:write"
    assert marks["POST", "/rules/{id}/apply/preview"] == "rules:read"
    assert marks["POST", "/identifiers/open/search"] == "master_data:read"
    assert marks["GET", "/auth/me"] == ANY
    assert marks["POST", "/auth/tokens"] == SESSION
    assert marks["DELETE", "/users/{id}"] == SESSION
