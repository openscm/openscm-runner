import os
import os.path

import numpy.testing as npt
import pymagicc.io
from scmdata import ScmDataFrame

from openscm_runner import run
from openscm_runner.adapters import MAGICC7
from openscm_runner.utils import calculate_quantiles

RTOL = 1e-5


def magicc7_is_available():
    try:
        magicc_version = MAGICC7.get_version()
        if magicc_version != "v7.4.0":
            raise AssertionError(
                "Wrong MAGICC version for tests ({})".format(magicc_version)
            )
        return True

    except ValueError:
        return False


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
                    "out_ascii_binary": "BINARY",
                    "out_binary_format": 2,
                },
                {
                    "core_climatesensitivity": 2,
                    "rf_soxi_dir_wm2": -0.1,
                    "out_temperature": 1,
                    "out_forcing": 1,
                    "out_ascii_binary": "BINARY",
                    "out_binary_format": 2,
                },
                {
                    "core_climatesensitivity": 5,
                    "rf_soxi_dir_wm2": -0.35,
                    "out_temperature": 1,
                    "out_forcing": 1,
                    "out_ascii_binary": "BINARY",
                    "out_binary_format": 2,
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
    assert res.get_unique_meta(
        "climate_model", no_duplicates=True
    ) == "MAGICC{}".format(MAGICC7.get_version())
    assert set(res.get_unique_meta("variable")) == set(
        [
            "Surface Temperature",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
        ]
    )

    npt.assert_allclose(
        2.6126502,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp126"
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        1.4454666,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp126"
        ).values.min(),
        rtol=RTOL,
    )

    npt.assert_allclose(
        5.5218109,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp370"
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        2.7332273999999996,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp370"
        ).values.min(),
        rtol=RTOL,
    )

    # check we can also calcluate quantiles
    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    npt.assert_allclose(
        1.4932964,
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
        2.54376164,
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
        2.8361154,
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
        5.34584055,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
        rtol=RTOL,
    )


def test_write_scen_files_and_make_full_cfgs(monkeypatch, tmpdir, test_scenarios, magicc7_is_available):
    adapter = MAGICC7()
    test_scenarios_magiccdf = pymagicc.io.MAGICCData(test_scenarios)
    res = adapter._write_scen_files_and_make_full_cfgs(
        test_scenarios_magiccdf,
        [{"file_emisscen_3": "overwrites adapter.magicc_scenario_setup", "other_cfg": 12}]
    )

    for (model, scenario), _ in test_scenarios_magiccdf.meta.groupby(["model", "scenario"]):
        scen_file_name = (
            "{}_{}.SCEN7".format(scenario, model)
            .upper()
            .replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "-")
        )

        scenario_cfg = [
            v for v in res if v["file_emisscen"] == scen_file_name
        ]

        assert len(scenario_cfg) == 1
        scenario_cfg = scenario_cfg[0]
        assert scenario_cfg["other_cfg"] == 12
        assert scenario_cfg["model"] == model
        assert scenario_cfg["scenario"] == scenario
        for i in range(2, 9):
            scen_flag_val = scenario_cfg["file_emisscen_{}".format(i)]
            if i == 3:
                assert scen_flag_val == "overwrites adapter.magicc_scenario_setup"
            else:
                assert scen_flag_val == "NONE"
