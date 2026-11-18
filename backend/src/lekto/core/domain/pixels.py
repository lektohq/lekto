"""Width and height of a raster image, read from its head without decoding it: PNG, GIF,
JPEG and WebP, the kinds mails carry as logos and signatures. Plain Python: the core decides
by them which images of a mail are too small to take (`mail_intake.kept`; DB-09)."""

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG_FRAMES = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
"""The JPEG markers that start a frame (SOF0 to SOF15), whose segment names the size."""


def pixels(data: bytes) -> tuple[int, int] | None:
    """Width and height of the image `data`; None for another kind or a head that does not
    say."""
    if data.startswith(_PNG) and data[12:16] == b"IHDR":
        return _size(int.from_bytes(data[16:20]), int.from_bytes(data[20:24]))
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return _size(int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little"))
    if data.startswith(b"\xff\xd8"):
        return _jpeg(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _webp(data)
    return None


def _jpeg(data: bytes) -> tuple[int, int] | None:
    """The size the first frame names, segment by segment from the start."""
    at = 2
    while at + 4 <= len(data):
        if data[at] != 0xFF:
            return None
        marker = data[at + 1]
        if marker == 0xFF:  # a fill byte
            at += 1
            continue
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:  # no segment of its own
            at += 2
            continue
        if marker in (0xD9, 0xDA):  # the end, or a scan before any frame
            return None
        if marker in _JPEG_FRAMES:
            if at + 9 > len(data):
                return None
            height = int.from_bytes(data[at + 5 : at + 7])
            return _size(int.from_bytes(data[at + 7 : at + 9]), height)
        length = int.from_bytes(data[at + 2 : at + 4])
        if length < 2:
            return None
        at += 2 + length
    return None


def _webp(data: bytes) -> tuple[int, int] | None:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:  # lossy
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        return _size(width, int.from_bytes(data[28:30], "little") & 0x3FFF)
    if chunk == b"VP8L" and len(data) >= 25:  # lossless: two numbers of 14 bits
        bits = int.from_bytes(data[21:25], "little")
        return _size((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    if chunk == b"VP8X" and len(data) >= 30:  # extended: two numbers of 24 bits
        width = int.from_bytes(data[24:27], "little") + 1
        return _size(width, int.from_bytes(data[27:30], "little") + 1)
    return None


def _size(width: int, height: int) -> tuple[int, int] | None:
    return (width, height) if width and height else None
