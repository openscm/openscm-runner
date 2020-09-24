import os
from unittest import mock

import pytest

from openscm_runner.settings import ConfigLoader


@mock.patch("openscm_runner.settings.dotenv_values")
def test_config_empty(mock_dotenv, monkeypatch):
    mock_dotenv.return_value = {}
    # This assumes that the envvar TEST_ENV_VAR does not exist
    config = ConfigLoader()
    assert not config.is_loaded

    with pytest.raises(KeyError, match="TEST_ENV_VAR"):
        config["TEST_ENV_VAR"]

    with pytest.raises(KeyError, match="TEST_ENV_VAR"):
        config["test_ENV_var"]


@mock.patch("openscm_runner.settings.dotenv_values")
def test_config_envvar(mock_dotenv, monkeypatch):
    mock_dotenv.return_value = {}
    config = ConfigLoader()

    res = config["PATH"]
    assert res == os.environ["PATH"]

    res = config["paTh"]
    assert res == os.environ["PATH"]


@mock.patch("openscm_runner.settings.dotenv_values")
def test_config_with_dotenv(mock_dotenv, monkeypatch):
    monkeypatch.setenv("TEST", "env_var")
    mock_dotenv.return_value = {"TEST": "env_file", "EXTRA": "yay"}

    config = ConfigLoader()

    assert config["TEST"] == "env_var"
    assert config["EXTRA"] == "yay"
    assert config["extra"] == "yay"

    with pytest.raises(KeyError, match="NOT_THERE"):
        config["not_there"]

    assert config.is_loaded
    mock_dotenv.assert_called_once()
    assert config._config == mock_dotenv.return_value


@mock.patch("openscm_runner.settings.dotenv_values")
def test_config_get(mock_dotenv, monkeypatch):
    monkeypatch.setenv("TEST", "env_var")
    mock_dotenv.return_value = {}

    config = ConfigLoader()

    assert config.get("TEST", "default") == "env_var"
    assert config.get("UNKNOWN_CONFIG", "default") == "default"
