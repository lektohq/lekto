"""Run a program in a process of its own, with a time limit.

Compute-heavy steps (OCR, parsing) run in child processes, so the event loop stays free and a
step that hangs can be stopped. The child starts a new session; on timeout or cancellation the
whole process group is killed, including the programs it started (Tesseract, Ghostscript).

A child gets the process's environment without Lekto's own settings (`LEKTO_*`): they carry the
secret key and the database and storage credentials, and OCRmyPDF, Ghostscript and Tesseract,
which process documents of unknown origin, have no use for them. What a child needs beyond that
(the vision plugin's configuration) the caller passes in `env`.

A child may get a limit of its address space (`memory`, `LEKTO_CHILD_MAX_MEMORY`), which the
programs it starts inherit: a document built to make them allocate without end fails the child,
not the worker. The limit is set right after the start (`prlimit`), not in the child before it
runs: that hook is not safe in a process with threads. The child is then still starting its
interpreter, long before it starts a program of its own.
"""

import asyncio
import contextlib
import os
import resource
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta

# Output kept for error messages, unless the caller asks for more (`tail`).
TAIL = 4000
# The prefix of Lekto's configuration variables (`composition/settings.py`); none of them
# reaches a child.
_SETTINGS_PREFIX = "LEKTO_"


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str  # the last `tail` characters


async def run_process(
    args: Sequence[str],
    *,
    timeout: timedelta,
    env: Mapping[str, str] | None = None,
    tail: int = TAIL,
    memory: int | None = None,
) -> Completed:
    """Run `args` and wait for it. TimeoutError after `timeout`; the process group is killed
    then, and also when the caller is cancelled. `env` adds to the child's environment (see the
    module); `tail` is how much of the end of its error output is kept; `memory` the bytes of
    address space the child and what it starts may take each (see the module)."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
        env=child_environment(env),
    )
    if memory is not None:
        with contextlib.suppress(ProcessLookupError):  # it ended already
            resource.prlimit(process.pid, resource.RLIMIT_AS, (memory, memory))
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout.total_seconds()
        )
    except TimeoutError:
        await _kill(process)
        raise TimeoutError(
            f"{os.path.basename(args[0])} did not finish within {timeout.total_seconds():g} s"
        ) from None
    except BaseException:
        await _kill(process)
        raise
    assert process.returncode is not None
    return Completed(
        returncode=process.returncode,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace")[-tail:],
    )


def child_environment(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment for a child process: this process's own without Lekto's settings,
    plus `extra`."""
    inherited = {
        name: value for name, value in os.environ.items() if not name.startswith(_SETTINGS_PREFIX)
    }
    return {**inherited, **(extra or {})}


async def _kill(process: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    # Reap the child; shielded, so a second cancellation does not leave a zombie behind.
    await asyncio.shield(process.wait())
