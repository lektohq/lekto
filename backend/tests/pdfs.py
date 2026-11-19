"""PDFs for the tests that PDFium has trouble with, built byte by byte or with pikepdf."""

import io
import zlib
from pathlib import Path

import pikepdf


def text_bomb(path: Path, operators: int) -> Path:
    """A page whose content stream shows `operators` times one letter: PDFium builds an object
    for each, two million (21 KB of file) take 1.1 GB."""
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(595, 842))
    font = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica
    )
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pdf.make_indirect(font)))
    body = b"BT /F1 1 Tf " + b"(A) Tj " * operators + b"ET"
    stream = pikepdf.Stream(pdf, zlib.compress(body, 9))
    stream.Filter = pikepdf.Name.FlateDecode
    page.Contents = stream
    pdf.save(path, compress_streams=False, recompress_flate=False)
    return path


def missing_page(path: Path) -> Path:
    """A PDF whose page tree names two pages, the second of which is not there: PDFium opens it
    and fails to load that page."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 9 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
    ]
    out = bytearray(b"%PDF-1.7\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1) + b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    path.write_bytes(bytes(out))
    return path


def _plain(pages: int) -> bytes:
    """A PDF of empty pages, its objects uncompressed and in order (for byte surgery)."""
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(200, 300))
    pdf.docinfo["/Title"] = "A title"
    buffer = io.BytesIO()
    pdf.save(buffer, object_stream_mode=pikepdf.ObjectStreamMode.disable, compress_streams=False)
    return buffer.getvalue()


def broken_pages_tree() -> bytes:
    """A PDF whose page tree and first page cannot be parsed: qpdf rebuilds it and raises
    `RuntimeError` ("/Count is wrong after flattening pages tree")."""
    data = _plain(3).replace(b"/Count 3", b"/Cou>t 3", 1)
    return data.replace(b"/Type /Pages >>\nendobj\n4 0 obj", b"/Type /Pages >>\n8ndobj\n4<0 obj", 1)


def metadata_not_a_stream() -> bytes:
    """A PDF whose catalog names as its XMP metadata a dictionary, not a stream: it opens,
    and reading the metadata raises `PdfError`."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R /Metadata 4 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
        b"<< /Type /Metadata /Subtype /XML >>",
    ]
    out = bytearray(b"%PDF-1.7\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1) + b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)
