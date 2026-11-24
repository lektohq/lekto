"""The tools of the domains `spaces` and `lenses`: where documents lie and who sees them, and the
caller's saved views, read only (Tobi, 01.11.2026, `.knowledge/decisions/2026-11-01-mcp.md`:
managing Lekto stays in the web UI)."""

from collections.abc import Iterable, Mapping
from uuid import UUID

from mcp.server.mcpserver import Context
from pydantic import BaseModel

from lekto.adapters.inbound.context import ApiContext
from lekto.adapters.inbound.mcp.names import FORMER_ACCOUNT, Names, member_labels, space_label
from lekto.adapters.inbound.mcp.output import compact
from lekto.adapters.inbound.mcp.registry import Tools, principal_of
from lekto.core.domain.ids import SpaceId
from lekto.core.domain.lenses import Lens
from lekto.core.domain.rights import Actor, TokenRight


class MemberOut(BaseModel):
    name: str
    role: str


class SpaceOut(BaseModel):
    name: str
    personal: bool | None
    description: str | None
    role: str | None  # yours
    members: list[MemberOut]


class SpacesOut(BaseModel):
    spaces: list[SpaceOut]


class LensFactOut(BaseModel):
    """A fact the documents have; what is missing is any."""

    kind: str | None = None
    value: str | None = None
    role: str | None = None


class LensOut(BaseModel):
    """Every filter of a lens, as `documents_list lens=` applies them (CO-K08)."""

    name: str
    query: str | None
    contacts: list[str]
    document_types: list[str]
    groups: list[str]  # of contacts and of types
    tags: list[str]
    topics: list[str]
    spaces: list[str]
    field: str | None
    facts: list[LensFactOut]
    document_period: str | None
    document_date_from: str | None
    document_date_to: str | None


class LensesOut(BaseModel):
    lenses: list[LensOut]


def add_space_tools(tools: Tools, context: ApiContext) -> None:
    @tools.read(
        "spaces_list",
        "The spaces you are a member of: a personal space by its person's name, your role "
        "(read or edit) and who else sees its documents.",
        needs=TokenRight.SPACES_READ,
    )
    async def spaces_list(ctx: Context) -> str:
        user = principal_of(ctx).actor
        spaces = await context.spaces.list_spaces(user)
        people = await member_labels(context, user, spaces)
        return compact(
            SpacesOut(
                spaces=[
                    SpaceOut(
                        name=space_label(space, people),
                        personal=True if space.personal_of is not None else None,
                        description=space.description,
                        role=None if (role := space.role_of(user.id)) is None else role.value,
                        members=[
                            MemberOut(name=people.get(id, FORMER_ACCOUNT), role=role.value)
                            for id, role in space.members.items()
                            if id != user.id
                        ],
                    )
                    for space in spaces
                ]
            )
        )

    @tools.read(
        "lenses_list",
        "Your lenses (saved views of the documents) with their words and filters; "
        "documents_list takes one by name.",
        needs=TokenRight.LENSES_READ,
    )
    async def lenses_list(ctx: Context) -> str:
        user = principal_of(ctx).actor
        names = await (await Names.load(context, user)).with_spaces(context, user)
        lenses = await context.lenses.list_lenses(user)
        return compact(LensesOut(lenses=[_lens(lens, names) for lens in lenses]))


async def space_name(context: ApiContext, user: Actor, id: SpaceId) -> str:
    """How the caller reads the space `id`: a personal one by its person's name."""
    space = await context.spaces.get(user, id)
    return space_label(space, await member_labels(context, user, [space]))


def _lens(lens: Lens, names: Names) -> LensOut:
    chosen = lens.filter
    field = None if chosen.field_id is None else names.fields.get(chosen.field_id)

    def named(ids: Iterable[UUID], table: Mapping[UUID, str]) -> list[str]:
        return [table[id] for id in ids if id in table]

    return LensOut(
        name=lens.name,
        query=lens.query,
        contacts=named(chosen.contact_ids, names.contacts),
        document_types=named(chosen.document_type_ids, names.document_types),
        groups=named((*chosen.contact_group_ids, *chosen.document_type_group_ids), names.groups),
        tags=named(chosen.tag_ids, names.tags),
        topics=named(chosen.topic_ids, names.topics),
        spaces=named(chosen.space_ids, names.spaces),
        field=None if field is None else field.name,
        facts=[
            LensFactOut(
                kind=None if fact.kind is None else fact.kind.value,
                value=fact.value,
                role=None if fact.role is None else fact.role.value,
            )
            for fact in chosen.facts
        ],
        document_period=None if chosen.relative_period is None else chosen.relative_period.value,
        document_date_from=None if chosen.date_from is None else chosen.date_from.isoformat(),
        document_date_to=None if chosen.date_to is None else chosen.date_to.isoformat(),
    )
