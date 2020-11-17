import os.path

import pandas as pd
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
def test_scenarios_2600(test_data_dir):
    scenarios = pyam.IamDataFrame(
        os.path.join(test_data_dir, "rcmip_scen_ssp_world_emissions_2600.csv")
    )

    return scenarios


@pytest.fixture(scope="session")
def magicc7_is_available():
    try:
        magicc_version = MAGICC7.get_version()
        if magicc_version != "v7.4.2-23-g635c48cab":
            raise AssertionError(
                "Wrong MAGICC version for tests ({})".format(magicc_version)
            )

    except KeyError:
        pytest.skip("MAGICC7 not available")


@pytest.fixture(scope="session")
def common_variables():
    # this could be replaced with the RCMIP variables in future (bigger job)
    return (
        "Surface Air Temperature Change",
        "Surface Air Ocean Blended Temperature Change",
        "Effective Radiative Forcing",
        "Effective Radiative Forcing|Anthropogenic",
        "Effective Radiative Forcing|Aerosols",
        "Effective Radiative Forcing|Aerosols|Direct Effect",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC AFOLU",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC AFOLU",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC AFOLU",
        "Effective Radiative Forcing|Aerosols|Indirect Effect",
        "Effective Radiative Forcing|Greenhouse Gases",
        "Effective Radiative Forcing|CO2",
        "Effective Radiative Forcing|CH4",
        "Effective Radiative Forcing|N2O",
        "Effective Radiative Forcing|F-Gases",
        "Effective Radiative Forcing|HFC125",
        "Effective Radiative Forcing|HFC134a",
        "Effective Radiative Forcing|HFC143a",
        "Effective Radiative Forcing|HFC227ea",
        "Effective Radiative Forcing|HFC23",
        "Effective Radiative Forcing|HFC245fa",
        "Effective Radiative Forcing|HFC32",
        "Effective Radiative Forcing|HFC4310",
        "Effective Radiative Forcing|CF4",
        "Effective Radiative Forcing|C6F14",
        "Effective Radiative Forcing|C2F6",
        "Effective Radiative Forcing|SF6",
        "Heat Uptake",
        "Heat Uptake|Ocean",
        "Atmospheric Concentrations|CO2",
        "Atmospheric Concentrations|CH4",
        "Atmospheric Concentrations|N2O",
        "Net Atmosphere to Land Flux|CO2",
        "Net Atmosphere to Ocean Flux|CO2",
    )
