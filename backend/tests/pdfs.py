"""PDFs for the tests that PDFium has trouble with, built byte by byte or with pikepdf."""

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
