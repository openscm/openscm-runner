"""
Re-useable fixtures etc. for tests

See https://docs.pytest.org/en/7.1.x/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest
import scmdata

from openscm_runner.adapters import CICEROSCM, MAGICC7

TEST_DATA_DIR = Path(__file__).parent / "test-data"
"""Directory in which test data lives"""

REQUIRED_MAGICC_VERSION = "v7.5.3"
"""MAGICC version required for the tests"""

try:
    MAGICC_VERSION = MAGICC7.get_version()
    if MAGICC_VERSION != REQUIRED_MAGICC_VERSION:
        CORRECT_MAGICC_IS_AVAILABLE = False
    else:
        CORRECT_MAGICC_IS_AVAILABLE = True

except (KeyError, subprocess.CalledProcessError) as exc:
    MAGICC_VERSION = None
    CORRECT_MAGICC_IS_AVAILABLE = False
    MAGICC_LOAD_EXC = exc


CICEROSCM_IS_AVAILABLE = False
try:
    CICEROSCM.get_version()
    CICEROSCM_IS_AVAILABLE = True
except OSError:
    CICERO_OS_ERROR = True
except KeyError:
    CICERO_OS_ERROR = False


def pytest_runtest_setup(item) -> None:
    for mark in item.iter_markers():
        if mark.name == "magicc" and not CORRECT_MAGICC_IS_AVAILABLE:
            if MAGICC_VERSION is None:
                pytest.skip(f"MAGICC7 not available. Exc: {MAGICC_LOAD_EXC}")
            else:
                pytest.skip(
                    "Wrong MAGICC version for tests ({}), we require {}".format(
                        MAGICC_VERSION, REQUIRED_MAGICC_VERSION
                    )
                )

        if mark.name == "ciceroscm" and not CICEROSCM_IS_AVAILABLE:
            if CICERO_OS_ERROR:
                pytest.skip("CICERO-SCM not available because of operating system")
            else:
                pytest.skip("CICERO-SCM not available")


@pytest.fixture(scope="session", autouse=True)
def pandas_terminal_width():
    # Set pandas terminal width so that doctests don't depend on terminal width.

    # We set the display width to 120 because examples should be short,
    # anything more than this is too wide to read in the source.
    pd.set_option("display.width", 120)

    # Display as many columns as you want (i.e. let the display width do the
    # truncation)
    pd.set_option("display.max_columns", 1000)


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def test_scenarios(test_data_dir: Path) -> scmdata.ScmRun:
    scenarios = scmdata.ScmRun(
        test_data_dir / "rcmip_scen_ssp_world_emissions.csv",
        lowercase_cols=True,
    )

    return scenarios


@pytest.fixture(scope="session")
def test_scenarios_2600(test_data_dir: Path) -> scmdata.ScmRun:
    scenarios = scmdata.ScmRun(
        test_data_dir / "rcmip_scen_ssp_world_emissions_2600.csv",
        lowercase_cols=True,
    )

    return scenarios


@pytest.fixture(scope="session")
def test_scenario_ssp370_world(test_data_dir: Path) -> scmdata.ScmRun:
    scenario = scmdata.ScmRun(
        test_data_dir / "rcmip-emissions-annual-means-v5-1-0-ssp370-world.csv",
        lowercase_cols=True,
    )

    return scenario
