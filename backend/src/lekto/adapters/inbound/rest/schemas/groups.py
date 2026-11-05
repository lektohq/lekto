"""The tree of conditions of every kind of rule, as the API takes and gives it: a group of `all`
(and) or `any` (or) of its items, each a condition or a group again, `not` turning the result
around (`condition_tree` in the domain). One pair of models for every kind: the kind gives the
condition (`C`); the document rules have `AllGroup[ConditionSchema]`, the mail rules
`AllGroup[MailConditionBody]`, which OpenAPI names `AllGroup_ConditionSchema_`,
`AllGroup_MailConditionBody_` and the items `GroupItems_…_` (Tobi, 05.11.2026). The items
stand in a type alias, evaluated late, so that the two models can refer to each other."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from lekto.core.domain.condition_tree import MAX_CONDITIONS


class AllGroup[C: BaseModel](BaseModel):
    """All items hold (and); `not` turns the result around."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    all: "GroupItems[C]"
    negate: bool = Field(default=False, alias="not")


class AnyGroup[C: BaseModel](BaseModel):
    """At least one item holds (or); `not` turns the result around."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    any: "GroupItems[C]"
    negate: bool = Field(default=False, alias="not")


type GroupItems[C: BaseModel] = Annotated[
    list[C | AllGroup[C] | AnyGroup[C]], Field(min_length=1, max_length=MAX_CONDITIONS)
]
"""The items of a group: conditions of the kind, and groups again."""

AllGroup.model_rebuild()
AnyGroup.model_rebuild()


def resolve(*models: type[BaseModel], condition: type[BaseModel]) -> None:
    """Resolve the references of a kind's two group models to each other and to its
    `condition`: they are made in the kind's module, not here, where the names stand."""
    namespace = {
        "AllGroup": AllGroup,
        "AnyGroup": AnyGroup,
        "GroupItems": GroupItems,
        condition.__name__: condition,
    }
    for model in models:
        model.model_rebuild(_types_namespace=namespace)
