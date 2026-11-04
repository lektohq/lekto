"""Folder names in modified UTF-7 and the lines of a LIST answer."""

import pytest

from lekto.adapters.outbound.imap.names import decode, encode, listed, quoted


@pytest.mark.parametrize(
    ("text", "wire"),
    [
        ("INBOX", b"INBOX"),
        ("Belege & Co", b"Belege &- Co"),
        ("Bestätigungen", b"Best&AOQ-tigungen"),
        ("Grüße/Übersicht", b"Gr&APwA3w-e/&ANw-bersicht"),
        ("日本語", b"&ZeVnLIqe-"),
    ],
)
def test_round_trip(text: str, wire: bytes) -> None:
    assert encode(text) == wire
    assert decode(wire) == text


def test_quoted_escapes() -> None:
    assert quoted('a "b" \\ c') == b'"a \\"b\\" \\\\ c"'


def test_listed_reads_names_flags_and_literals() -> None:
    entries: list[bytes | tuple[bytes, bytes] | None] = [
        b'(\\HasNoChildren) "/" "INBOX"',
        b'(\\HasChildren \\Noselect) "/" "[Gmail]"',
        b'(\\HasNoChildren) "." Archiv',
        (b'(\\HasNoChildren) "/" {17}', b"Best&AOQ-tigungen"),
        b'(\\HasNoChildren) NIL "Say \\"hi\\""',
        None,
    ]
    assert listed(entries) == [
        ("INBOX", frozenset({"\\hasnochildren"})),
        ("[Gmail]", frozenset({"\\haschildren", "\\noselect"})),
        ("Archiv", frozenset({"\\hasnochildren"})),
        ("Bestätigungen", frozenset({"\\hasnochildren"})),
        ('Say "hi"', frozenset({"\\hasnochildren"})),
    ]
