import numpy as np
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.adapters import FAIR

RTOL = 1e-5


def test_fair_run(test_scenarios):
    res = run(
        climate_models_cfgs={
            "FaIR": [
                {},
                {"q": np.array([0.3, 0.45]), "r0": 30.0, "lambda_global": 0.9},
                {"q": np.array([0.35, 0.4]), "r0": 25.0, "lambda_global": 1.1},
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
            "CO2 Air to Land Flux",  # should be ignored
        ),
        out_config=None,
    )

    assert isinstance(res, ScmRun)
    assert res["run_id"].min() == 0
    assert res["run_id"].max() == 8
    assert res.get_unique_meta("climate_model", no_duplicates=True) == "FaIRv{}".format(
        FAIR.get_version()
    )

    assert set(res.get_unique_meta("variable")) == set(
        [
            "Surface Temperature",
            "Atmospheric Concentrations|CO2",
            "Heat Content",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
        ]
    )

    res.filter(
        variable="Surface Temperature", region="World", year=2100, scenario="ssp126",
    )

    # check we can also calcluate quantiles
    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    quantiles.filter(
        variable="Surface Temperature",
        region="World",
        year=2100,
        scenario="ssp126",
        quantile=0.05,
    )


def test_fair_ocean_factors(test_scenarios):
    res_default_factors = run(
        climate_models_cfgs={"FaIR": [{}]},
        scenarios=test_scenarios.filter(scenario=["ssp585"]),
        output_variables=(
            "Surface Temperature (GMST)",
            "Heat Uptake|Ocean",
            "Heat Content|Ocean",
        ),
    )

    res_custom_factors = run(
        climate_models_cfgs={
            "FaIR": [
                {
                    "gmst_factor": np.linspace(0.90, 1.00, 351),  # test with array
                    "ohu_factor": 0.93,
                }
            ]
        },
        scenarios=test_scenarios.filter(scenario=["ssp585"]),
        output_variables=(
            "Surface Temperature (GMST)",
            "Heat Uptake|Ocean",
            "Heat Content|Ocean",
        ),
    )

    assert (
        res_default_factors.filter(
            variable="Surface Temperature (GMST)",
            region="World",
            year=2100,
            scenario="ssp585",
        ).values
        != res_custom_factors.filter(
            variable="Surface Temperature (GMST)",
            region="World",
            year=2100,
            scenario="ssp585",
        ).values
    )
