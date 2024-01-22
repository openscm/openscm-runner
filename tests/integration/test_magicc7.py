import os.path

import pymagicc.io
import pytest
from scmdata import ScmRun

import openscm_runner.run
from openscm_runner.adapters import MAGICC7
from openscm_runner.testing import _AdapterTester
from openscm_runner.utils import calculate_quantiles


@pytest.mark.magicc
class TestMagicc7Adapter(_AdapterTester):
    def test_run(
        self,
        test_scenarios,
        num_regression,
    ):
        res = openscm_runner.run.run(
            climate_models_cfgs={
                "MAGICC7": [
                    {
                        "core_climatesensitivity": 3,
                        "rf_soxi_dir_wm2": -0.2,
                        "out_temperature": 1,
                        "out_forcing": 1,
                        "out_dynamic_vars": [
                            "DAT_AEROSOL_ERF",
                            "DAT_HEATCONTENT_AGGREG_TOTAL",
                            "DAT_CO2_AIR2LAND_FLUX",
                        ],
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
                "Surface Air Temperature Change",
                "Effective Radiative Forcing",
                "Effective Radiative Forcing|Aerosols",
                "Effective Radiative Forcing|CO2",
                "Heat Content",
                "Heat Content|Ocean",
                "Heat Uptake",
                "Heat Uptake|Ocean",
                "Net Atmosphere to Land Flux|CO2",
            ),
        )

        assert isinstance(res, ScmRun)
        assert res["run_id"].min() == 0
        assert res["run_id"].max() == 8
        assert (
            res.get_unique_meta("climate_model", no_duplicates=True)
            == f"MAGICC{MAGICC7.get_version()}"
        )
        assert set(res.get_unique_meta("variable")) == {
            "Surface Air Temperature Change",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
            "Heat Content",
            "Heat Content|Ocean",
            "Heat Uptake",
            "Heat Uptake|Ocean",
            "Net Atmosphere to Land Flux|CO2",
        }

        # check we can also calcluate quantiles
        assert "run_id" in res.meta
        quantiles = calculate_quantiles(res, [0, 0.05, 0.17, 0.5, 0.83, 0.95, 1])
        assert "run_id" not in quantiles.meta

        # a problem for another day...
        # self._check_heat_content_heat_uptake_consistency(res)

        outputs_to_get = {
            "MAGICCv7.5.3": [
                {
                    "variable": "Heat Content|Ocean",
                    "unit": "ZJ",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Heat Uptake|Ocean",
                    "unit": "W/m^2",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Heat Uptake",
                    "unit": "W/m^2",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Effective Radiative Forcing",
                    "unit": "W/m^2",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Net Atmosphere to Land Flux|CO2",
                    "unit": "GtC / yr",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 0,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp370",
                    "quantile": 1,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp370",
                    "quantile": 0,
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
            ]
        }

        output_dict = self._get_output_dict(res, outputs_to_get)
        num_regression.check(output_dict, default_tolerance=dict(rtol=self._rtol))

    def test_variable_naming(self, test_scenarios):
        common_variables = self._common_variables
        res = openscm_runner.run.run(
            climate_models_cfgs={"MAGICC7": ({"core_climatesensitivity": 3},)},
            scenarios=test_scenarios.filter(scenario="ssp126"),
            output_variables=common_variables,
        )

        missing_vars = set(common_variables) - set(res["variable"])
        if missing_vars:
            raise AssertionError(missing_vars)


@pytest.mark.magicc
def test_write_scen_files_and_make_full_cfgs(test_scenarios):
    adapter = MAGICC7()
    test_scenarios_magiccdf = pymagicc.io.MAGICCData(test_scenarios)
    res = adapter._write_scen_files_and_make_full_cfgs(
        test_scenarios_magiccdf,
        [
            {
                "file_emisscen_3": "overwritten by adapter.magicc_scenario_setup",
                "other_cfg": 12,
            }
        ],
    )

    for (model, scenario), _ in test_scenarios_magiccdf.meta.groupby(
        ["model", "scenario"]
    ):
        scen_file_name = (
            f"{scenario}_{model}.SCEN7".upper()
            .replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "-")
        )
        scen_full_filename = os.path.join(
            adapter._run_dir(), "openscm-runner", scen_file_name
        )

        scenario_cfg = [v for v in res if v["file_emisscen"] == scen_full_filename]

        assert len(scenario_cfg) == 1
        scenario_cfg = scenario_cfg[0]
        assert scenario_cfg["other_cfg"] == 12
        assert scenario_cfg["model"] == model
        assert scenario_cfg["scenario"] == scenario
        for i in range(2, 9):
            scen_flag_val = scenario_cfg[f"file_emisscen_{i}"]

            assert scen_flag_val == "NONE"


@pytest.mark.magicc
@pytest.mark.parametrize(
    "out_config",
    (
        ("core_climatesensitivity", "rf_total_runmodus"),
        ("core_climatesensitivity",),
        ("rf_total_runmodus",),
    ),
)
def test_return_config(test_scenarios, out_config):
    core_climatesensitivities = [2, 3]
    rf_total_runmoduses = ["ALL", "CO2"]

    cfgs = []
    for cs in core_climatesensitivities:
        for runmodus in rf_total_runmoduses:
            cfgs.append(
                {
                    "out_dynamic_vars": [
                        "DAT_TOTAL_INCLVOLCANIC_ERF",
                        "DAT_SURFACE_TEMP",
                    ],
                    "core_climatesensitivity": cs,
                    "rf_total_runmodus": runmodus,
                }
            )

    res = openscm_runner.run.run(
        climate_models_cfgs={"MAGICC7": cfgs},
        scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
        output_variables=(
            "Surface Air Temperature Change",
            "Effective Radiative Forcing",
        ),
        out_config={"MAGICC7": out_config},
    )

    for k in out_config:
        assert k in res.meta.columns
        ssp126 = res.filter(scenario="ssp126")

        # check all the configs were used and check that each scenario
        # has all the configs included in the metadata too
        if k == "core_climatesensitivity":
            assert set(res.get_unique_meta(k)) == set(core_climatesensitivities)
            assert set(ssp126.get_unique_meta(k)) == set(core_climatesensitivities)
        elif k == "rf_total_runmodus":
            assert set(res.get_unique_meta(k)) == set(rf_total_runmoduses)
            assert set(ssp126.get_unique_meta(k)) == set(rf_total_runmoduses)
        else:
            raise NotImplementedError(k)


@pytest.mark.magicc
@pytest.mark.parametrize(
    "cfgs",
    (
        [{"pf_apply": 1, "PF_APPLY": 0}],
        [{"pf_apply": 1}, {"pf_apply": 1, "PF_APPLY": 0}],
    ),
)
def test_return_config_clash_error(test_scenarios, cfgs):
    with pytest.raises(ValueError):
        openscm_runner.run.run(
            climate_models_cfgs={"MAGICC7": cfgs},
            scenarios=test_scenarios.filter(scenario=["ssp126"]),
            output_variables=("Surface Air Temperature Change",),
            out_config={"MAGICC7": ("pf_apply",)},
        )
