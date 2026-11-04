"""A mailbox's settings: checked as a whole, a failed change leaves it as it was."""

from datetime import date, timedelta

import pytest

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import UserId, new_id
from lekto.core.domain.mail import (
    Fallback,
    FetchStart,
    Mailbox,
    MailboxChanges,
    MailboxStatus,
    MailSecurity,
)
from tests.builders import HOUR, NOW


def _mailbox() -> Mailbox:
    return Mailbox.create(
        name="  Household ",
        host=" imap.example.test ",
        port=993,
        security=MailSecurity.TLS,
        username=" household@example.test",
        encrypted_password=b"sealed",
        folders=("INBOX", " Rechnungen ", "INBOX"),
        now=NOW,
    )


def test_create_trims_and_keeps_the_defaults() -> None:
    mailbox = _mailbox()
    assert (mailbox.name, mailbox.host, mailbox.username) == (
        "Household",
        "imap.example.test",
        "household@example.test",
    )
    assert mailbox.folders == ("INBOX", "Rechnungen")
    assert mailbox.interval == timedelta(minutes=5)
    assert (mailbox.start, mailbox.fallback, mailbox.enabled) == (
        FetchStart.SINCE_SETUP,
        Fallback.NOTHING,
        True,
    )
    assert mailbox.status == MailboxStatus()


@pytest.mark.parametrize(
    "changes",
    [
        MailboxChanges(name=" "),
        MailboxChanges(name="x" * 101),
        MailboxChanges(host="imap example"),
        MailboxChanges(port=70000),
        MailboxChanges(username=""),
        MailboxChanges(folders=()),
        MailboxChanges(folders=("INBOX", " ")),
        MailboxChanges(folders=tuple(f"f{index}" for index in range(21))),
        MailboxChanges(interval=timedelta(seconds=30)),
        MailboxChanges(interval=timedelta(days=2)),
        MailboxChanges(start=FetchStart.SINCE_DATE),
        MailboxChanges(fallback=Fallback.EVERYTHING),
    ],
)
def test_a_bad_change_is_refused_and_changes_nothing(changes: MailboxChanges) -> None:
    mailbox = _mailbox()
    before = vars(mailbox).copy()
    with pytest.raises(ValidationError):
        mailbox.change(changes, now=NOW + HOUR)
    assert vars(mailbox) == before


def test_parts_go_together() -> None:
    mailbox = _mailbox()
    person = UserId(new_id())
    mailbox.change(
        MailboxChanges(start=FetchStart.SINCE_DATE, since=date(2026, 1, 1)), now=NOW + HOUR
    )
    mailbox.change(
        MailboxChanges(fallback=Fallback.EVERYTHING, fallback_user_id=person), now=NOW + HOUR
    )
    assert (mailbox.since, mailbox.fallback_user_id, mailbox.updated_at) == (
        date(2026, 1, 1),
        person,
        NOW + HOUR,
    )
    mailbox.change(MailboxChanges(name="Only the name"), now=NOW)
    assert (mailbox.since, mailbox.fallback_user_id) == (date(2026, 1, 1), person)
    mailbox.change(MailboxChanges(start=FetchStart.UNREAD, fallback=Fallback.NOTHING), now=NOW)
    assert (mailbox.since, mailbox.fallback_user_id) == (None, None)
    mailbox.change(MailboxChanges(name="Only the name"), now=NOW)
    assert mailbox.start is FetchStart.UNREAD


def test_recording_a_fetch_does_not_touch_the_settings() -> None:
    mailbox = _mailbox()
    mailbox.record(MailboxStatus(last_attempt_at=NOW + HOUR, mails=2))
    assert mailbox.updated_at == NOW
    assert mailbox.status.mails == 2
