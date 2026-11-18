"""Removing the temporary files of an upload (RA-05)."""

import asyncio
import hashlib
from pathlib import Path

from lekto.adapters.inbound.rest.upload import ReceivedFile, Upload, Uploads
from lekto.core.domain.documents import Sha256
from lekto.core.services.pipeline import IncomingFile


def received(path: Path) -> ReceivedFile:
    path.write_bytes(b"%PDF-1.7")
    digest = Sha256(hashlib.sha256(b"%PDF-1.7").hexdigest())
    return ReceivedFile(IncomingFile(path=path, sha256=digest, size=8), path.name)


async def gone(paths: list[Path]) -> bool:
    for _ in range(100):
        if not any(path.exists() for path in paths):
            return True
        await asyncio.sleep(0.01)
    return False


async def test_a_cancelled_removal_leaves_no_file_behind(tmp_path: Path) -> None:
    """The request ends while it waits for the removal: the files go all the same."""
    paths = [tmp_path / f"{n}.pdf" for n in range(3)]
    uploads = Uploads([received(path) for path in paths], {})
    removal = asyncio.create_task(uploads.remove())
    await asyncio.sleep(0)
    removal.cancel()
    assert await gone(paths)


async def test_an_upload_removes_its_file(tmp_path: Path) -> None:
    item = received(tmp_path / "one.pdf")
    await Upload(item.file, item.filename, {}).remove()
    assert not item.file.path.exists()
