"""The integration tests get the image's system packages: `python3 -m unittest discover -s
.github/scripts`.

The stage `base` of the Dockerfile installs the packages of OCRmyPDF and WeasyPrint; the job
`integration` installs them on the runner through `ocr-packages.sh` (`PACKAGES`). A package added
to only one of them lets the tests pass on something the image does not have, or the other way
round. `ca-certificates` is the image's alone (the runner has it)."""

import re
import shlex
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE_ONLY = {"ca-certificates"}


def image_packages() -> set[str]:
    """What `apt-get install` installs in the Dockerfile's stage `base`."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    stage = re.search(r"^FROM \S+ AS base$(.*?)^FROM ", text, re.MULTILINE | re.DOTALL)
    assert stage is not None, "no stage `base` in the Dockerfile"
    lines = [line for line in stage.group(1).splitlines() if not line.lstrip().startswith("#")]
    commands = "\n".join(lines).replace("\\\n", " ").split("&&")
    installs = [
        shlex.split(command)
        for command in commands
        if command.split()[:2] == ["apt-get", "install"]
        or command.split()[1:3] == ["apt-get", "install"]
    ]
    assert len(installs) == 1, f"one apt-get install in the stage `base`, not {len(installs)}"
    words = installs[0]
    return {word for word in words[words.index("install") + 1 :] if not word.startswith("-")}


def script_packages() -> set[str]:
    """The array `PACKAGES` of `ocr-packages.sh`."""
    text = (ROOT / ".github/scripts/ocr-packages.sh").read_text(encoding="utf-8")
    array = re.search(r"^PACKAGES=\((.*?)\)$", text, re.MULTILINE | re.DOTALL)
    assert array is not None, "no PACKAGES in ocr-packages.sh"
    return set(shlex.split(array.group(1), comments=True))


class OcrPackagesTest(unittest.TestCase):
    def test_finds_the_packages(self) -> None:
        self.assertIn("tesseract-ocr", image_packages())
        self.assertIn("tesseract-ocr", script_packages())

    def test_the_runner_gets_the_packages_of_the_image(self) -> None:
        self.assertEqual(script_packages(), image_packages() - IMAGE_ONLY)


if __name__ == "__main__":
    unittest.main()
