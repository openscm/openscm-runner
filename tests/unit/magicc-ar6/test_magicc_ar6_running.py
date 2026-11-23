"""
Unit tests of running MAGICC which don't need MAGICC

The platform-specific code is tested by mocking the platform.
"""

from __future__ import annotations

import platform
from pathlib import Path

import pytest
from openscm_runner.adapters.magicc_ar6 import running as running_module
from openscm_runner.adapters.magicc_ar6.running import (
    MAGICCInstallation,
    MAGICCRunError,
    get_binary_name,
    get_environment,
)

# These are the MAGICC AR6 adapters' tests (see docs/testing.md)
pytestmark = pytest.mark.magicc_ar6


@pytest.mark.parametrize(
    "system, machine, expected",
    (
        pytest.param("Darwin", "arm64", "magicc-darwin-arm64", id="macos-arm"),
        pytest.param("Darwin", "x86_64", "magicc-darwin-amd64", id="macos-intel"),
        pytest.param("Linux", "x86_64", "magicc", id="linux"),
        pytest.param("Windows", "AMD64", "magicc.exe", id="windows"),
    ),
)
def test_get_binary_name(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str, expected: str
) -> None:
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "machine", lambda: machine)

    assert get_binary_name() == expected


def test_get_binary_name_unknown_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Plan9")

    with pytest.raises(
        NotImplementedError, match="No MAGICC binary is known for Plan9"
    ):
        get_binary_name()


@pytest.mark.parametrize(
    "existing_dyld_library_path, expected_suffix",
    (
        pytest.param(None, "", id="no-existing"),
        pytest.param("/somewhere/else", ":/somewhere/else", id="existing"),
    ),
)
def test_get_environment_uses_first_existing_library_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing_dyld_library_path: str | None,
    expected_suffix: str,
) -> None:
    exists = [tmp_path / "second", tmp_path / "third"]
    for path in exists:
        path.mkdir()

    monkeypatch.setattr(
        running_module,
        "MACOS_GFORTRAN_LIBRARY_PATHS",
        (tmp_path / "first", *exists),
    )
    if existing_dyld_library_path is None:
        monkeypatch.delenv("DYLD_LIBRARY_PATH", raising=False)
    else:
        monkeypatch.setenv("DYLD_LIBRARY_PATH", existing_dyld_library_path)

    res = get_environment()

    assert res["DYLD_LIBRARY_PATH"] == f"{tmp_path / 'second'}{expected_suffix}"


def test_get_environment_no_library_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E.g. on linux, the environment is passed through unchanged"""
    monkeypatch.setattr(
        running_module, "MACOS_GFORTRAN_LIBRARY_PATHS", (tmp_path / "missing",)
    )
    monkeypatch.delenv("DYLD_LIBRARY_PATH", raising=False)

    res = get_environment()

    assert "DYLD_LIBRARY_PATH" not in res


def make_installation(
    tmp_path: Path, *, binary: bool = True, run_dir: bool = True
) -> MAGICCInstallation:
    if run_dir:
        (tmp_path / "run").mkdir()

    installation = MAGICCInstallation(
        root_dir=tmp_path, expected_version="v7.5.3", binary_path=tmp_path / "magicc"
    )
    if binary:
        # Unix only (a shell script), which is fine as CI doesn't run on Windows
        # (see `make_failing_binary` in the AR scenario integration tests)
        installation.binary.write_text(
            '#!/bin/sh\necho "$MAGICC_VERSION"\nexit "$EXIT"\n'
        )
        installation.binary.chmod(0o755)

    return installation


@pytest.mark.parametrize(
    "binary, run_dir",
    (
        pytest.param(False, True, id="no-binary"),
        pytest.param(True, False, id="no-run-dir"),
    ),
)
def test_installation_check_missing(
    tmp_path: Path, binary: bool, run_dir: bool
) -> None:
    installation = make_installation(tmp_path, binary=binary, run_dir=run_dir)

    with pytest.raises(FileNotFoundError, match="doesn't exist"):
        installation.check()


@pytest.mark.parametrize(
    "version, exit_code",
    (
        pytest.param("v7.5.3", "0", id="right-version"),
        pytest.param("v7.6.0", "0", id="wrong-version"),
        pytest.param("v7.5.3", "1", id="non-zero-exit"),
    ),
)
def test_installation_check_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str, exit_code: str
) -> None:
    installation = make_installation(tmp_path)
    monkeypatch.setenv("MAGICC_VERSION", version)
    monkeypatch.setenv("EXIT", exit_code)

    if version == installation.expected_version and exit_code == "0":
        installation.check()
    else:
        with pytest.raises(MAGICCRunError, match="Expected MAGICC v7.5.3"):
            installation.check()
