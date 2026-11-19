"""What Lekto takes from a mail: the id of a mail's record."""

import io
import os
from uuid import UUID

from PIL import Image

from lekto.core.domain.ids import MailboxId, new_id
from lekto.core.domain.mail_intake import SMALL_IMAGE, kept, record_id
from lekto.core.domain.mail_message import MailPart


def test_a_mail_has_the_same_record_id_at_every_fetch() -> None:
    mailbox = MailboxId(new_id())
    assert record_id(mailbox, "INBOX", 7, 42) == record_id(mailbox, "INBOX", 7, 42)


def test_a_record_id_is_the_same_in_every_version_of_lekto() -> None:
    # Ids computed before the repository moved (12.11.2026) stay what they were.
    mailbox = MailboxId(UUID("00000000-0000-0000-0000-000000000001"))
    assert record_id(mailbox, "INBOX", 1700000000, 42) == UUID(
        "3f25cb33-b1c3-567d-9dba-43a6d4e13817"
    )


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


def noise(width: int, height: int) -> bytes:
    """A PNG of `width` by `height` pixels that does not compress: as large as its pixels."""
    buffer = io.BytesIO()
    Image.frombytes("RGB", (width, height), os.urandom(width * height * 3)).save(buffer, "PNG")
    return buffer.getvalue()


def test_small_images_are_left_out_by_their_bytes_or_their_edges() -> None:
    """A logo or a signature: under 20 KB, or with no edge of 300 pixels ([[mail-intake]];
    DB-09)."""
    logo, picture = noise(200, 80), noise(300, 40)
    assert len(logo) > SMALL_IMAGE and len(picture) > SMALL_IMAGE
    assert not kept(MailPart("logo.png", "image/png", logo))
    assert kept(MailPart("scan.png", "image/png", picture))
    assert not kept(MailPart("tiny.png", "image/png", noise(20, 20)))
    assert kept(MailPart("bill.pdf", "application/pdf", b"%PDF-1.7"))
    unknown = b"\x00" * SMALL_IMAGE  # no head that says: by its bytes alone
    assert kept(MailPart("scan.tif", "image/tiff", unknown))
