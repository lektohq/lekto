"""The registry of the tools: names, classes, and who may use a tool."""

import pytest

from lekto.adapters.inbound.mcp.registry import ToolClass, ToolSpec, _slim, split_name
from lekto.core.domain.identity import ApiToken, TokenScope
from lekto.core.domain.rights import TokenRight
from lekto.core.services.auth import Principal
from tests import builders


@pytest.mark.parametrize(
    ("name", "parts"),
    [
        ("documents_search", ("documents", "search")),
        ("documents_dry_run", ("documents", "dry_run")),
        ("document_types_list", ("document_types", "list")),
        ("inbox_mark_seen", ("inbox", "mark_seen")),
    ],
)
def test_a_name_is_a_domain_and_a_verb(name: str, parts: tuple[str, str]) -> None:
    assert split_name(name) == parts


@pytest.mark.parametrize(
    "name",
    ["search", "documents.search", "documents_frobnicate", "papers_list", "Documents_list"],
)
def test_other_names_are_refused(name: str) -> None:
    assert split_name(name) is None
    with pytest.raises(ValueError, match="is not <domain>_<verb>"):
        ToolSpec(name, ToolClass.READ, frozenset())


def test_the_class_gives_the_annotations() -> None:
    read = ToolSpec("documents_get", ToolClass.READ, frozenset()).annotations
    assert (read.read_only_hint, read.open_world_hint) == (True, False)
    write = ToolSpec("documents_update", ToolClass.WRITE, frozenset(), idempotent=True).annotations
    assert (write.read_only_hint, write.destructive_hint, write.idempotent_hint) == (
        False,
        False,
        True,
    )


def principal(
    *, admin: bool = False, scope: TokenScope | None = TokenScope.READ_WRITE
) -> Principal:
    user = builders.admin() if admin else builders.user()
    token = (
        None
        if scope is None
        else ApiToken.issue(
            user_id=user.id, name="t", rights=scope.rights(admin=admin), now=builders.NOW
        )[0]
    )
    return Principal(user=user, api_token=token)


def test_a_read_token_may_use_the_read_tools_only() -> None:
    read, write = (
        ToolSpec("documents_get", ToolClass.READ, frozenset({TokenRight.DOCUMENTS_READ})),
        ToolSpec("documents_update", ToolClass.WRITE, frozenset({TokenRight.DOCUMENTS_WRITE})),
    )
    reader = principal(scope=TokenScope.READ)
    assert read.refusal(reader) is None
    assert write.refusal(reader) == "this API token may only read"
    assert write.refusal(principal()) is None
    assert write.refusal(principal(scope=None)) is None  # a session may write
    assert read.refusal(None) == "authentication is required"


def test_a_tool_for_admins_is_for_admins_only() -> None:
    needs = frozenset({TokenRight.MASTER_DATA_READ, TokenRight.ADMIN_MANAGE})
    spec = ToolSpec("identifiers_open", ToolClass.READ, needs)
    assert spec.refusal(principal(admin=True)) is None
    assert spec.refusal(principal()) == "only admins may use this tool"


def test_a_tool_needs_the_rights_it_names() -> None:
    """A token of rights chosen one by one sees the tools its rights open
    (`.knowledge/plans/token-rights.md`)."""
    rules = ToolSpec("rules_list", ToolClass.READ, frozenset({TokenRight.RULES_READ}))
    admin = builders.admin()
    token = ApiToken.issue(
        user_id=admin.id,
        name="t",
        rights=frozenset({TokenRight.DOCUMENTS_READ, TokenRight.DOCUMENTS_WRITE}),
        now=builders.NOW,
    )[0]
    caller = Principal(user=admin, api_token=token)
    assert rules.refusal(caller) == "this API token lacks the right rules:read"
    needs = frozenset({TokenRight.MASTER_DATA_READ, TokenRight.ADMIN_MANAGE})
    spec = ToolSpec("identifiers_open", ToolClass.READ, needs)
    assert spec.refusal(caller) == "this API token lacks the right admin:manage"


def test_the_listed_schemas_leave_out_what_a_client_needs_no_telling() -> None:
    """Titles go; null beside the type goes where null is the default (the client leaves the
    parameter out), and stays where it means something (no default: null removes a value)."""
    schema = {
        "title": "documents_listArguments",
        "properties": {
            "title": {"title": "Title", "type": "string"},
            "contact": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
            "kept": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "either": {
                "anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}],
                "default": None,
            },
        },
    }
    assert _slim(schema) == {
        "properties": {
            "title": {"type": "string"},
            "contact": {"type": "string"},
            "kept": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "either": {
                "anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}],
                "default": None,
            },
        },
    }
