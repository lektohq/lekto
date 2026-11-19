"""Images for the tests whose size, not their content, matters."""

import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image

import lekto.adapters.outbound.imaging


def stated_png(path: Path, width: int, height: int) -> Path:
    """A PNG whose header states `width` by `height` grey pixels, with a few bytes of data after
    it: Pillow opens it, and only decoding it fails."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + data))
        return struct.pack(">I", len(data)) + kind + data + crc

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    signature = b"\x89PNG\r\n\x1a\n"
    data = zlib.compress(b"\x00" * 64)
    path.write_bytes(
        signature + chunk(b"IHDR", header) + chunk(b"IDAT", data) + chunk(b"IEND", b"")
    )
    return path


def too_large_on_page_two(path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A TIFF whose second page has 1.1 megapixels, over the limit lowered here to one."""
    monkeypatch.setattr(lekto.adapters.outbound.imaging, "MAX_DOCUMENT_PIXELS", 1_000_000)
    Image.new("L", (100, 100), 255).save(
        path,
        save_all=True,
        append_images=[Image.new("L", (1100, 1000), 255)],
        compression="tiff_lzw",
    )
    return path
