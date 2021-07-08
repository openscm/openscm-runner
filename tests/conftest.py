import os.path

import pyam
import pytest
from scmdata import ScmRun

from openscm_runner.adapters import CICEROSCM, MAGICC7

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test-data")


@pytest.fixture(scope="session")
def test_data_dir():
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def test_scenarios(test_data_dir):
    scenarios = pyam.IamDataFrame(
        os.path.join(test_data_dir, "rcmip_scen_ssp_world_emissions.csv")
    )

    return scenarios


@pytest.fixture(scope="session")
def test_scenarios_2600(test_data_dir):
    scenarios = pyam.IamDataFrame(
        os.path.join(test_data_dir, "rcmip_scen_ssp_world_emissions_2600.csv")
    )

    return scenarios


@pytest.fixture(scope="session")
def test_scenario_ssp370_world(test_data_dir):
    scenario = ScmRun(
        os.path.join(
            test_data_dir, "rcmip-emissions-annual-means-v5-1-0-ssp370-world.csv"
        ),
        lowercase_cols=True,
    )

    return scenario


REQUIRED_MAGICC_VERSION = "v7.5.1"

try:
    MAGICC_VERSION = MAGICC7.get_version()
    if MAGICC_VERSION != REQUIRED_MAGICC_VERSION:
        CORRECT_MAGICC_IS_AVAILABLE = False
    else:
        CORRECT_MAGICC_IS_AVAILABLE = True

except KeyError:
    MAGICC_VERSION = None
    CORRECT_MAGICC_IS_AVAILABLE = False


CICEROSCM_IS_AVAILABLE = False
try:
    CICEROSCM.get_version()
    CICEROSCM_IS_AVAILABLE = True
except OSError:
    CICERO_OS_ERROR = True
except KeyError:
    CICERO_OS_ERROR = False


def pytest_runtest_setup(item):
    for mark in item.iter_markers():
        if mark.name == "magicc" and not CORRECT_MAGICC_IS_AVAILABLE:
            if MAGICC_VERSION is None:
                pytest.skip("MAGICC7 not available")
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


def pytest_addoption(parser):
    parser.addoption(
        "--update-expected-values",
        action="store_true",
        default=False,
        help="Overwrite expected values",
    )


@pytest.fixture
def update_expected_values(request):
    return request.config.getoption("--update-expected-values")
