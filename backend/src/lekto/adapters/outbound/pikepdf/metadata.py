"""The metadata of a stored file: of a PDF with pikepdf (its document information and its XMP
packet), of an image with Pillow (format, size, resolution, EXIF).

Values are text as the file holds them; a value of bytes (an EXIF maker note) is left out, a
long one cut at `MAX_VALUE` characters. Of an image's tags, those that only describe how its
pixels are stored (strips, compression, bits) are left out; the camera's (the EXIF directory)
are in. A file that cannot be read, or an encrypted PDF, is unprocessable.
"""

import asyncio
import email.policy
import re
from email.parser import BytesHeaderParser
from pathlib import Path
from typing import BinaryIO

import pikepdf
from PIL import ExifTags, Image, UnidentifiedImageError

from lekto.adapters.outbound.imaging import DOCUMENT_FORMATS
from lekto.core.domain import media_types
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.metadata import FileMetadata, MetadataEntry, MetadataReader, MetadataSource

MAX_VALUE = 2000
# How the pixels are stored, and pointers to other directories: nothing a person reads.
_STORAGE_TAGS = frozenset(
    {
        *("BitsPerSample", "Compression", "ExifOffset", "FillOrder", "GPSInfo"),
        *("ImageLength", "ImageWidth", "JPEGInterchangeFormat", "JPEGInterchangeFormatLength"),
        *("PhotometricInterpretation", "PlanarConfiguration", "Predictor", "ResolutionUnit"),
        *("RowsPerStrip", "SampleFormat", "SamplesPerPixel", "StripByteCounts", "StripOffsets"),
        *("TileByteCounts", "TileLength", "TileOffsets", "TileWidth", "XResolution"),
        *("YResolution", "ExifImageHeight", "ExifImageWidth", "InteroperabilityOffset"),
    }
)
_QUALIFIED = re.compile(r"\{(.*)\}(.*)")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class FileMetadataReader(MetadataReader):
    async def read_metadata(self, source: Path) -> FileMetadata:
        return await asyncio.to_thread(_read, source)


def _read(source: Path) -> FileMetadata:
    with source.open("rb") as handle:
        kind = media_types.detect(handle.read(media_types.SNIFF_SIZE))
        if kind == media_types.EML:
            handle.seek(0)
            return _mail(handle)
    if kind == media_types.PDF:
        return _pdf(source)
    if kind in (media_types.JPEG, media_types.PNG, media_types.TIFF):
        return _image(source)
    raise UnprocessableDocumentError(because(ReasonCode.FILE_NOT_PDF_OR_IMAGE))


def _text(value: object) -> str | None:
    if isinstance(value, bytes):
        return None
    text = ", ".join(map(str, value)) if isinstance(value, list | tuple) else str(value)
    text = _CONTROL.sub("", text).strip()
    return text[:MAX_VALUE] if text else None


# What qpdf raises for a damaged file: on opening, and on reading an object later (it reads
# them as they are used), as `RuntimeError` too ("/Count is wrong after flattening pages tree").
_DAMAGED = (pikepdf.PdfError, RuntimeError)


def _pdf(source: Path) -> FileMetadata:
    try:
        pdf = pikepdf.open(source)
    except pikepdf.PasswordError:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_ENCRYPTED)) from None
    except _DAMAGED:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_UNREADABLE)) from None
    try:
        with pdf:
            return _read_pdf(pdf)
    except _DAMAGED:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_UNREADABLE)) from None


def _read_pdf(pdf: pikepdf.Pdf) -> FileMetadata:
    """What the open PDF says about itself (qpdf reads its objects here)."""
    entries: list[MetadataEntry] = []
    for key, value in pdf.docinfo.items():
        text = _text(value)
        if text is not None:
            entries.append(MetadataEntry(MetadataSource.INFO, str(key).lstrip("/"), text))
    # Read only: opened outside a `with`, nothing is written back.
    xmp = pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False)
    pdfa = xmp.pdfa_status or None
    for qualified, value in xmp.items():
        text = _text(value)
        if text is None:
            continue
        match = _QUALIFIED.fullmatch(qualified)
        if match is None:
            key = qualified
        else:
            prefix = xmp.REVERSE_NS.get(match.group(1))
            key = f"{prefix}:{match.group(2)}" if prefix else match.group(2)
        entries.append(MetadataEntry(MetadataSource.XMP, key, text))
    return FileMetadata(
        format="PDF",
        pdf_version=pdf.pdf_version,
        pdfa=pdfa,
        pages=len(pdf.pages),
        entries=tuple(entries),
    )


def _image(source: Path) -> FileMetadata:
    try:
        with Image.open(source, formats=DOCUMENT_FORMATS) as image:
            dpi = image.info.get("dpi")
            entries: list[MetadataEntry] = []
            exif = image.getexif()
            for tag, value in [*exif.items(), *exif.get_ifd(ExifTags.IFD.Exif).items()]:
                name = ExifTags.TAGS.get(tag, f"0x{tag:04x}")
                text = None if name in _STORAGE_TAGS else _text(value)
                if text is not None:
                    entries.append(MetadataEntry(MetadataSource.EXIF, name, text))
            return FileMetadata(
                format=image.format or "image",
                pages=getattr(image, "n_frames", 1),
                width=image.width,
                height=image.height,
                dpi=round(float(dpi[0]), 1) if dpi else None,
                entries=tuple(entries),
            )
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        raise UnprocessableDocumentError(because(ReasonCode.IMAGE_UNREADABLE)) from None


_MAIL_HEADERS = frozenset(
    {
        "from",
        "sender",
        "to",
        "cc",
        "reply-to",
        "date",
        "subject",
        "message-id",
        "user-agent",
        "x-mailer",
    }
)
"""The header lines of a mail its file information shows; the routing ones stay out."""


def _mail(handle: BinaryIO) -> FileMetadata:
    # The header lines alone: the parts of a large mail are not read for them.
    message = BytesHeaderParser(policy=email.policy.default).parse(handle)
    entries = []
    for name, value in message.items():
        if name.lower() not in _MAIL_HEADERS:
            continue
        try:
            text = _text(str(value))
        except LookupError, UnicodeError, ValueError:
            text = None
        if text is not None:
            entries.append(MetadataEntry(MetadataSource.MAIL, name, text))
    return FileMetadata(format="E-Mail", entries=tuple(entries))
