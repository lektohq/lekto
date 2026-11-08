"""Images are prepared for OCRmyPDF: a plausible resolution, no transparency, all pages."""

import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageSequence

from lekto.adapters.outbound.ocrmypdf.engine import image_dpi, prepare_image
from lekto.core.domain.errors import UnprocessableDocumentError
from tests.builders import SAMPLES


@pytest.mark.parametrize(
    ("size", "stated", "expected"),
    [
        ((2480, 3508), (300, 300), 300),  # A4 at 300 dpi: kept
        ((1200, 900), (72, 72), 72),  # 16.7 inches at 72 dpi: plausible, kept
        ((4032, 3024), (72, 72), 345),  # phone photo claiming 72 dpi: 56 inches
        ((1000, 1300), None, 111),  # no resolution
        ((600, 300), (600, 600), 51),  # one inch wide: too small
    ],
)
def test_images_get_a_plausible_resolution(
    size: tuple[int, int], stated: tuple[int, int] | None, expected: int
) -> None:
    assert image_dpi(size, stated) == expected


def test_a_usable_image_is_passed_on_as_it_is(tmp_path: Path) -> None:
    prepared = tmp_path / "prepared.tiff"
    assert prepare_image(SAMPLES / "lowres.jpg", prepared) == (SAMPLES / "lowres.jpg", 72)
    assert not prepared.exists()


def test_transparency_is_put_on_white(tmp_path: Path) -> None:
    path, dpi = prepare_image(SAMPLES / "screenshot.png", tmp_path / "prepared.tiff")
    assert (path, dpi) == (tmp_path / "prepared.tiff", 150)
    with Image.open(path) as image:
        assert image.mode == "RGB"
        assert image.getpixel((0, 0)) == (255, 255, 255)


def test_all_pages_of_a_tiff_are_kept(tmp_path: Path) -> None:
    path, _ = prepare_image(SAMPLES / "pages.tiff", tmp_path / "prepared.tiff")
    with Image.open(path) as image:
        assert len(list(ImageSequence.Iterator(image))) == 2


def test_cmyk_becomes_rgb(tmp_path: Path) -> None:
    source = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (800, 1100), (0, 0, 0, 0)).save(source, dpi=(100, 100))
    path, _ = prepare_image(source, tmp_path / "prepared.tiff")
    with Image.open(path) as image:
        assert image.mode == "RGB"


def test_an_unreadable_image_is_unprocessable(tmp_path: Path) -> None:
    source = tmp_path / "broken.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    with pytest.raises(UnprocessableDocumentError, match="cannot be read"):
        prepare_image(source, tmp_path / "prepared.tiff")


def bomb_on_page_two(path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A TIFF whose second page is over Pillow's limit (lowered here, so the page stays small)."""
    Image.new("L", (100, 100), 255).save(
        path,
        save_all=True,
        append_images=[Image.new("L", (300, 300), 255)],
        compression="tiff_lzw",  # an uncompressed page is not checked by Pillow
    )
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 20_000)
    return path


def test_a_page_over_the_limit_after_the_first_is_unprocessable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = bomb_on_page_two(tmp_path / "bomb.tiff", monkeypatch)
    with pytest.raises(UnprocessableDocumentError, match="cannot be read"):
        prepare_image(source, tmp_path / "prepared.tiff")


_PEAK = """
import resource, sys
import subprocess
import sys
from pathlib import Path
from lekto.adapters.outbound.ocrmypdf.engine import prepare_image
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
prepare_image(Path(sys.argv[1]), Path(sys.argv[2]))
print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before)
"""


@pytest.mark.skipif(sys.platform != "linux", reason="ru_maxrss counts KiB on Linux")
def test_the_pages_of_a_fax_are_prepared_one_at_a_time(tmp_path: Path) -> None:
    # 40 pages of A4 at 300 dpi, bilevel and compressed to almost nothing: Pillow holds a page
    # at a byte per pixel, 8.7 MB, so all of them at once would take some 350 MB.
    page = Image.new("1", (2480, 3508), 1)
    source = tmp_path / "fax.tiff"
    page.save(
        source, save_all=True, append_images=[page] * 39, compression="group4", dpi=(300, 300)
    )
    prepared = tmp_path / "prepared.tiff"
    grown = subprocess.run(
        [sys.executable, "-c", _PEAK, str(source), str(prepared)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert int(grown) < 100_000  # KiB
    with Image.open(prepared) as image:
        assert getattr(image, "n_frames", 1) == 40
