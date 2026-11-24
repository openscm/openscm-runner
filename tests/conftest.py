"""
Re-useable fixtures etc. for tests

See https://docs.pytest.org/en/7.1.x/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).parents[1]
"""Root of the repository"""

DOTENV_PATH = REPO_ROOT / ".env"
"""
Path to the `.env` file the tests fall back to (see `.env.sample`)

The file is optional and gitignored.
"""


@pytest.fixture(scope="session", autouse=True)
def pandas_terminal_width():
    # Set pandas terminal width so that doctests don't depend on terminal width.

    # We set the display width to 120 because examples should be short,
    # anything more than this is too wide to read in the source.
    pd.set_option("display.width", 120)

    # Display as many columns as you want (i.e. let the display width do the
    # truncation)
    pd.set_option("display.max_columns", 1000)


def set_unset_env_vars_from_dotenv(
    monkeypatch: pytest.MonkeyPatch, dotenv_path: Path
) -> None:
    """
    Set environment variables from a `.env` file, unless they're already set

    Variables which are already set in the environment are used as given
    (even if they are empty), the `.env` file is only a fallback.
    The variables are set with `monkeypatch`,
    so they are only set for the duration of the test.

    Variables with empty values in the `.env` file are left out,
    so a `.env` copied from `.env.sample` doesn't set anything
    until values are filled in.

    Parameters
    ----------
    monkeypatch
        Monkeypatch to set the variables with

    dotenv_path
        Path to the `.env` file. If it doesn't exist, nothing is set.
    """
    if not dotenv_path.exists():
        return

    for key, value in dotenv_values(dotenv_path).items():
        # `None`: a key without `=`, `""`: an empty value
        if value and key not in os.environ:
            monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def env_vars_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Fall back to the repository's `.env` for environment variables which aren't set

    E.g. so the MAGICC AR6 tests can find MAGICC (see `.env.sample`)
    without having to export anything.
    Variables already set in the environment (e.g. in CI) take precedence.
    """
    set_unset_env_vars_from_dotenv(monkeypatch, DOTENV_PATH)
