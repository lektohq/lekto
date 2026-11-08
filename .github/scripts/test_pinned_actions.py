"""Every action the workflows use is pinned to a commit: `python3 -m unittest discover -s
.github/scripts`.

A tag can be moved to other code after the fact, a commit cannot; `release.yml` pushes the images
with `packages: write`. The version stands in a comment beside the commit (`@<sha> # v6.1.0`):
Renovate reads it to update both, and leaves a commit without one alone."""

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"[^@\s]+@[0-9a-f]{40}")
VERSION = re.compile(r"\s+#\s*v\d+(?:\.\d+){0,2}\s*")


def uses() -> list[tuple[str, str, str]]:
    """Every `uses:` of the workflows: where it stands, what it names, what follows."""
    found = []
    for workflow in sorted(WORKFLOWS.glob("*.y*ml")):
        for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            match = USES.match(line)
            if match is not None:
                found.append((f"{workflow.name}:{number}", match.group(1), match.group(2)))
    return found


class PinnedActionsTest(unittest.TestCase):
    def test_finds_the_actions(self) -> None:
        self.assertGreater(len(uses()), 10)

    def test_every_action_is_pinned_to_a_commit_with_its_version(self) -> None:
        unpinned = [
            f"{where}: {target}{rest}"
            for where, target, rest in uses()
            if not target.startswith("./")  # an action of this repository
            and not (PINNED.fullmatch(target) and VERSION.fullmatch(rest))
        ]
        self.assertEqual(unpinned, [])

    def test_a_tag_or_a_commit_without_its_version_is_unpinned(self) -> None:
        sha = "d23441a48e516b6c34aea4fa41551a30e30af803"
        for line, pinned in [
            (f"      - uses: actions/checkout@{sha} # v6.1.0", True),
            (f"        uses: actions/cache/save@{sha} # v5", True),
            ("      - uses: actions/checkout@v6", False),
            ("      - uses: actions/checkout@v6.1.0 # v6.1.0", False),
            (f"      - uses: actions/checkout@{sha}", False),
            (f"      - uses: actions/checkout@{sha[:12]} # v6.1.0", False),
        ]:
            match = USES.match(line)
            assert match is not None
            target, rest = match.groups()
            ok = bool(PINNED.fullmatch(target) and VERSION.fullmatch(rest))
            self.assertEqual(ok, pinned, line)


if __name__ == "__main__":
    unittest.main()
