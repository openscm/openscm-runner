import numpy as np
import numpy.testing as npt
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.utils import calculate_quantiles

RTOL = 1e-5


def _check_res(exp, check_val, raise_error, rtol=RTOL):
    try:
        npt.assert_allclose(exp, check_val, rtol=rtol)
    except AssertionError:
        if raise_error:
            raise

        print("exp: {}, check_val: {}".format(exp, check_val))


def test_multimodel_run(test_scenarios, magicc7_is_available):
    debug_run = False

    res = run(
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
            "Heat Uptake|Ocean",
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
                "Heat Uptake|Ocean",
                "Atmospheric Concentrations|CO2",
            ]
        )

    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    _check_res(
        1.31448,
        quantiles.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
        ).values,
        not debug_run,
        rtol=RTOL,
    )
    _check_res(
        2.48715,
        quantiles.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.95,
        ).values,
        not debug_run,
        rtol=RTOL,
    )

    _check_res(
        2.97359,
        quantiles.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.05,
        ).values,
        not debug_run,
        rtol=RTOL,
    )
    _check_res(
        5.18685,
        quantiles.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
        not debug_run,
        rtol=RTOL,
    )

    quantiles_cm = calculate_quantiles(
        res,
        [0.05, 0.17, 0.5, 0.83, 0.95],
        process_over_columns=("run_id", "ensemble_member"),
    )

    _check_res(
        1.26457,
        quantiles_cm.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
            climate_model="MAGICC*",
        ).values,
        not debug_run,
        rtol=RTOL,
    )
    _check_res(
        5.20233,
        quantiles_cm.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
            climate_model="MAGICC*",
        ).values,
        not debug_run,
        rtol=RTOL,
    )

    _check_res(
        1.64102168,
        quantiles_cm.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
            climate_model="FaIR*",
        ).values,
        not debug_run,
        rtol=RTOL,
    )
    _check_res(
        4.58938509,
        quantiles_cm.filter(
            variable="Surface Air Temperature Change",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
            climate_model="FaIR*",
        ).values,
        not debug_run,
        rtol=RTOL,
    )

    if debug_run:
        assert False, "Turn off debug"
