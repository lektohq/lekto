"""pikepdf and Pillow put pages together: pass the contract, keep a PDF's pages as they are
(turning adds to their rotation, also one they inherit), and make pages of images: a JPEG as it
is with its EXIF orientation as rotation, any other without loss, sized by its resolution."""

import io
from pathlib import Path

import pikepdf
import pytest
from PIL import ExifTags, Image

from lekto.adapters.outbound.pikepdf import PikepdfPageComposer
from lekto.core.domain import media_types
from lekto.core.domain.editing import PagePick
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.ports.composer import PageSource
from tests.builders import SAMPLES
from tests.contracts.processing import PageComposerContract


@pytest.fixture
def page_composer() -> PikepdfPageComposer:
    return PikepdfPageComposer()


class TestPikepdfPageComposer(PageComposerContract):
    pass


def three_pages(path: Path, *, inherited: int | None = None) -> PageSource:
    """A PDF of three pages of different widths (100, 200, 300 points); the second turned 90°,
    or with `inherited` all of them turned that far by the page tree."""
    pdf = pikepdf.new()
    for width in (100, 200, 300):
        pdf.add_blank_page(page_size=(width, 400))
    if inherited is None:
        pdf.pages[1].Rotate = 90
    else:
        pdf.Root.Pages.Rotate = inherited
    pdf.save(path)
    return PageSource(path, media_types.PDF)


def image(path: Path, picture: Image.Image, kind: str, **options: object) -> PageSource:
    picture.save(path, kind, **options)
    return PageSource(path, {"JPEG": media_types.JPEG, "PNG": media_types.PNG}[kind])


def widths(path: Path) -> list[tuple[int, int]]:
    """Width and rotation of every page."""
    with pikepdf.open(path) as pdf:
        return [
            (round(float(page.mediabox[2])), int(page.obj.get("/Rotate", 0))) for page in pdf.pages
        ]


async def test_pages_keep_their_rotation_and_turning_adds_to_it(
    page_composer: PikepdfPageComposer, tmp_path: Path
) -> None:
    source = three_pages(tmp_path / "three.pdf")
    target = tmp_path / "part.pdf"
    picks = [PagePick(0, 3), PagePick(0, 2, rotate=270), PagePick(0, 1, rotate=180)]
    await page_composer.compose([source], picks, target)
    assert widths(target) == [(300, 0), (200, 0), (100, 180)]


async def test_a_rotation_the_page_tree_gives_stays(
    page_composer: PikepdfPageComposer, tmp_path: Path
) -> None:
    source = three_pages(tmp_path / "three.pdf", inherited=90)
    target = tmp_path / "part.pdf"
    await page_composer.compose([source], [PagePick(0, 1), PagePick(0, 2, rotate=90)], target)
    assert widths(target) == [(100, 90), (200, 180)]


async def test_a_pdf_page_is_copied_not_rendered(
    page_composer: PikepdfPageComposer, tmp_path: Path
) -> None:
    text = PageSource(SAMPLES / "text.pdf", media_types.PDF)
    target = tmp_path / "part.pdf"
    await page_composer.compose([text], [PagePick(0, 1)], target)
    with pikepdf.open(SAMPLES / "text.pdf") as before, pikepdf.open(target) as after:
        assert after.pages[0].Contents.read_bytes() == before.pages[0].Contents.read_bytes()


async def test_the_frames_of_a_tiff_are_its_pages(
    page_composer: PikepdfPageComposer, tmp_path: Path
) -> None:
    tiff = PageSource(SAMPLES / "pages.tiff", media_types.TIFF)
    assert await page_composer.count_pages(tiff) == 2
    target = tmp_path / "part.pdf"
    await page_composer.compose([tiff], [PagePick(0, 2), PagePick(0, 1)], target)
    assert len(widths(target)) == 2


