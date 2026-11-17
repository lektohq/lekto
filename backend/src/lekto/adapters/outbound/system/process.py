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
not the worker. A short Python prelude (`_LIMITED`) sets it in the child and then becomes the
program (`exec`): the limit holds from the program's first instruction. Set from the parent
after the start (`prlimit`), it came late on a busy machine, and a child allocated without it;
set before the start in the parent's fork (`preexec_fn`), it would not be safe in a process
with threads. Where the process's own hard limit is lower (a container's `--ulimit as=`), the
child gets that one: it cannot be raised.
"""

import asyncio
import contextlib
import os
import shutil
import signal
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta

# Output kept for error messages, unless the caller asks for more (`tail`).
TAIL = 4000
# The prefix of Lekto's configuration variables (`composition/settings.py`); none of them
# reaches a child.
_SETTINGS_PREFIX = "LEKTO_"
# The prelude of a child with a memory limit: `python -I -c _LIMITED LIMIT PROGRAM ARGS...`.
_LIMITED = (
    "import os, resource, sys\n"
    "limit = int(sys.argv[1])\n"
    "_, hard = resource.getrlimit(resource.RLIMIT_AS)\n"
    "if hard != resource.RLIM_INFINITY:\n"
    "    limit = min(limit, hard)\n"
    "resource.setrlimit(resource.RLIMIT_AS, (limit, limit))\n"
    "os.execvp(sys.argv[2], sys.argv[2:])\n"
)


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
    input: bytes | None = None,
) -> Completed:
    """Run `args` and wait for it. TimeoutError after `timeout`; the process group is killed
    then, and also when the caller is cancelled. `env` adds to the child's environment (see the
    module); `tail` is how much of the end of its error output is kept; `memory` the bytes of
    address space the child and what it starts may take each (see the module); `input` what it
    reads from its standard input (else nothing)."""
    command = list(args)
    if memory is not None:
        if shutil.which(command[0]) is None:  # as starting it without the prelude would
            raise FileNotFoundError(f"no program {command[0]!r}")
        command = [sys.executable, "-I", "-c", _LIMITED, str(memory), *command]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL if input is None else asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
        env=child_environment(env),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input), timeout=timeout.total_seconds()
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
