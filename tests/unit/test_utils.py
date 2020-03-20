import os

import pytest

from openscm_runner.utils import get_env


def test_get_env(monkeypatch):
    expected_output = "hello"
    monkeypatch.setenv("TESTVAR", expected_output)
    assert get_env("TESTVAR") == expected_output


def test_get_env_not_defined(monkeypatch):
    monkeypatch.delenv("TESTVAR", raising=False)
    with pytest.raises(ValueError, match="TESTVAR is not set"):
        get_env("TESTVAR")
