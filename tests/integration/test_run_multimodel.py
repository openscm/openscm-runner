import numpy as np
import numpy.testing as npt
import pytest
from scmdata import ScmRun

import openscm_runner.run
import openscm_runner.testing
from openscm_runner.utils import calculate_quantiles

RTOL = 1e-5


def _check_res(exp, check_val, raise_error, rtol=RTOL):
    try:
        npt.assert_allclose(exp, check_val, rtol=rtol)
    except AssertionError:
        if raise_error:
            raise

        print(f"exp: {exp}, check_val: {check_val}")


@pytest.mark.magicc
def test_multimodel_run(test_scenarios, num_regression):
    res = openscm_runner.run.run(
        climate_models_cfgs={
            "FaIR": [
                {},
                {"q": np.array([0.3, 0.45]), "r0": 30.0, "lambda_global": 0.9},
                {"q": np.array([0.35, 0.4]), "r0": 25.0, "lambda_global": 1.1},
            ],
            "MAGICC7": [
                {
                    "core_climatesensitivity": 3,
                    "rf_soxi_dir_wm2": -0.2,
                    "out_temperature": 1,
                    "out_forcing": 1,
                    "out_dynamic_vars": [
                        "DAT_CO2_CONC",
                        "DAT_AEROSOL_ERF",
                        "DAT_HEATCONTENT_AGGREG_TOTAL",
                        "DAT_HEATUPTK_AGGREG",
                    ],
                    "out_ascii_binary": "BINARY",
                    "out_binary_format": 2,
                },
                {
                    "core_climatesensitivity": 2,
                    "rf_soxi_dir_wm2": -0.1,
                    "out_temperature": 1,
                    "out_forcing": 1,
                    "out_dynamic_vars": [
                        "DAT_CO2_CONC",
                        "DAT_AEROSOL_ERF",
                        "DAT_HEATCONTENT_AGGREG_TOTAL",
                        "DAT_HEATUPTK_AGGREG",
                    ],
                    "out_ascii_binary": "BINARY",
                    "out_binary_format": 2,
                },
                {
                    "core_climatesensitivity": 5,
                    "rf_soxi_dir_wm2": -0.35,
                    "out_temperature": 1,
                    "out_forcing": 1,
                    "out_dynamic_vars": [
                        "DAT_CO2_CONC",
                        "DAT_AEROSOL_ERF",
                        "DAT_HEATCONTENT_AGGREG_TOTAL",
                        "DAT_HEATUPTK_AGGREG",
                    ],
                    "out_ascii_binary": "BINARY",
                    "out_binary_format": 2,
                },
            ],
        },
        scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
        output_variables=(
            "Surface Air Temperature Change",
            "Atmospheric Concentrations|CO2",
            "Heat Content|Ocean",
            "Heat Content",
            "Heat Uptake|Ocean",
            "Heat Uptake",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
        ),
        out_config=None,
    )

    assert isinstance(res, ScmRun)

    climate_models = res.get_unique_meta("climate_model")
    assert any(["MAGICC" in m for m in climate_models])
    assert any(["FaIR" in m for m in climate_models])

    for climate_model in climate_models:
        res_cm = res.filter(climate_model=climate_model)
        assert set(res_cm.get_unique_meta("variable")) == set(
            [
                "Surface Air Temperature Change",
                "Effective Radiative Forcing",
                "Effective Radiative Forcing|Aerosols",
                "Effective Radiative Forcing|CO2",
                "Heat Content|Ocean",
                "Heat Content",
                "Heat Uptake|Ocean",
                "Heat Uptake",
                "Atmospheric Concentrations|CO2",
            ]
        )

    # check we can also calcluate quantiles
    assert "run_id" in res.meta
    quantiles = calculate_quantiles(res, [0, 0.05, 0.17, 0.5, 0.83, 0.95, 1])
    assert "run_id" not in quantiles.meta

    outputs_to_get = {
        "*": [
            {
                "variable": "Effective Radiative Forcing",
                "unit": "W/m^2",
                "region": "World",
                "year": 2100,
                "scenario": "ssp126",
                "quantile": 0.05,
            },
            {
                "variable": "Heat Uptake",
                "unit": "W/m^2",
                "region": "World",
                "year": 2100,
                "scenario": "ssp126",
                "quantile": 0.05,
            },
            {
                "variable": "Heat Content",
                "unit": "ZJ",
                "region": "World",
                "year": 2100,
                "scenario": "ssp126",
                "quantile": 0.05,
            },
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp126",
                "quantile": 0.05,
            },
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp126",
                "quantile": 0.95,
            },
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp370",
                "quantile": 0.05,
            },
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp370",
                "quantile": 0.95,
            },
        ],
        "MAGICC*": [
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp126",
                "quantile": 0.05,
            },
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp370",
                "quantile": 0.95,
            },
        ],
        "FaIR*": [
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp126",
                "quantile": 0.05,
            },
            {
                "variable": "Surface Air Temperature Change",
                "region": "World",
                "year": 2100,
                "scenario": "ssp370",
                "quantile": 0.95,
            },
        ],
    }

    output_dict = openscm_runner.testing._get_output_dict(res, outputs_to_get)
    num_regression.check(output_dict, default_tolerance=dict(rtol=RTOL))
