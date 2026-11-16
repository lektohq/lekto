"""Folder names in modified UTF-7 and the lines of a LIST answer."""

import pytest

from lekto.adapters.outbound.imap.names import decode, encode, listed, quoted, shown


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
    assert [(item.name, item.flags) for item in listed(entries)] == [
        ("INBOX", frozenset({"\\hasnochildren"})),
        ("[Gmail]", frozenset({"\\haschildren", "\\noselect"})),
        ("Archiv", frozenset({"\\hasnochildren"})),
        ("Bestätigungen", frozenset({"\\hasnochildren"})),
        ('Say "hi"', frozenset({"\\hasnochildren"})),
    ]


def test_a_name_sent_against_the_standard_is_shown_and_kept_as_sent() -> None:
    """A server sends UTF-8, or a bare `&`: the name is shown as UTF-8, the list stays whole,
    and the bytes as sent address the folder."""
    raw = "Entwürfe".encode()
    entries: list[bytes | tuple[bytes, bytes] | None] = [
        b'(\\HasNoChildren) "/" "INBOX"',
        b'(\\HasNoChildren) "/" "R&D"',
        b'(\\HasNoChildren) "/" "' + raw + b'"',
        b'(\\HasNoChildren) "/" "Best&AOQ-tigungen"',
        b'(\\HasNoChildren) "/" "\xff&"',
    ]
    assert [(item.name, item.raw) for item in listed(entries)] == [
        ("INBOX", b"INBOX"),
        ("R&D", b"R&D"),
        ("Entwürfe", raw),
        ("Bestätigungen", b"Best&AOQ-tigungen"),
        ("\ufffd&", b"\xff&"),
    ]
    assert shown(b"Gr&APwA3w-e") == "Grüße"
