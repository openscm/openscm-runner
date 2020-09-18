import numpy as np
import numpy.testing as npt
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.utils import calculate_quantiles

RTOL = 1e-5


def test_multimodel_run(test_scenarios, magicc7_is_available):
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
                        "DAT_HEATUPTK_AGGREG",
                    ],
                    "out_ascii_binary": "BINARY",
                    "out_binary_format": 2,
                },
            ],
        },
        scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
        output_variables=(
            "Surface Temperature",
            "Atmospheric Concentrations|CO2",
            "Heat Content",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
        ),
        full_config=False,
    )

    assert isinstance(res, ScmRun)

    climate_models = res.get_unique_meta("climate_model")
    assert any(["MAGICC" in m for m in climate_models])
    assert any(["FaIR" in m for m in climate_models])

    for climate_model in climate_models:
        res_cm = res.filter(climate_model=climate_model)
        assert set(res_cm.get_unique_meta("variable")) == set(
            [
                "Surface Temperature",
                "Effective Radiative Forcing",
                "Effective Radiative Forcing|Aerosols",
                "Effective Radiative Forcing|CO2",
                "Heat Content",
                "Atmospheric Concentrations|CO2",
            ]
        )

    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    npt.assert_allclose(
        1.53273349,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
        ).values,
        rtol=RTOL,
    )
    npt.assert_allclose(
        2.51196596,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.95,
        ).values,
        rtol=RTOL,
    )

    npt.assert_allclose(
        2.9904474,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.05,
        ).values,
        rtol=RTOL,
    )
    npt.assert_allclose(
        5.34757776,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
        rtol=RTOL,
    )

    quantiles_cm = calculate_quantiles(
        res,
        [0.05, 0.17, 0.5, 0.83, 0.95],
        process_over_columns=("run_id", "ensemble_member"),
    )

    npt.assert_allclose(
        1.4932964,
        quantiles_cm.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
            climate_model="MAGICC*",
        ).values,
        rtol=RTOL,
    )
    npt.assert_allclose(
        5.34584055,
        quantiles_cm.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
            climate_model="MAGICC*",
        ).values,
        rtol=RTOL,
    )

    npt.assert_allclose(
        1.80924238,
        quantiles_cm.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
            climate_model="FaIR*",
        ).values,
        rtol=RTOL,
    )
    npt.assert_allclose(
        4.76399179,
        quantiles_cm.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
            climate_model="FaIR*",
        ).values,
        rtol=RTOL,
    )
