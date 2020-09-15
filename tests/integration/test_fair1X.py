import numpy as np
import numpy.testing as npt
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.adapters import FAIR
from openscm_runner.utils import calculate_quantiles

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
            "Ocean Heat Uptake",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
            "CO2 Air to Land Flux",  # should be ignored
        ),
        full_config=False,
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
            "Ocean Heat Uptake",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
        ]
    )

    npt.assert_allclose(
        2.2099132544445927,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        1.7945341435607594,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
        ).values.min(),
        rtol=RTOL,
    )

    npt.assert_allclose(
        4.824878345585957,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        4.07184261082167,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
        ).values.min(),
        rtol=RTOL,
    )

    # check we can also calcluate quantiles
    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    npt.assert_allclose(
        1.80924238,
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
        2.18308358,
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
        4.08625963,
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
        4.76399179,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
        rtol=RTOL,
    )
