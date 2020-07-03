import os.path

import pyam
import pytest

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
