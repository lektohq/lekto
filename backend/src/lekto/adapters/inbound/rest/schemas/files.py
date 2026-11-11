"""A document's files as they are stored, and what they say about themselves."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lekto.core.domain.versions import DocumentVersion
from lekto.core.ports.metadata import FileMetadata, MetadataSource
from lekto.core.services.documents import DocumentFiles, StoredFile


class MetadataEntryOut(BaseModel):
    source: MetadataSource = Field(
        description=(
            "`info`: a PDF's document information; `xmp`: its XMP packet (`prefix:name`); "
            "`exif`: an image's EXIF tags."
        )
    )
    key: str = Field(examples=["xmp:CreatorTool"])
    value: str = Field(description="As the file holds it; someone else's text.")


class FileMetadataOut(BaseModel):
    format: str = Field(examples=["PDF", "JPEG"])
    pdf_version: str | None = Field(examples=["1.7"])
    pdfa: str | None = Field(description="PDF/A part and conformance.", examples=["2B"])
    pages: int | None
    width: int | None = Field(description="An image's width in pixels.")
    height: int | None = Field(description="An image's height in pixels.")
    dpi: float | None = Field(description="An image's resolution.")
    entries: list[MetadataEntryOut] = Field(description="In the file's order.")

    @classmethod
    def of(cls, metadata: FileMetadata) -> "FileMetadataOut":
        return cls(
            format=metadata.format,
            pdf_version=metadata.pdf_version,
            pdfa=metadata.pdfa,
            pages=metadata.pages,
            width=metadata.width,
            height=metadata.height,
            dpi=metadata.dpi,
            entries=[
                MetadataEntryOut(source=entry.source, key=entry.key, value=entry.value)
                for entry in metadata.entries
            ],
        )


class StoredFileOut(BaseModel):
    size: int = Field(description="In bytes.")
    sha256: str
    metadata: FileMetadataOut | None = Field(
        description="Null if the file cannot be read for it (damaged, encrypted)."
    )

    @classmethod
    def of(cls, stored: StoredFile) -> "StoredFileOut":
        return cls(
            size=stored.size,
            sha256=stored.sha256,
            metadata=None if stored.metadata is None else FileMetadataOut.of(stored.metadata),
        )


class VersionKindOut(StrEnum):
    RECEIVED = "received"
    REPLACED = "replaced"
    EDITED = "edited"
    SPLIT = "split"
    SEPARATED = "separated"


class DocumentVersionOut(BaseModel):
    """A version of the document's original: its number (from 1), whether it is the current
    one, its file, how and when it came, by whom (null where nobody is known), and what it was
    made from (an edit: the version and its pages). Its file:
    `GET /documents/{id}/versions/{number}/original`."""

    number: int
    current: bool
    original_filename: str
    media_type: str
    kind: VersionKindOut = Field(
        description="`received`: how the document came in; `replaced`: a person put another "
        "file in its place; `edited`: a person edited its pages; `split`: the first version, "
        "pages split off another document (by a person, or at a separator sheet); `separated`: "
        "the first part of the stack the document came in as, split at its separator sheets."
    )
    created_at: datetime
    created_by: UUID | None
    detail: dict[str, Any] = Field(
        description=(
            "What it was made from. `edited` and `split`: `pages`, each with its `source` (0 "
            "the edited version, 1, 2, … the files in `added`, by name), `page` and `rotate`; "
            "`edited` also `from`, the version edited, and `split_off`, the documents split off "
            "in the same edit; `split` also `document`, `title` and `version`, the document "
            "it was split off (which may be gone since) and its version then, and `sheets` "
            "where it was split at separator sheets. `separated`: `pages` (source 0, the "
            "stack), `from`, `sheets`, the pages that were separator sheets, and `split_off`, "
            "the documents made of the other parts."
        )
    )

    @classmethod
    def of(cls, version: DocumentVersion, *, current: bool) -> "DocumentVersionOut":
        return cls(
            number=version.number,
            current=current,
            original_filename=version.original_filename,
            media_type=version.media_type,
            kind=VersionKindOut(version.kind.value),
            created_at=version.created_at,
            created_by=version.created_by,
            detail=dict(version.detail),
        )


class DocumentFilesOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "added": "2026-07-03T08:40:36Z",
                    "modified": "2026-07-07T10:12:00Z",
                    "original_filename": "scan-2026-07-03.pdf",
                    "media_type": "application/pdf",
                    "page_count": 2,
                    "original": {
                        "size": 10_812_334,
                        "sha256": (
                            "60da47f43707a540e24deda1ab809e1e395af4a86351d5784b9158acaafffddc"
                        ),
                        "metadata": {
                            "format": "PDF",
                            "pdf_version": "1.4",
                            "pdfa": None,
                            "pages": 2,
                            "width": None,
                            "height": None,
                            "dpi": None,
                            "entries": [
                                {"source": "info", "key": "Producer", "value": "Scanner 2.1"}
                            ],
                        },
                    },
                    "archive": None,
                    "versions": [
                        {
                            "number": 1,
                            "current": True,
                            "original_filename": "scan-2026-07-03.pdf",
                            "media_type": "application/pdf",
                            "kind": "received",
                            "created_at": "2026-07-03T08:40:36Z",
                            "created_by": "01999d5e-4444-7c1e-b6a3-2f4d5e6f7a8b",
                            "detail": {},
                        }
                    ],
                }
            ]
        }
    )

    added: datetime
    modified: datetime
    original_filename: str
    media_type: str
    page_count: int | None
    original: StoredFileOut
    archive: StoredFileOut | None = Field(description="Null while there is none.")
    versions: list[DocumentVersionOut] = Field(
        description="The versions of the original, the first first; the last is the current one."
    )

    @classmethod
    def of(cls, files: DocumentFiles) -> "DocumentFilesOut":
        document = files.document
        return cls(
            added=document.created_at,
            modified=document.updated_at,
            original_filename=document.original_filename,
            media_type=document.media_type,
            page_count=document.page_count,
            original=StoredFileOut.of(files.original),
            archive=None if files.archive is None else StoredFileOut.of(files.archive),
            versions=[
                DocumentVersionOut.of(version, current=index == len(files.versions) - 1)
                for index, version in enumerate(files.versions)
            ],
        )
