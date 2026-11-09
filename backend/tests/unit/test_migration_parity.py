"""The migration client keeps copies of what Lekto decides (it does not import Lekto): how an
env file is read, which files Lekto takes, how names are compared and how long they and review
reasons may be. These tests keep each copy equal to Lekto's."""

from pathlib import Path

import pytest
from lekto_migration import check, config, expect, mapping, plan

from lekto.composition.env_file import read_env_file
from lekto.composition.errors import ConfigurationError
from lekto.core.domain import imports, media_types, validation

SAMPLES = Path(__file__).parent.parent / "samples"

LINES = [
    "A=1",
    "export B=two",
    "export  C=3",
    "D='single quoted # not a comment'",
    'E="double \\"quoted\\" \\$HOME \\\\ end"',
    "F=x # a comment",
    "G='x' # c",
    "H=",
    '  I="with  spaces"  ',
    "# a comment",
    "",
]
REFUSED = ["no equals", "1A=x", "J=x y", "K='open", 'L="a\\"', 'M="a" b', "N.O=1"]


def _client(path: Path) -> dict[str, str]:
    return config.env_file(path, {})


@pytest.mark.parametrize("line", LINES)
def test_an_env_file_line_reads_alike(tmp_path: Path, line: str) -> None:
    path = tmp_path / "x.env"
    path.write_text(line + "\n", encoding="utf-8")
    assert _client(path) == read_env_file(path)


@pytest.mark.parametrize("line", REFUSED)
def test_an_env_file_line_is_refused_alike(tmp_path: Path, line: str) -> None:
    path = tmp_path / "x.env"
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ConfigurationError) as lekto:
        read_env_file(path)
    with pytest.raises(config.ConfigError) as client:
        _client(path)
    assert str(client.value) == str(lekto.value)


HEADS = [
    b"%PDF1.7 no dash",
    b"\x89PNGxxxx",
    b" " * 500 + b"%PDF-1.4",
    b"From: a@example.test\nSubject: hi\n\nbody",
    b"From: a@example.test\nX-Other: 1\n\nbody",
    b"II*\x00rest",
    b"MM\x00*rest",
    b"\xff\xd8\xff\xe0",
    b"",
]


@pytest.mark.parametrize(
    "head", HEADS + [p.read_bytes()[:1024] for p in sorted(SAMPLES.iterdir()) if p.is_file()]
)
def test_the_client_takes_a_file_as_lekto_does(head: bytes) -> None:
    assert check.kind_of(head) == media_types.detect(head)


def test_the_client_knows_lektos_media_types_and_mail_headers() -> None:
    assert set(expect.SUPPORTED) == set(media_types.SUPPORTED)
    assert check._MAIL_HEADERS == media_types._MAIL_HEADERS
    assert check.HEAD == media_types.SNIFF_SIZE


@pytest.mark.parametrize("name", ["Stadtwerke", "  STADTWERKE  ", "Straße", "ǅemal", "Ἀθήνα"])
def test_the_client_compares_names_as_lekto_does(name: str) -> None:
    assert plan.norm(name) == validation.name_key(name)


def test_the_client_limits_names_and_review_reasons_as_lekto_does() -> None:
    assert mapping.NAME_LIMIT == validation.MAX_NAME
    assert plan.MAX_REVIEW_REASON == imports.MAX_REVIEW_REASON
