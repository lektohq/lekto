"""The PDFium page renderer passes the contract, keeps the widths and reads images."""

from pathlib import Path

import pypdfium2
import pytest
from PIL import ExifTags, Image

from lekto.adapters.outbound.pdfium import PdfiumPageRenderer
from lekto.adapters.outbound.pdfium.pages import MAX_EDGE, page_scale
from lekto.core.domain import media_types
from tests.builders import SAMPLES
from tests.contracts.processing import PageRendererContract


@pytest.fixture
def page_renderer() -> PdfiumPageRenderer:
    return PdfiumPageRenderer()


class TestPdfiumPageRenderer(PageRendererContract):
    pass


def size(path: Path) -> tuple[str | None, int, int]:
    with Image.open(path) as image:
        return image.format, image.width, image.height


async def test_pages_and_preview_have_the_configured_widths(tmp_path: Path) -> None:
    renderer = PdfiumPageRenderer(width=300, preview_width=100)
    rendered = await renderer.render_pages(
        SAMPLES / "text.pdf", media_type=media_types.PDF, target=tmp_path
    )
    assert rendered.pages == 1 and rendered.renderer.startswith("pdfium ")
    assert size(tmp_path / "1.webp") == ("WEBP", 300, round(300 * 842 / 595))  # A4 portrait
    assert size(tmp_path / "preview.webp") == ("WEBP", 100, round(100 * 842 / 595))


async def test_every_frame_of_a_tiff_is_a_page(tmp_path: Path) -> None:
    rendered = await PdfiumPageRenderer(width=300).render_pages(
        SAMPLES / "pages.tiff", media_type=media_types.TIFF, target=tmp_path
    )
    assert rendered.pages == 2 and rendered.renderer.startswith("pillow ")
    assert {path.name for path in tmp_path.iterdir()} == {"1.webp", "2.webp", "preview.webp"}
    assert size(tmp_path / "2.webp")[1] == 300


async def test_a_small_image_keeps_its_size_and_transparency_turns_white(tmp_path: Path) -> None:
    rendered = await PdfiumPageRenderer(width=1200).render_pages(
        SAMPLES / "screenshot.png", media_type=media_types.PNG, target=tmp_path
    )
    assert rendered.pages == 1
    with Image.open(tmp_path / "1.webp") as image:
        assert (image.width, image.height) == (1000, 600)  # not scaled up
        assert image.convert("RGB").getpixel((0, 0)) == (255, 255, 255)


async def test_a_file_that_is_no_image_is_unprocessable(tmp_path: Path) -> None:
    from lekto.core.domain.errors import UnprocessableDocumentError

    with pytest.raises(UnprocessableDocumentError, match="cannot be read"):
        await PdfiumPageRenderer().render_pages(
            SAMPLES / "damaged.pdf", media_type=media_types.JPEG, target=tmp_path
        )
    assert list(tmp_path.iterdir()) == []


async def test_a_later_frame_over_the_limit_is_unprocessable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lekto.core.domain.errors import UnprocessableDocumentError

    source = tmp_path / "bomb.tiff"
    Image.new("L", (100, 100), 255).save(
        source,
        save_all=True,
        append_images=[Image.new("L", (300, 300), 255)],
        compression="tiff_lzw",  # an uncompressed page is not checked by Pillow
    )
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 20_000)  # page two is over it
    target = tmp_path / "pages"
    target.mkdir()
    with pytest.raises(UnprocessableDocumentError, match="cannot be read"):
        await PdfiumPageRenderer().render_pages(source, media_type=media_types.TIFF, target=target)


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (595, 842, 2),  # A4: 1190 pixels wide, as before
        (612, 792, 1200 / 612),  # Letter: rendered at the page width, not larger
        (14_400, 14_400, 1200 / 14_400),  # the largest page a PDF may give
        (600, 14_400, MAX_EDGE / 14_400),  # very high: the long edge holds it
        (0, 0, 2),  # a page without a size
    ],
)
def test_the_scale_follows_the_size_of_the_page(
    width: float, height: float, expected: float
) -> None:
    assert page_scale(width, height, 1200) == pytest.approx(expected)


async def test_a_huge_page_renders_at_the_page_width(tmp_path: Path) -> None:
    """A file of a few hundred bytes with a page of 14 400 points a side: rendered at a fixed
    scale it asked for 3.3 GB."""
    source = tmp_path / "huge.pdf"
    document = pypdfium2.PdfDocument.new()
    document.new_page(14_400, 14_400)
    document.new_page(600, 14_400)
    document.save(source)
    document.close()
    target = tmp_path / "pages"
    target.mkdir()
    rendered = await PdfiumPageRenderer().render_pages(
        source, media_type=media_types.PDF, target=target
    )
    assert rendered.pages == 2
    assert size(target / "1.webp") == ("WEBP", 1200, 1200)
    assert size(target / "2.webp")[2] <= MAX_EDGE


async def test_a_photo_turned_by_its_exif_renders_upright_at_the_page_width(
    tmp_path: Path,
) -> None:
    """Made small first and turned then: the width that counts is the upright one."""
    source = tmp_path / "photo.jpg"
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # taken on its side: turned by a quarter
    Image.new("RGB", (4000, 3000), (120, 90, 60)).save(source, "JPEG", exif=exif)
    target = tmp_path / "pages"
    target.mkdir()
    await PdfiumPageRenderer().render_pages(source, media_type=media_types.JPEG, target=target)
    assert size(target / "1.webp") == ("WEBP", 1200, 1600)


async def test_a_palette_image_with_transparency_turns_white_when_made_small(
    tmp_path: Path,
) -> None:
    source = tmp_path / "logo.png"
    image = Image.new("P", (3000, 1500), 0)
    image.putpalette([0, 0, 0, 200, 30, 30] + [0, 0, 0] * 254)
    image.paste(1, (1500, 0, 3000, 1500))
    image.save(source, "PNG", transparency=0)
    target = tmp_path / "pages"
    target.mkdir()
    await PdfiumPageRenderer().render_pages(source, media_type=media_types.PNG, target=target)
    with Image.open(target / "1.webp") as page:
        rgb = page.convert("RGB")
        assert rgb.size == (1200, 600)
        assert rgb.getpixel((100, 300)) == (255, 255, 255)  # transparent: white paper
        pixel = rgb.getpixel((1100, 300))
        assert isinstance(pixel, tuple)
        red, green, blue = pixel
        assert red > 150 and green < 80 and blue < 80


async def test_a_bilevel_scan_is_made_small_in_grey(tmp_path: Path) -> None:
    source = tmp_path / "fax.tiff"
    Image.new("1", (2480, 3508), 1).save(source, "TIFF", compression="group4")
    target = tmp_path / "pages"
    target.mkdir()
    await PdfiumPageRenderer().render_pages(source, media_type=media_types.TIFF, target=target)
    assert size(target / "1.webp") == ("WEBP", 1200, round(3508 * 1200 / 2480))
