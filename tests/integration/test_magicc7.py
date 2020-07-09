import numpy.testing as npt
import pytest
from scmdata import ScmDataFrame

from openscm_runner import run
from openscm_runner.adapters import MAGICC7
from openscm_runner.utils import calculate_quantiles


def test_magicc7_run(test_scenarios, magicc7_is_available):
    res = run(
        climate_models_cfgs={
            "MAGICC7": [
                {
                    "core_climatesensitivity": 3,
                    "rf_soxi_dir_wm2": -0.2,
                    "out_temperature": 1,
                    "out_forcing": 1,
                    "out_dynamic_vars": ["DAT_AEROSOL_ERF"],
                },
                {
                    "core_climatesensitivity": 2,
                    "rf_soxi_dir_wm2": -0.1,
                    "out_temperature": 1,
                    "out_forcing": 1,
                },
                {
                    "core_climatesensitivity": 5,
                    "rf_soxi_dir_wm2": -0.35,
                    "out_temperature": 1,
                    "out_forcing": 1,
                },
            ],
        },
        scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
        output_variables=(
            "Surface Temperature",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
            # "CO2 Air to Land Flux",  # todo: add this back in
        ),
        full_config=False,
    )

    assert isinstance(res, ScmDataFrame)
    assert res["run_id"].min() == 0
    assert res["run_id"].max() == 8
    assert res.get_unique_meta("climate_model", no_duplicates=True) == "MAGICC{}".format(MAGICC7.get_version())
    assert set(res.get_unique_meta("variable")) == set(
        [
            "Surface Temperature",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
        ]
    )

    npt.assert_allclose(
        2.9113092,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp126"
        ).values.max(),
    )
    npt.assert_allclose(
        1.278011,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp126"
        ).values.min(),
    )

    npt.assert_allclose(
        5.283013,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp370"
        ).values.max(),
    )
    npt.assert_allclose(
        2.4871168,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp370"
        ).values.min(),
    )

    # check we can also calcluate quantiles
    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    npt.assert_allclose(
        1.33356199,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
        ).values,
    )
    npt.assert_allclose(
        2.80353037,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.95,
        ).values,
    )

    npt.assert_allclose(
        2.58370978,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.05,
        ).values,
    )
    npt.assert_allclose(
        5.10001636,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
    )
