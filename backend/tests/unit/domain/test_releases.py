"""Which release is news to a running Lekto (`.knowledge/open/update-notifier-fas.md`)."""

from datetime import UTC, datetime

from lekto.core.domain.releases import (
    Release,
    Version,
    is_development,
    newest_for,
    update_available,
)

WHEN = datetime(2026, 11, 19, 12, tzinfo=UTC)


def release(version: str) -> Release:
    return Release(version=version, published_at=WHEN, url=f"https://github.com/r/{version}")


def v(text: str) -> Version:
    version = Version.parse(text)
    assert version is not None
    return version


def test_versions_follow_semver() -> None:
    assert v("0.15.6") < v("0.16.0") < v("1.0.0-beta.1") < v("1.0.0-beta.2") < v("1.0.0")
    assert v("1.0.0-beta.2") < v("1.0.0-beta.10")
    assert v("v1.2.3") == v("1.2.3")
    assert Version.parse("latest") is None
    assert not v("0.16.0").stable and not v("1.0.0-rc.1").stable and v("1.0.0").stable


def test_a_beta_hears_of_newer_betas_and_stable_releases() -> None:
    releases = [release("0.15.5"), release("0.16.0"), release("1.0.0-beta.1"), release("0.15.6")]
    assert newest_for("0.15.6", releases) == release("1.0.0-beta.1")
    assert newest_for("1.0.0-beta.1", releases) is None


def test_a_stable_release_hears_of_stable_ones_only() -> None:
    releases = [release("1.0.0"), release("1.1.0-beta.1"), release("1.0.1")]
    assert newest_for("1.0.0", releases) == release("1.0.1")
    assert newest_for("1.0.1", releases) is None


def test_a_development_state_hears_of_nothing() -> None:
    assert is_development("0.0.0.dev0") and is_development("nonsense")
    assert not is_development("0.15.6")
    assert newest_for("0.0.0.dev0", [release("0.16.0")]) is None
    assert not update_available("0.0.0.dev0", release("0.16.0"))


def test_an_update_is_available_while_the_latest_is_newer() -> None:
    assert update_available("0.15.6", release("0.16.0"))
    assert not update_available("0.16.0", release("0.16.0"))  # updated meanwhile
    assert not update_available("0.16.1", release("0.16.0"))
    assert not update_available("0.15.6", None)
