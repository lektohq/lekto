"""Versions of a document's original (`.idea/architektur.md`, "Fassungen"; Umsetzungsplan
"Fassungen, Datei ersetzen, PDF bearbeiten"): a document has versions 1, 2, …, each an original
that never changes. A new version comes in when a person replaces the file or edits the pages;
none is overwritten. The document carries its current one's hash, name and media type; the
derivatives (archive PDF, text, pages) are the current version's."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from lekto.core.domain.documents import Sha256
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentId, UserId
from lekto.core.domain.json_value import JsonObject
from lekto.core.domain.validation import require_name, require_utc


class VersionKind(StrEnum):
    RECEIVED = "received"  # how the document came in
    REPLACED = "replaced"  # a person put another file in its place
    EDITED = "edited"  # a person edited its pages


@dataclass(frozen=True, kw_only=True)
class DocumentVersion:
    """Version `number` (from 1) of the original of `document_id`. `created_by`: who made it
    (the uploader for the first; None where nobody is known). `detail`: what it was made from
    (an edit: the version and its pages)."""

    document_id: DocumentId
    number: int
    sha256: Sha256
    original_filename: str
    media_type: str
    kind: VersionKind
    created_at: datetime
    created_by: UserId | None = None
    detail: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValidationError("a version is numbered from 1")
        require_name(self.original_filename, "original filename", max_length=None)
        require_name(self.media_type, "media type", max_length=None)
        require_utc(self.created_at)