async def test_a_jpeg_is_embedded_as_it_is_turned_as_its_exif_says(
    page_composer: PikepdfPageComposer, tmp_path: Path
) -> None:
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # shown turned 90° clockwise
    source = image(
        tmp_path / "photo.jpg",
        Image.new("RGB", (600, 300), "white"),
        "JPEG",
        dpi=(100, 100),
        exif=exif,
    )
    target = tmp_path / "part.pdf"
    await page_composer.compose([source], [PagePick(0, 1, rotate=90)], target)
    with pikepdf.open(target) as pdf:
        page = pdf.pages[0]
        picture = page.Resources.XObject.Im0
        assert picture.Filter == pikepdf.Name.DCTDecode
        assert picture.read_raw_bytes() == source.path.read_bytes()
        assert int(page.Rotate) == 180
        # 600 pixels at 100 dpi: 6 inches.
        assert [round(float(value)) for value in page.mediabox] == [0, 0, 432, 216]


async def test_other_images_are_embedded_without_loss_upright_on_white(
    page_composer: PikepdfPageComposer, tmp_path: Path
) -> None:
    picture = Image.new("RGBA", (13, 7), (0, 0, 0, 0))
    picture.putpixel((0, 0), (255, 0, 0, 255))
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 2  # mirrored: no rotation shows it
    source = image(tmp_path / "shot.png", picture, "PNG", exif=exif)
    page = Image.new("1", (13, 7), 1)
    page.putpixel((12, 6), 0)  # rows of 13 bits: each starts on a byte of its own
    bits = image(tmp_path / "fax.png", page, "PNG")
    target = tmp_path / "part.pdf"
    await page_composer.compose([source, bits], [PagePick(0, 1), PagePick(1, 1)], target)
    with pikepdf.open(target) as pdf:
        colour = pdf.pages[0].Resources.XObject.Im0
        fax = pdf.pages[1].Resources.XObject.Im0
        assert isinstance(colour, pikepdf.Stream) and isinstance(fax, pikepdf.Stream)
        assert "/Rotate" not in pdf.pages[0].obj
        assert colour.Filter == pikepdf.Name.FlateDecode
        shown = pikepdf.PdfImage(colour).as_pil_image()
        assert shown.mode == "RGB"
        assert shown.getpixel((12, 0)) == (255, 0, 0)  # mirrored back
        assert shown.getpixel((0, 0)) == (255, 255, 255)  # transparent on white
        assert int(fax.BitsPerComponent) == 1
        read = pikepdf.PdfImage(fax).as_pil_image().convert("L")
        assert [read.getpixel(spot) for spot in ((12, 6), (12, 5), (0, 6))] == [0, 255, 255]


@pytest.mark.parametrize(
    ("name", "data", "media_type"),
    [
        ("mail.eml", b"From: a@example.org\r\n\r\nHello\r\n", media_types.EML),
        ("broken.png", b"\x89PNG\r\n\x1a\nbroken", media_types.PNG),
    ],
)
async def test_what_it_cannot_read_is_unprocessable(
    page_composer: PikepdfPageComposer, tmp_path: Path, name: str, data: bytes, media_type: str
) -> None:
    path = tmp_path / name
    path.write_bytes(data)
    with pytest.raises(UnprocessableDocumentError):
        await page_composer.count_pages(PageSource(path, media_type))
    with pytest.raises(UnprocessableDocumentError):
        await page_composer.compose(
            [PageSource(path, media_type)], [PagePick(0, 1)], tmp_path / "x.pdf"
        )


async def test_an_encrypted_pdf_is_unprocessable(
    page_composer: PikepdfPageComposer, tmp_path: Path
) -> None:
    pdf = pikepdf.new()
    pdf.add_blank_page()
    out = io.BytesIO()
    pdf.save(out, encryption=pikepdf.Encryption(owner="owner", user="user"))
    path = tmp_path / "locked.pdf"
    path.write_bytes(out.getvalue())
    with pytest.raises(UnprocessableDocumentError, match="encrypted"):
        await page_composer.count_pages(PageSource(path, media_types.PDF))
