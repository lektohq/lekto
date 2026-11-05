"""What a mail is marked with: importance from its header, keywords and flag from IMAP."""

import pytest

from lekto.core.domain.mail_message import read_mail
from lekto.core.domain.mail_traits import (
    FlagColor,
    Importance,
    MailMarks,
    flag_bits,
    importance_of,
    is_keyword,
    shown_keywords,
)
from tests.mails import plain_mail


@pytest.mark.parametrize(
    ("headers", "importance"),
    [
        ({}, Importance.NORMAL),
        ({"importance": "High"}, Importance.HIGH),
        ({"importance": "low"}, Importance.LOW),
        ({"x-priority": "1 (Highest)"}, Importance.HIGH),
        ({"x-priority": "2"}, Importance.HIGH),
        ({"x-priority": "3 (Normal)"}, Importance.NORMAL),
        ({"x-priority": "5 (Lowest)"}, Importance.LOW),
        ({"priority": "urgent"}, Importance.HIGH),
        ({"priority": "non-urgent"}, Importance.LOW),
        ({"x-msmail-priority": "High"}, Importance.HIGH),
        ({"importance": "normal", "x-priority": "1"}, Importance.HIGH),
    ],
)
def test_the_importance_a_header_gives(headers: dict[str, str], importance: Importance) -> None:
    assert importance_of(headers) is importance


def test_a_read_mail_knows_its_importance() -> None:
    data = plain_mail("Dringend").replace(b"Subject:", b"X-Priority: 1\r\nSubject:", 1)
    assert read_mail(data).importance is Importance.HIGH
    assert read_mail(plain_mail()).importance is Importance.NORMAL


@pytest.mark.parametrize(
    ("bits", "color"),
    [
        ((), FlagColor.RED),
        (("$MailFlagBit0",), FlagColor.ORANGE),
        (("$MailFlagBit1",), FlagColor.YELLOW),
        (("$MailFlagBit0", "$MailFlagBit1"), FlagColor.GREEN),
        (("$MailFlagBit2",), FlagColor.BLUE),
        (("$mailflagbit0", "$MailFlagBit2"), FlagColor.PURPLE),
        (("$MailFlagBit1", "$MailFlagBit2"), FlagColor.GRAY),
        (("$MailFlagBit0", "$MailFlagBit1", "$MailFlagBit2"), FlagColor.RED),
    ],
)
def test_the_colour_of_a_flag(bits: tuple[str, ...], color: FlagColor) -> None:
    marks = MailMarks.of_flags(["\\Flagged", "\\Seen", *bits, "Lekto"])
    assert (marks.flag, marks.keywords) == (color, ("Lekto",))


@pytest.mark.parametrize("color", list(FlagColor))
def test_the_bits_of_a_colour_read_back(color: FlagColor) -> None:
    assert MailMarks.of_flags(["\\Flagged", *flag_bits(color)]).flag is color


def test_bits_without_a_flag_are_no_flag() -> None:
    assert MailMarks.of_flags(["$MailFlagBit2", "\\Seen"]) == MailMarks()
    assert MailMarks.of_flags(["lekto"]).has("LEKTO")


def test_the_keywords_to_choose() -> None:
    flags = ["\\Seen", "\\*", "$Forwarded", "NotJunk", "$MailFlagBit0", "Lekto", "$label1", "b"]
    assert shown_keywords(flags) == ("$label1", "b", "Lekto")


@pytest.mark.parametrize(
    ("value", "valid"),
    [("Lekto", True), ("$label1", True), ("two words", False), ("Größe", False), ("a]", False)],
)
def test_a_keyword_imap_can_carry(value: str, valid: bool) -> None:
    assert is_keyword(value) is valid
