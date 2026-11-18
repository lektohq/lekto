"""pikepdf and Pillow: pass the contract, and read what a PDF and an image say about
themselves (document information, XMP, PDF/A level; EXIF without how the pixels are stored)."""

import io
from pathlib import Path

import pikepdf
import pytest
from PIL import ExifTags, Image

from lekto.adapters.outbound.pikepdf import FileMetadataReader
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.ports.metadata import MetadataSource
from tests.builders import SAMPLES
from tests.contracts.processing import MetadataReaderContract
from tests.images import stated_png
from tests.mails import rich_mail
from tests.pdfs import broken_pages_tree, metadata_not_a_stream


@pytest.fixture
def metadata_reader() -> FileMetadataReader:
    return FileMetadataReader()


class TestFileMetadataReader(MetadataReaderContract):
    pass


def pdf_a(*, encrypted: bool = False) -> bytes:
    """A two-page PDF with document information and XMP claiming PDF/A-2B."""
    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.add_blank_page()
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as xmp:
        xmp["xmp:CreatorTool"] = "Lekto Test Scanner"
        xmp["pdfaid:part"] = "2"
        xmp["pdfaid:conformance"] = "B"
    pdf.docinfo["/Title"] = "Stromrechnung"
    pdf.docinfo["/Producer"] = "Lekto Test 1.0"
    out = io.BytesIO()
    encryption = pikepdf.Encryption(owner="owner", user="user") if encrypted else False
    pdf.save(out, encryption=encryption)
    return out.getvalue()


def at(directory: Path, data: bytes, name: str = "file") -> Path:
    """`data` as a file: the reader takes a path (SB-09)."""
    path = directory / name
    path.write_bytes(data)
    return path


async def test_a_pdf_with_its_information_xmp_and_pdf_a_level(
    metadata_reader: FileMetadataReader, tmp_path: Path
) -> None:
    metadata = await metadata_reader.read_metadata(at(tmp_path, pdf_a()))
    assert (metadata.format, metadata.pages, metadata.pdfa) == ("PDF", 2, "2B")
    entries = {(entry.source, entry.key): entry.value for entry in metadata.entries}
    assert entries[MetadataSource.INFO, "Title"] == "Stromrechnung"
    assert entries[MetadataSource.INFO, "Producer"] == "Lekto Test 1.0"
    assert entries[MetadataSource.XMP, "xmp:CreatorTool"] == "Lekto Test Scanner"
    assert entries[MetadataSource.XMP, "pdfaid:part"] == "2"


async def test_an_encrypted_pdf_is_unprocessable(
    metadata_reader: FileMetadataReader, tmp_path: Path
) -> None:
    with pytest.raises(UnprocessableDocumentError, match="encrypted"):
        await metadata_reader.read_metadata(at(tmp_path, pdf_a(encrypted=True)))


async def test_a_photo_with_its_camera_but_not_how_its_pixels_are_stored(
    metadata_reader: FileMetadataReader, tmp_path: Path
) -> None:
    image = Image.new("RGB", (120, 80), "white")
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "Lekto"
    exif[ExifTags.Base.Model] = "Test Camera"
    exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = "2026:10:16 09:30:00"
    out = io.BytesIO()
    image.save(out, "JPEG", exif=exif, dpi=(300, 300))
    metadata = await metadata_reader.read_metadata(at(tmp_path, out.getvalue()))
    assert (metadata.format, metadata.width, metadata.height, metadata.dpi) == (
        "JPEG",
        120,
        80,
        300.0,
    )
    entries = {entry.key: entry.value for entry in metadata.entries}
    assert entries["Make"] == "Lekto"
    assert entries["Model"] == "Test Camera"
    assert entries["DateTimeOriginal"] == "2026:10:16 09:30:00"
    assert "ExifOffset" not in entries
    assert {entry.source for entry in metadata.entries} == {MetadataSource.EXIF}


async def test_every_page_of_a_tiff(metadata_reader: FileMetadataReader) -> None:
    metadata = await metadata_reader.read_metadata(SAMPLES / "pages.tiff")
    assert (metadata.format, metadata.pages) == ("TIFF", 2)
    assert not {entry.key for entry in metadata.entries} & {"StripOffsets", "Compression"}


async def test_a_mail_with_the_header_lines_a_person_reads(
    metadata_reader: FileMetadataReader, tmp_path: Path
) -> None:
    metadata = await metadata_reader.read_metadata(at(tmp_path, rich_mail()))
    assert metadata.format == "E-Mail"
    assert [(entry.source, entry.key) for entry in metadata.entries] == [
        (MetadataSource.MAIL, "From"),
        (MetadataSource.MAIL, "To"),
        (MetadataSource.MAIL, "Cc"),
        (MetadataSource.MAIL, "Date"),
        (MetadataSource.MAIL, "Message-ID"),
        (MetadataSource.MAIL, "Subject"),
    ]
    assert metadata.entries[-1].value == "Ihre Rechnung über 123,45 €"


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
async def test_a_file_damaged_beyond_opening_is_unprocessable(
    metadata_reader: FileMetadataReader, tmp_path: Path
) -> None:
    """qpdf reads objects as they are used, and raises `RuntimeError` too; an image may state
    more pixels than Pillow opens: each is a file that cannot be read, not a raw error."""
    huge = stated_png(tmp_path / "huge.png", 20_000, 20_000).read_bytes()
    for data in (broken_pages_tree(), metadata_not_a_stream(), huge):
        with pytest.raises(UnprocessableDocumentError):
            await metadata_reader.read_metadata(at(tmp_path, data))
