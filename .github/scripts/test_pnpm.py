"""The image installs the pnpm `web/package.json` names: `python3 -m unittest discover -s
.github/scripts`.

Renovate raises `packageManager` there; a version of the Dockerfile's own stayed behind it
(OP-K06)."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PnpmTest(unittest.TestCase):
    def test_the_dockerfile_names_no_version_of_its_own(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"pnpm@\d", dockerfile))
        self.assertIn("packageManager", dockerfile)


if __name__ == "__main__":
    unittest.main()
