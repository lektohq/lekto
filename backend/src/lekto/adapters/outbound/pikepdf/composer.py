"""Pages of PDFs and images put together as a new PDF with pikepdf (`ports.composer`).

A PDF's pages are copied as they are, their resources with them and nothing rendered again;
turning one adds to its `/Rotate`. The sources stay open until the new PDF is written: pikepdf
copies a page's content from its source only then.

An image becomes PDF pages first, one per frame, each as large as the frame at its resolution
(`imaging.image_dpi`, as OCRmyPDF's input). A JPEG whose picture needs no mirroring is embedded
as it is (`/DCTDecode`), its EXIF orientation as the page's rotation; any other frame is decoded
with Pillow, set upright and on white, and embedded without loss (`/FlateDecode`): as one bit,
grey or RGB.

Every PDF written gets a random file identifier, so the same pages make two files.
"""

import asyncio
import os
import zlib
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path

import pikepdf
from PIL import ExifTags, Image, ImageOps, ImageSequence

from lekto.adapters.outbound.imaging import flatten_on_white, image_dpi
from lekto.core.domain import media_types
from lekto.core.domain.editing import PagePick
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.composer import PageSource

_IMAGES = (media_types.JPEG, media_types.PNG, media_types.TIFF)
# How a page shows an EXIF orientation, turned clockwise; the others mirror the picture.
_TURNS = {1: 0, 3: 180, 6: 90, 8: 270}
_POINTS_PER_INCH = 72


class PikepdfPageComposer:
    async def count_pages(self, source: PageSource) -> int:
        return await asyncio.to_thread(_count, source)

    async def compose(
        self, sources: Sequence[PageSource], pages: Sequence[PagePick], target: Path
    ) -> None:
        await asyncio.to_thread(_compose, sources, pages, target)


def _count(source: PageSource) -> int:
    if source.media_type == media_types.PDF:
        with _opened_pdf(source.path) as pdf:
            return len(pdf.pages)
    if source.media_type in _IMAGES:
        try:
            with Image.open(source.path) as image:
                return int(getattr(image, "n_frames", 1))
        except (OSError, Image.DecompressionBombError) as error:
            raise _unreadable_image(error) from None
    raise UnprocessableDocumentError(because(ReasonCode.FILE_NOT_PDF_OR_IMAGE))


def _compose(sources: Sequence[PageSource], pages: Sequence[PagePick], target: Path) -> None:
    partial = target.with_name(f".{target.name}.part")
    with ExitStack() as stack:
        result = stack.enter_context(pikepdf.new())
        opened: dict[int, pikepdf.Pdf] = {}
        for pick in pages:
            if not 0 <= pick.source < len(sources):
                raise ValueError(f"there is no source {pick.source}")
            if pick.source not in opened:
                opened[pick.source] = stack.enter_context(_as_pdf(sources[pick.source]))
            source = opened[pick.source]
            if pick.page > len(source.pages):
                raise ValueError(f"source {pick.source} has no page {pick.page}")
            result.pages.append(source.pages[pick.page - 1])
            if pick.rotate:
                result.pages[-1].rotate(pick.rotate, relative=True)
        result.trailer.ID = pikepdf.Array(
            [pikepdf.String(os.urandom(16)), pikepdf.String(os.urandom(16))]
        )
        try:
            result.save(partial)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)


@contextmanager
def _as_pdf(source: PageSource) -> Iterator[pikepdf.Pdf]:
    if source.media_type == media_types.PDF:
        with _opened_pdf(source.path) as pdf:
            yield pdf
    elif source.media_type in _IMAGES:
        with _image_pdf(source.path) as pdf:
            yield pdf
    else:
        raise UnprocessableDocumentError(because(ReasonCode.FILE_NOT_PDF_OR_IMAGE))


@contextmanager
def _opened_pdf(path: Path) -> Iterator[pikepdf.Pdf]:
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_ENCRYPTED)) from None
    except pikepdf.PdfError:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_UNREADABLE)) from None
    with pdf:
        yield pdf


def _image_pdf(path: Path) -> pikepdf.Pdf:
    """A PDF of the frames of the image at `path`, one page each."""
    pdf = pikepdf.new()
    try:
        with Image.open(path) as image:
            as_is = image.format == "JPEG" and image.mode in ("L", "RGB")
            for frame in ImageSequence.Iterator(image):
                _add_page(pdf, frame, path.read_bytes() if as_is else None)
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        pdf.close()
        raise _unreadable_image(error) from None
    return pdf


def _add_page(pdf: pikepdf.Pdf, frame: Image.Image, jpeg: bytes | None) -> None:
    """A page of `frame`; `jpeg`: the file it is the only frame of, to embed as it is."""
    turn = _TURNS.get(frame.getexif().get(ExifTags.Base.Orientation, 1))
    dpi = image_dpi(frame.size, frame.info.get("dpi"))
    if jpeg is not None and turn is not None:
        grey = frame.mode == "L"
        data, bits, filter = jpeg, 8, pikepdf.Name.DCTDecode
        width, height = frame.size
    else:
        turn = 0
        upright = _embeddable(flatten_on_white(ImageOps.exif_transpose(frame)))
        grey = upright.mode in ("1", "L")
        data = zlib.compress(upright.tobytes())
        bits, filter = (1 if upright.mode == "1" else 8), pikepdf.Name.FlateDecode
        width, height = upright.size
    picture = pikepdf.Stream(pdf, data)
    picture.Type, picture.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
    picture.Width, picture.Height, picture.BitsPerComponent = width, height, bits
    picture.ColorSpace = pikepdf.Name.DeviceGray if grey else pikepdf.Name.DeviceRGB
    picture.Filter = filter
    across, high = width * _POINTS_PER_INCH / dpi, height * _POINTS_PER_INCH / dpi
    page = pdf.add_blank_page(page_size=(across, high))
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=picture))
    page.Contents = pdf.make_stream(f"q {across:.4f} 0 0 {high:.4f} 0 0 cm /Im0 Do Q".encode())
    if turn:
        page.rotate(turn, relative=True)


def _embeddable(image: Image.Image) -> Image.Image:
    """`image` as one bit, grey or RGB, the modes a page holds it in."""
    if image.mode in ("1", "L", "RGB"):
        return image
    if image.mode.startswith(("I", "F")):
        return image.convert("L")
    return image.convert("RGB")  # a palette, CMYK, YCbCr, LAB, HSV


def _unreadable_image(error: Exception) -> UnprocessableDocumentError:
    return UnprocessableDocumentError(
        because(ReasonCode.IMAGE_UNREADABLE_DETAIL, detail=str(error))
    )
