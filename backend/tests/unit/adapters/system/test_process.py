import json
import sys
from datetime import timedelta

import pytest

from lekto.adapters.outbound.system import run_process

SHOW_ENVIRONMENT = (
    "import json, os; "
    "print(json.dumps({k: v for k, v in os.environ.items() "
    "if k.startswith('LEKTO_') or k == 'PATH'}))"
)


async def test_a_child_gets_no_lekto_settings_but_what_the_caller_adds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OCRmyPDF, Ghostscript and Tesseract process documents of unknown origin; the secret key
    and the credentials stay out of their reach."""
    monkeypatch.setenv("LEKTO_SECRET_KEY", "the-key")
    monkeypatch.setenv("LEKTO_DB_PASSWORD_FILE", "/run/secrets/db")
    completed = await run_process(
        [sys.executable, "-I", "-c", SHOW_ENVIRONMENT],
        timeout=timedelta(seconds=30),
        env={"LEKTO_OCR_VISION": "{}"},
    )
    assert completed.returncode == 0, completed.stderr
    seen = json.loads(completed.stdout)
    assert "LEKTO_SECRET_KEY" not in seen
    assert "LEKTO_DB_PASSWORD_FILE" not in seen
    assert seen["LEKTO_OCR_VISION"] == "{}"
    assert "PATH" in seen


async def test_a_child_that_takes_too_long_is_killed() -> None:
    with pytest.raises(TimeoutError, match="did not finish"):
        await run_process(
            [sys.executable, "-I", "-c", "import time; time.sleep(30)"],
            timeout=timedelta(milliseconds=200),
        )


async def test_the_end_of_the_error_output_is_kept_as_far_as_asked() -> None:
    script = "import sys; sys.stderr.write('a' * 5000 + 'b' * 5000)"
    default = await run_process([sys.executable, "-c", script], timeout=timedelta(seconds=30))
    assert default.stderr == "b" * 4000
    more = await run_process(
        [sys.executable, "-c", script], timeout=timedelta(seconds=30), tail=8000
    )
    assert more.stderr == "a" * 3000 + "b" * 5000


ALLOCATE = "import sys; block = bytearray(int(sys.argv[1]) * 1024 * 1024); print(len(block))"
LIMIT_OF_A_GRANDCHILD = (
    "import subprocess, sys; "
    "print(subprocess.run([sys.executable, '-I', '-c', "
    "'import resource; print(resource.getrlimit(resource.RLIMIT_AS)[0])'], "
    "capture_output=True, text=True).stdout.strip())"
)
MiB = 1024 * 1024


async def test_a_child_takes_no_more_memory_than_its_limit() -> None:
    """A document built to make Ghostscript or Tesseract allocate without end fails its child,
    not the worker."""
    small = await run_process(
        [sys.executable, "-I", "-c", ALLOCATE, "16"],
        timeout=timedelta(seconds=30),
        memory=512 * MiB,
    )
    assert small.returncode == 0, small.stderr
    large = await run_process(
        [sys.executable, "-I", "-c", ALLOCATE, "1024"],
        timeout=timedelta(seconds=30),
        memory=512 * MiB,
    )
    assert large.returncode != 0
    assert "MemoryError" in large.stderr


async def test_the_programs_a_child_starts_inherit_its_limit() -> None:
    """OCRmyPDF starts Ghostscript and Tesseract: they get the same limit."""
    completed = await run_process(
        [sys.executable, "-I", "-c", LIMIT_OF_A_GRANDCHILD],
        timeout=timedelta(seconds=30),
        memory=512 * MiB,
    )
    assert completed.returncode == 0, completed.stderr
    assert int(completed.stdout) == 512 * MiB
