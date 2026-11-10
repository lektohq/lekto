"""Editing a document's pages (`POST /documents/{id}/edit`, `domain.editing`)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from lekto.adapters.inbound.rest.schemas.documents import DocumentDetails
from lekto.core.domain.editing import EditPart, PagePick

PARTS_LIMIT = 256 * 1024
"""Bytes the field `parts` may have: some 6,000 pages."""


class PagePickIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: int = Field(
        default=0,
        ge=0,
        description=(
            "0: the document's original (its current version); 1, 2, …: the files sent along "
            "in `files`, in their order."
        ),
    )
    page: int = Field(ge=1, description="The page of that source, from 1; an image's frames.")
    rotate: Literal[0, 90, 180, 270] = Field(
        default=0, description="Degrees clockwise, beyond how the page is shown now."
    )


class EditPartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[PagePickIn] = Field(
        min_length=1, description="Its pages in their order; each page goes in one part at most."
    )
    replaces: bool = Field(
        default=False,
        description=(
            "It becomes the document's next version; at most one part does. Every other part "
            "becomes a new document in the document's space; without one, the document is "
            "deleted."
        ),
    )

    def to_domain(self) -> EditPart:
        picks = tuple(PagePick(pick.source, pick.page, pick.rotate) for pick in self.pages)
        return EditPart(picks, replaces=self.replaces)


PARTS = TypeAdapter(list[EditPartIn])
"""The field `parts`: JSON of a list of parts."""


def parts_schema() -> dict[str, Any]:
    """The JSON schema of `parts` with its definitions in place, for the form's description."""
    schema = PARTS.json_schema()
    definitions = schema.pop("$defs", {})

    def inline(value: Any) -> Any:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/$defs/"):
                return inline(definitions[reference.removeprefix("#/$defs/")])
            return {key: inline(item) for key, item in value.items()}
        if isinstance(value, list):
            return [inline(item) for item in value]
        return value

    return inline(schema)  # type: ignore[no-any-return]


class EditedDocuments(BaseModel):
    documents: list[DocumentDetails] = Field(
        description=(
            "In the order of the parts: the document where a part replaces it, a new one for "
            "each other part. Each is processed again and waits in the inbox."
        )
    )
    deleted: bool = Field(description="No part replaced the document, and it is deleted.")


class PagePreviews(BaseModel):
    pages: list[str] = Field(
        description="Each page of the file in its order, small, as a `data:` URL of a WebP image."
    )
