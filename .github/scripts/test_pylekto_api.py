"""Tests of `pylekto_api.py`: `python3 -m unittest discover .github/scripts`."""

import unittest

from pylekto_api import (
    MIGRATION_LOCK,
    VERSION_MODULE,
    api_version,
    mismatch,
    pylekto_version,
)

LOCK = """\
version = 1

[[package]]
name = "pydantic"
version = "2.14.3"

[[package]]
name = "pylekto"
version = "0.9.1"
"""


class PylektoApiTest(unittest.TestCase):
    def test_reads_the_api_version(self) -> None:
        module = '"""The version."""\n\nAPI_VERSION = "0.10"\nFINGERPRINT = "abc"\n'
        self.assertEqual(api_version(module), "0.10")

    def test_reads_the_locked_pylekto(self) -> None:
        self.assertEqual(pylekto_version(LOCK), "0.9.1")

    def test_a_lock_without_pylekto_fails(self) -> None:
        with self.assertRaises(ValueError):
            pylekto_version('version = 1\n\n[[package]]\nname = "pydantic"\nversion = "2.14.3"\n')

    def test_a_pylekto_of_the_api_fits(self) -> None:
        self.assertIsNone(mismatch("0.9", "0.9.0"))
        self.assertIsNone(mismatch("0.9", "0.9.12"))

    def test_a_pylekto_of_another_api_is_named(self) -> None:
        why = mismatch("0.10", "0.9.0")
        self.assertIsNotNone(why)
        assert why is not None
        self.assertIn("pylekto 0.9.0 (API 0.9)", why)
        self.assertIn("the API 0.10", why)
        # 0.1 is no prefix match of 0.10.
        self.assertIsNotNone(mismatch("0.10", "0.1.3"))

    def test_the_repository_reads(self) -> None:
        api_version(VERSION_MODULE.read_text(encoding="utf-8"))
        pylekto_version(MIGRATION_LOCK.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
