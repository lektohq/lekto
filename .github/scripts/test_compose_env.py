"""The two base examples set Lekto up alike: `python3 -m unittest discover -s .github/scripts`.

`docker/compose.yml` (SQLite, one container) and `docker/compose.postgres.yml` (PostgreSQL, API
and worker) each spell out the settings of `lekto`; a setting the examples show belongs in both
(review 0.12.2, O-14). Compared is what Compose makes of them (`docker compose config`): the
same variables with the same values, but for the role and the database. Skipped without docker.
"""

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

DOCKER = Path(__file__).resolve().parents[2] / "docker"
REQUIRED = re.compile(r"\$\{([A-Z0-9_]+):\?")
OWN = re.compile(r"^LEKTO_(ROLE|DB_[A-Z0-9_]+)$")


def environment(*files: str) -> dict[str, str]:
    """The environment of the service `lekto` as Compose resolves it, with a placeholder for
    every variable the files require."""
    required = {
        name
        for file in files
        for name in REQUIRED.findall((DOCKER / file).read_text(encoding="utf-8"))
    }
    env = {"PATH": os.environ.get("PATH", ""), **{name: "ci" for name in required}}
    args = [arg for file in files for arg in ("-f", file)]
    result = subprocess.run(
        ["docker", "compose", *args, "config", "--format", "json"],
        cwd=DOCKER,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    found: dict[str, str] = json.loads(result.stdout)["services"]["lekto"]["environment"]
    return {key: str(value) for key, value in found.items() if not OWN.match(key)}


@unittest.skipIf(shutil.which("docker") is None, "needs docker compose")
class ComposeEnvironmentTest(unittest.TestCase):
    def test_both_examples_set_lekto_up_alike(self) -> None:
        single = environment("compose.yml")
        postgres = environment("compose.postgres.yml")
        self.assertGreater(len(single), 10)
        self.assertEqual(single, postgres)


if __name__ == "__main__":
    unittest.main()
