import pymagicc.io
import pytest
from base import _AdapterTester
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.adapters import MAGICC7
from openscm_runner.utils import calculate_quantiles


class TestMagicc7Adapter(_AdapterTester):
    def test_run(self, test_scenarios, magicc7_is_available):
        debug_run = False

        res = run(
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
                "Heat Content|Ocean",
                "Net Atmosphere to Land Flux|CO2",
            ),
        )

        assert isinstance(res, ScmRun)
        assert res["run_id"].min() == 0
        assert res["run_id"].max() == 8
        assert res.get_unique_meta(
            "climate_model", no_duplicates=True
        ) == "MAGICC{}".format(MAGICC7.get_version())
        assert set(res.get_unique_meta("variable")) == set(
            [
                "Surface Air Temperature Change",
                "Effective Radiative Forcing",
                "Effective Radiative Forcing|Aerosols",
                "Effective Radiative Forcing|CO2",
                "Heat Content|Ocean",
                "Net Atmosphere to Land Flux|CO2",
            ]
        )

        # check ocean heat content unit conversion comes through correctly
        self._check_res(
            2508.737908,
            res.filter(
                unit="ZJ",
                variable="Heat Content|Ocean",
                region="World",
                year=2100,
                scenario="ssp126",
            ).values.max(),
            not debug_run,
        )

        self._check_res(
            0.472378,
            res.filter(
                unit="GtC / yr",
                variable="Net Atmosphere to Land Flux|CO2",
                region="World",
                year=2100,
                scenario="ssp126",
            ).values.max(),
            not debug_run,
        )

        self._check_res(
            2.756034,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
            ).values.max(),
            not debug_run,
        )
        self._check_res(
            1.2195495,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
            ).values.min(),
            not debug_run,
        )

        self._check_res(
            5.5226571,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
            ).values.max(),
            not debug_run,
        )
        self._check_res(
            2.733369581,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
            ).values.min(),
            not debug_run,
        )

        # check we can also calcluate quantiles
        quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

        self._check_res(
            1.27586919,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
                quantile=0.05,
            ).values,
            not debug_run,
        )
        self._check_res(
            2.6587052,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
                quantile=0.95,
            ).values,
            not debug_run,
        )

        self._check_res(
            2.83627686,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
                quantile=0.05,
            ).values,
            not debug_run,
        )
        self._check_res(
            5.34663565,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
                quantile=0.95,
            ).values,
            not debug_run,
        )

        if debug_run:
            assert False, "Turn off debug"

    def test_variable_naming(
        self, test_scenarios, magicc7_is_available
    ):
        common_variables = self._common_variables
        res = run(
            climate_models_cfgs={"MAGICC7": ({"core_climatesensitivity": 3},)},
            scenarios=test_scenarios.filter(scenario="ssp126"),
            output_variables=common_variables,
        )

        missing_vars = set(common_variables) - set(res["variable"])
        if missing_vars:
            raise AssertionError(missing_vars)


def test_write_scen_files_and_make_full_cfgs(test_scenarios, magicc7_is_available):
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
            "{}_{}.SCEN7".format(scenario, model)
            .upper()
            .replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "-")
        )

        scenario_cfg = [v for v in res if v["file_emisscen"] == scen_file_name]

        assert len(scenario_cfg) == 1
        scenario_cfg = scenario_cfg[0]
        assert scenario_cfg["other_cfg"] == 12
        assert scenario_cfg["model"] == model
        assert scenario_cfg["scenario"] == scenario
        for i in range(2, 9):
            scen_flag_val = scenario_cfg["file_emisscen_{}".format(i)]

            assert scen_flag_val == "NONE"


@pytest.mark.parametrize(
    "out_config",
    (
        ("core_climatesensitivity", "rf_total_runmodus"),
        ("core_climatesensitivity",),
        ("rf_total_runmodus",),
    ),
)
def test_return_config(test_scenarios, magicc7_is_available, out_config):
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

    res = run(
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
