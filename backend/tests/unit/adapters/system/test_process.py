import asyncio
import json
import subprocess
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


async def test_every_child_is_limited_from_its_first_instruction() -> None:
    """Many children at once on a busy machine, each allocating at once: a limit set from the
    parent after the start came too late for some of them."""
    children = [
        run_process(
            [sys.executable, "-I", "-c", ALLOCATE, "300"],
            timeout=timedelta(seconds=60),
            memory=256 * MiB,
        )
        for _ in range(12)
    ]
    for completed in await asyncio.gather(*children):
        assert completed.returncode != 0
        assert "MemoryError" in completed.stderr


LOWER_HARD_LIMIT = """
import asyncio, resource, sys
SHOW_HARD_LIMIT = "import resource; print(resource.getrlimit(resource.RLIMIT_AS)[1])"
from datetime import timedelta
from lekto.adapters.outbound.system import run_process
hard, wanted = int(sys.argv[1]), int(sys.argv[2])
resource.setrlimit(resource.RLIMIT_AS, (hard, hard))
async def main():
    completed = await run_process(
        [sys.executable, "-I", "-c", SHOW_HARD_LIMIT],
        timeout=timedelta(seconds=30),
        memory=wanted,
    )
    print(completed.returncode, completed.stdout.strip())
asyncio.run(main())
"""


def test_a_lower_hard_limit_of_the_process_is_the_childs() -> None:
    """A container's `--ulimit as=` below `LEKTO_CHILD_MAX_MEMORY`: the child gets that one
    (raising it failed, and the child ran on without a limit, unsupervised)."""
    hard, wanted = 2048 * MiB, 4096 * MiB
    ran = subprocess.run(
        [sys.executable, "-c", LOWER_HARD_LIMIT, str(hard), str(wanted)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.split() == ["0", str(hard)]


async def test_a_program_that_is_not_there_is_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        await run_process(["lekto-no-such-program"], timeout=timedelta(seconds=5), memory=MiB)
