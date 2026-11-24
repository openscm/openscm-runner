"""
Unit tests of `MAGICCAR6AdapterConfiguration.from_environment`
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openscm_runner.adapters.magicc_ar6 import (
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6NotFoundError,
)
from openscm_runner.adapters.magicc_ar6.base import (
    MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR,
    MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR,
    MAGICC_AR6_V753_ROOT_DIR_ENV_VAR,
    get_magicc_download_token,
)

# These are the MAGICC AR6 adapters' tests (see docs/development/testing.md)
pytestmark = pytest.mark.magicc_ar6

ENV_VARS = (
    MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR,
    MAGICC_AR6_V753_ROOT_DIR_ENV_VAR,
    MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR,
)


@pytest.fixture(autouse=True)
def no_magicc_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


@pytest.fixture
def fake_from_token(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Record `from_token` calls instead of downloading"""
    calls: list[tuple[str, Any]] = []

    def fake(cls: Any, token: str, **kwargs: Any) -> str:
        calls.append((token, kwargs))
        return "from-token"

    monkeypatch.setattr(MAGICCAR6AdapterConfiguration, "from_token", classmethod(fake))

    return calls


def make_paths(tmp_path: Path) -> tuple[Path, Path]:
    magicc_root = tmp_path / "magicc"
    magicc_root.mkdir()
    distribution = tmp_path / "distribution.json"
    distribution.write_text("{}")

    return magicc_root, distribution


def set_paths(
    monkeypatch: pytest.MonkeyPatch, magicc_root: Path, distribution: Path
) -> None:
    monkeypatch.setenv(MAGICC_AR6_V753_ROOT_DIR_ENV_VAR, str(magicc_root))
    monkeypatch.setenv(MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR, str(distribution))


def test_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR, "a-token")

    assert get_magicc_download_token() == "a-token"


@pytest.mark.parametrize(
    "value",
    (pytest.param(None, id="not-set"), pytest.param("", id="empty")),
)
def test_no_token_raises(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    # An empty value counts as missing
    if value is not None:
        monkeypatch.setenv(MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR, value)

    with pytest.raises(MAGICCAR6NotFoundError, match=MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR):
        get_magicc_download_token()


def test_configuration_from_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_from_token: list[Any]
) -> None:
    magicc_root, distribution = make_paths(tmp_path)
    set_paths(monkeypatch, magicc_root, distribution)
    # The paths win over the token
    monkeypatch.setenv(MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR, "a-token")

    res = MAGICCAR6AdapterConfiguration.from_environment(n_workers=3)

    assert res == MAGICCAR6AdapterConfiguration(
        magicc_root=magicc_root,
        ar6_probabilistic_distribution=distribution,
        n_workers=3,
    )
    assert not fake_from_token


def test_configuration_from_token(
    monkeypatch: pytest.MonkeyPatch, fake_from_token: list[Any]
) -> None:
    monkeypatch.setenv(MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR, "a-token")
    # Empty paths count as not set
    monkeypatch.setenv(MAGICC_AR6_V753_ROOT_DIR_ENV_VAR, "")

    res = MAGICCAR6AdapterConfiguration.from_environment(n_workers=3)

    assert res == "from-token"
    assert fake_from_token == [("a-token", {"n_workers": 3})]


def test_configuration_nothing_set_raises() -> None:
    with pytest.raises(MAGICCAR6NotFoundError, match=MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR):
        MAGICCAR6AdapterConfiguration.from_environment()


@pytest.mark.parametrize(
    "env_var",
    (
        MAGICC_AR6_V753_ROOT_DIR_ENV_VAR,
        MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR,
    ),
)
def test_configuration_only_one_path_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env_var: str
) -> None:
    monkeypatch.setenv(env_var, str(tmp_path))

    with pytest.raises(MAGICCAR6NotFoundError, match="Set both"):
        MAGICCAR6AdapterConfiguration.from_environment()


@pytest.mark.parametrize(
    "missing, match",
    (
        pytest.param("magicc", "isn't a directory", id="magicc"),
        pytest.param("distribution", "isn't a file", id="distribution"),
    ),
)
def test_configuration_missing_path_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str, match: str
) -> None:
    magicc_root, distribution = make_paths(tmp_path)
    if missing == "magicc":
        magicc_root = tmp_path / "typo"
    else:
        distribution = tmp_path / "typo.json"

    set_paths(monkeypatch, magicc_root, distribution)

    with pytest.raises(MAGICCAR6NotFoundError, match=match):
        MAGICCAR6AdapterConfiguration.from_environment()
