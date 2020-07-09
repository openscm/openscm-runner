import os.path

import pyam
import pytest

from openscm_runner.adapters import MAGICC7


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
def magicc7_is_available():
    try:
        MAGICC7.get_version()

    except ValueError:
        pytest.skip("MAGICC7 not available")
