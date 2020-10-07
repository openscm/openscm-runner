import numpy as np
import numpy.testing as npt
import pytest
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

    # these values are from the run-fair notebook
    npt.assert_allclose(
        2.003964892582933,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        1.6255017914500822,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
        ).values.min(),
        rtol=RTOL,
    )

    npt.assert_allclose(
        4.645930053608295,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        3.927009494888895,
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
        1.6410216803638293,
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
        1.9816384713833952,
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
        3.9423565896925803,
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
        4.58938509254004,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
        rtol=RTOL,
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


def test_startyear(test_scenarios, test_scenarios_2600):
    # I think we can change the start year, but we can't run different start years in the same ensemble as output files will differ in shape.
    res_1850 = run(
        climate_models_cfgs={"FaIR": [{"startyear": 1850}]},
        scenarios=test_scenarios.filter(scenario=["ssp245"]),
        output_variables=("Surface Temperature",),
        out_config=None,
    )

    res_1750 = run(
        climate_models_cfgs={"FaIR": [{"startyear": 1750}]},
        scenarios=test_scenarios.filter(scenario=["ssp245"]),
        output_variables=("Surface Temperature",),
        out_config=None,
    )

    res_default = run(
        climate_models_cfgs={"FaIR": [{},],},
        scenarios=test_scenarios.filter(scenario=["ssp245"]),
        output_variables=("Surface Temperature",),
        out_config=None,
    )

    gsat2100_start1850 = res_1850.filter(
        variable="Surface Temperature", region="World", year=2100,
    ).values

    gsat2100_start1750 = res_1750.filter(
        variable="Surface Temperature", region="World", year=2100,
    ).values

    gsat2100_startdefault = res_default.filter(
        variable="Surface Temperature", region="World", year=2100,
    ).values

    assert gsat2100_start1850 != gsat2100_start1750
    assert gsat2100_start1750 == gsat2100_startdefault

    with pytest.raises(ValueError):
        run(
            climate_models_cfgs={"FaIR": [{"startyear": 1650}]},
            scenarios=test_scenarios.filter(scenario=["ssp245"]),
            output_variables=("Surface Temperature",),
            out_config=None,
        )

    with pytest.raises(ValueError):
        run(
            climate_models_cfgs={"FaIR": [{}]},
            scenarios=test_scenarios_2600.filter(scenario=["ssp245"]),
            output_variables=("Surface Temperature",),
            out_config=None,
        )
