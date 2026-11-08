"""What Lekto takes from a mail: the id of a mail's record."""

from lekto.core.domain.ids import MailboxId, new_id
from lekto.core.domain.mail_intake import record_id


def test_a_mail_has_the_same_record_id_at_every_fetch() -> None:
    mailbox = MailboxId(new_id())
    assert record_id(mailbox, "INBOX", 7, 42) == record_id(mailbox, "INBOX", 7, 42)


def test_each_part_of_where_a_mail_lies_makes_another_record_id() -> None:
    mailbox = MailboxId(new_id())
    ids = {
        record_id(mailbox, "INBOX", 7, 42),
        record_id(mailbox, "INBOX", 7, 43),
        record_id(mailbox, "INBOX", 8, 42),
        record_id(mailbox, "Archiv", 7, 42),
        record_id(MailboxId(new_id()), "INBOX", 7, 42),
        record_id(mailbox, "INBOX 7", 4, 2),  # the parts do not run into one another
    }
    assert len(ids) == 6
