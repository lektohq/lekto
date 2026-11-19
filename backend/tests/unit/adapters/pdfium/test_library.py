"""What the text layer of a PDF tells before OCR."""

import gc
from pathlib import Path

import pypdfium2
import pypdfium2.raw
import pytest

from lekto.adapters.outbound.pdfium import has_unreadable_text
from lekto.adapters.outbound.pdfium.library import LOCK, unreadable_share
from lekto.adapters.outbound.pdfium.pages import render
from lekto.adapters.outbound.zxing.reader import read_codes
from lekto.core.domain import media_types
from tests.builders import SAMPLES


@pytest.mark.parametrize(
    ("text", "share"),
    [
        ("", 0.0),
        (" \n\t", 0.0),
        ("Rechnung 4711", 0.0),
        ("\x17\x1b5\x1b", 0.75),
        ("ab�", 0.5),
    ],
)
def test_the_share_of_characters_that_map_to_nothing(text: str, share: float) -> None:
    assert unreadable_share(text) == share


def test_a_font_without_a_character_map_makes_the_text_unreadable() -> None:
    assert has_unreadable_text(SAMPLES / "unmapped.pdf")
    for sample in ("text.pdf", "printout.pdf", "scan.pdf", "blank.pdf", "damaged.pdf"):
        assert not has_unreadable_text(SAMPLES / sample), sample


def test_bitmaps_are_released_under_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every use of PDFium goes through `LOCK`, releasing a page's bitmap too, by the page
    renderer and by the code reader (AD-07)."""
    held: list[bool] = []
    destroy = pypdfium2.raw.FPDFBitmap_Destroy

    def recorded(bitmap: object) -> None:
        held.append(LOCK.locked())
        destroy(bitmap)

    monkeypatch.setattr(pypdfium2.raw, "FPDFBitmap_Destroy", recorded)
    render(SAMPLES / "codes.pdf", media_types.PDF, tmp_path, 400, 200)
    read_codes(SAMPLES / "codes.pdf", max_pages=None)
    gc.collect()
    assert len(held) >= 2
    assert all(held)
