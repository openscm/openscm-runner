import os

import numpy as np
import numpy.testing as npt
import pytest
from scmdata import ScmRun
import pandas as pd
from pyam import IamDataFrame
from openscm_runner.adapters import CICEROSCM
from openscm_runner.adapters.ciceroscm_adapter import (
    make_scenario_files,
    write_parameter_files,
)
from openscm_runner.adapters.utils import _parallel_process
from openscm_runner.utils import calculate_quantiles

RTOL = 1e-5


def _check_res(exp, check_val, raise_error, rtol=RTOL):
    try:
        npt.assert_allclose(exp, check_val, rtol=rtol)
        print("Check passed")
    except AssertionError:
        print("exp: {}, check_val: {}".format(exp, check_val))
        print(raise_error)
        if raise_error:
            raise


def test_ciceroscm_run(test_scenarios):
    debug_run = False
    adapter = CICEROSCM()
    res = adapter._run(
        scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
        cfgs=[
            {
                "Index": 30040,
                "lambda": 0.540,
                "akapa": 0.341,
                "cpi": 0.556,
                "W": 1.897,
                "rlamdo": 16.618,
                "beto": 3.225,
                "mixed": 107.277,
                "dirso2_forc": -0.457,
                "indso2_forc": -0.514,
                "bc_forc": 0.200,
                "oc_forc": -0.103,
            },
            {
                "Index": 1,
                "lambda": 0.3925,
                "akapa": 0.2421,
                "cpi": 0.3745,
                "W": 0.8172,
                "rlamdo": 16.4599,
                "beto": 4.4369,
                "mixed": 35.4192,
                "dirso2_forc": -0.3428,
                "indso2_forc": -0.3856,
                "bc_forc": 0.1507,
                "oc_forc": -0.0776,
            },
        ],
        output_variables=(
            "Surface Temperature",
            "Surface Temperature (GMST)",
            "Heat Content|Ocean",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|Greenhouse Gases",
            "Heat Uptake",
            "Atmospheric Concentrations|CO2",
            "Emissions|CO2",
        ),
        output_config=None,
    )
    assert isinstance(res, ScmRun)
    assert res["run_id"].min() == 1
    assert res["run_id"].max() == 30040
    assert res.get_unique_meta("climate_model", no_duplicates=True) == "Cicero-SCM"

    assert set(res.get_unique_meta("variable")) == set(
        [
            "Surface Temperature",
            "Surface Temperature (GMST)",
            "Heat Content|Ocean",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|Greenhouse Gases",
            "Heat Uptake",
            "Atmospheric Concentrations|CO2",
            "Emissions|CO2",
        ]
    )

    # check ocean heat content unit conversion comes through correctly
    _check_res(
        904.474,
        res.filter(
            unit="ZJ",
            variable="Heat Content|Ocean",
            region="World",
            year=2100,
            scenario="ssp126",
        ).values.max(),
        not debug_run,
        rtol=RTOL,
    )

    _check_res(
        1.50177,
        res.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
        ).values.max(),
        not debug_run,
        rtol=RTOL,
    )

    _check_res(
        3.35742,
        res.filter(
            variable="Surface Temperature (GMST)",
            region="World",
            year=2100,
            scenario="ssp370",
        ).values.max(),
        not debug_run,
        rtol=RTOL,
    )
    _check_res(
        -2.5292859114958564,
        res.filter(
            unit="ZJ/yr",
            variable="Heat Uptake",
            region="World",
            year=2100,
            scenario="ssp126",
        ).values.max(),
        not debug_run,
        rtol=RTOL,
    )
    _check_res(
        780.2869999999999,
        res.filter(
            variable="Atmospheric Concentrations|CO2",
            region="World",
            year=2100,
            scenario="ssp370",
        ).values.max(),
        not debug_run,
        rtol=RTOL,
    )
    _check_res(
        22.5616,
        res.filter(
            variable="Emissions|CO2", region="World", year=2100, scenario="ssp370",
        ).values.max(),
        not debug_run,
        rtol=RTOL,
    )
    # check we can also calcluate quantiles
    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    _check_res(
        1.1427785,
        quantiles.filter(
            variable="Surface Temperature (GMST)",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
        ).values,
        not debug_run,
        rtol=RTOL,
    )

    _check_res(
        1.4757515,
        quantiles.filter(
            variable="Surface Temperature (GMST)",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.95,
        ).values,
        not debug_run,
        rtol=RTOL,
    )

    _check_res(
        2.7883605,
        quantiles.filter(
            variable="Surface Temperature (GMST)",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.05,
        ).values,
        not debug_run,
        rtol=RTOL,
    )

    _check_res(
        3.3274695,
        quantiles.filter(
            variable="Surface Temperature (GMST)",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
        not debug_run,
        rtol=RTOL,
    )
    if debug_run:
        assert False, "Turn off debug"


def test_w_output_config(test_scenarios):
    adapter = CICEROSCM()
    with pytest.raises(NotImplementedError):
        adapter._run(
            scenarios=test_scenarios.filter(scenario=["ssp126"]),
            cfgs=[
                {
                    "Index": 30040,
                    "lambda": 0.540,
                    "akapa": 0.341,
                    "cpi": 0.556,
                    "W": 1.897,
                    "rlamdo": 16.618,
                    "beto": 3.225,
                    "mixed": 107.277,
                    "dirso2_forc": -0.457,
                    "indso2_forc": -0.514,
                    "bc_forc": 0.200,
                    "oc_forc": -0.103,
                },
            ],
            output_variables=("Surface Temperature",),
            output_config="With ECS",
        )


def test_make_scenario_files(test_scenarios):
    npt.assert_string_equal(
        make_scenario_files.unit_name_converter("Mt C/yr"), "Tg C/yr"
    )
    npt.assert_string_equal(make_scenario_files.unit_name_converter("kt N2O"), "Gg N2O")
    npt.assert_string_equal(
        make_scenario_files.unit_name_converter("Gt tests"), "Pg tests"
    )
    npt.assert_string_equal(make_scenario_files.unit_name_converter("Test"), "Test")

    _check_res(
        3.0 / 11 * 1000.0,
        make_scenario_files.unit_conv_factor("Mg_C", "Gg CO2/yr", "CO2_lu"),
        False,
        rtol=RTOL,
    )
    _check_res(
        0.636 / 1.0e12,
        make_scenario_files.unit_conv_factor("Pg_N", "kg N2O/yr", "N2O"),
        False,
        rtol=RTOL,
    )
    _check_res(
        0.304 / 1.0e12,
        make_scenario_files.unit_conv_factor("Pt_N", "kt NOx/yr", "NOx"),
        False,
        rtol=RTOL,
    )
    _check_res(
        0.501,
        make_scenario_files.unit_conv_factor("Tg_S", "Tg SO2/yr", "SO2"),
        False,
        rtol=RTOL,
    )
    """
    sfilewriter = make_scenario_files.SCENARIOFILEWRITER(os.path.join("src", "openscm_runner", "adapters", "ciceroscm_adapter", "utils_templates"))
    scenario = test_scenarios.filter(scenario="ssp126").as_pandas()
    scenario['year'] = [pd.Timestamp(y) for y in scenario['year']]
    scenarioIAM = IamDataFrame(scenario)
    print(scenarioIAM.head())
    interpol = sfilewriter.transform_scenarioframe(scenarioIAM.timeseries())
    print(interpol.head())
    npt.assert_equal(sfilewriter.transform_scenarioframe(scenarioIAM.timeseries()).shape, (23,86))
    assert(False)
    
    """

@pytest.mark.parametrize(
    "input,exp",
    (
        ("folder", ("folder",)),
        (os.path.join("folder", "subfolder"), ("folder", "subfolder")),
    ),
)
def test_write_parameter_files(input, exp):
    assert write_parameter_files.splitall(input) == exp


def _self_function(x):
    return x


def test_parallel():
    runs = [{"x": x} for x in range(10)]

    result = _parallel_process._parallel_process(
        func=_self_function,
        configuration=runs,
        pool=None,
        config_are_kwargs=True,
        front_serial=2,
        front_parallel=2,
    )
    npt.assert_array_equal(np.sort(result), range(10))
    runs2 = [x for x in range(10)]
    result2 = _parallel_process._parallel_process(
        func=_self_function,
        configuration=runs2,
        pool=None,
        config_are_kwargs=False,
        front_serial=2,
        front_parallel=2,
    )
    npt.assert_array_equal(np.sort(result2), range(10))
