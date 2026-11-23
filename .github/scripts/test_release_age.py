"""pnpm waits as long as Renovate does: `python3 -m unittest discover -s .github/scripts`.

Renovate proposes a release 10 days after it came out at the earliest (`renovate.json`). pnpm
keeps its own age (`web/pnpm-workspace.yaml`, in minutes) at every resolution, transitive packages
and Renovate's lock runs included; it replaced overrides that held packages at older releases and
outlived their reason (WK-03). Shorter, it would take what Renovate does not propose yet; longer,
Renovate's pull requests would fail on the lock."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAYS = re.compile(r"(\d+) days")
PNPM = re.compile(r"^minimumReleaseAge: (\d+)$", re.MULTILINE)


class ReleaseAgeTest(unittest.TestCase):
    def test_pnpm_waits_as_long_as_renovate(self) -> None:
        renovate = json.loads((ROOT / "renovate.json").read_text(encoding="utf-8"))
        days = DAYS.fullmatch(renovate["minimumReleaseAge"])
        self.assertIsNotNone(days, renovate["minimumReleaseAge"])
        assert days is not None
        workspace = (ROOT / "web" / "pnpm-workspace.yaml").read_text(encoding="utf-8")
        minutes = PNPM.search(workspace)
        self.assertIsNotNone(minutes, "no minimumReleaseAge in web/pnpm-workspace.yaml")
        assert minutes is not None
        self.assertEqual(int(minutes.group(1)), int(days.group(1)) * 24 * 60)


if __name__ == "__main__":
    unittest.main()
