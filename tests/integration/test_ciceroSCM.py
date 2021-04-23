import os

import numpy.testing as npt
import pytest
from base import _AdapterTester
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.adapters import CICEROSCM
from openscm_runner.adapters.ciceroscm_adapter import (
    make_scenario_files,
    write_parameter_files,
)
from openscm_runner.utils import calculate_quantiles

RTOL = 1e-5


class TestCICEROSCMAdapter(_AdapterTester):
    @pytest.mark.ciceroscm
    def test_run(
        self, test_scenarios, test_data_dir, update_expected_values,
    ):
        expected_output_file = os.path.join(
            test_data_dir,
            "expected-integration-output",
            "expected_ciceroscm_test_run_output.json",
        )

        res = run(
            scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
            climate_models_cfgs={
                "CICEROSCM": [
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
                ]
            },
            output_variables=(
                "Surface Air Temperature Change",
                "Surface Air Ocean Blended Temperature Change",
                "Heat Content|Ocean",
                "Effective Radiative Forcing",
                "Effective Radiative Forcing|Anthropogenic",
                "Effective Radiative Forcing|Aerosols",
                "Effective Radiative Forcing|Greenhouse Gases",
                "Heat Uptake",
                "Atmospheric Concentrations|CO2",
                "Atmospheric Concentrations|CH4",
                "Atmospheric Concentrations|N2O",
                "Emissions|CO2",
            ),
            out_config=None,
        )
        assert isinstance(res, ScmRun)
        assert res["run_id"].min() == 1
        assert res["run_id"].max() == 30040
        assert res.get_unique_meta("climate_model", no_duplicates=True) == "CICERO-SCM"

        assert set(res.get_unique_meta("variable")) == set(
            [
                "Surface Air Temperature Change",
                "Surface Air Ocean Blended Temperature Change",
                "Heat Content|Ocean",
                "Effective Radiative Forcing",
                "Effective Radiative Forcing|Anthropogenic",
                "Effective Radiative Forcing|Aerosols",
                "Effective Radiative Forcing|Greenhouse Gases",
                "Heat Uptake",
                "Atmospheric Concentrations|CO2",
                "Atmospheric Concentrations|CH4",
                "Atmospheric Concentrations|N2O",
                "Emissions|CO2",
            ]
        )

        # check we can also calcluate quantiles
        assert "run_id" in res.meta
        quantiles = calculate_quantiles(res, [0, 0.05, 0.17, 0.5, 0.83, 0.95, 1])
        assert "run_id" not in quantiles.meta

        assert (
            res.filter(variable="Atmospheric Concentrations|CO2").get_unique_meta(
                "unit", True
            )
            == "ppm"
        )
        assert (
            res.filter(variable="Atmospheric Concentrations|CH4").get_unique_meta(
                "unit", True
            )
            == "ppb"
        )
        assert (
            res.filter(variable="Atmospheric Concentrations|N2O").get_unique_meta(
                "unit", True
            )
            == "ppb"
        )
        assert (
            res.filter(variable="Emissions|CO2").get_unique_meta("unit", True)
            == "PgC / yr"
        )

        # check that emissions were passed through correctly
        npt.assert_allclose(
            res.filter(variable="Emissions|CO2", year=2100, scenario="ssp126")
            .convert_unit("PgC/yr")
            .values,
            -2.3503,
            rtol=1e-4,
        )
        npt.assert_allclose(
            res.filter(variable="Emissions|CO2", year=2100, scenario="ssp370")
            .convert_unit("PgC/yr")
            .values,
            22.562,
            rtol=1e-4,
        )

        self._check_output(res, expected_output_file, update_expected_values)

    @pytest.mark.ciceroscm
    def test_variable_naming(self, test_scenarios):
        missing_from_ciceroscm = (
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC AFOLU",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC AFOLU",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC AFOLU",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
            "Heat Uptake|Ocean",
            "Net Atmosphere to Land Flux|CO2",
            "Net Atmosphere to Ocean Flux|CO2",
        )
        common_variables = [
            c for c in self._common_variables if c not in missing_from_ciceroscm
        ]
        res = run(
            climate_models_cfgs={"CICEROSCM": ({"lambda": 0.540},)},
            scenarios=test_scenarios.filter(scenario="ssp126"),
            output_variables=common_variables,
        )

        missing_vars = set(common_variables) - set(res["variable"])
        if missing_vars:
            raise AssertionError(missing_vars)

    @pytest.mark.ciceroscm
    def test_w_out_config(self, test_scenarios):
        with pytest.raises(NotImplementedError):
            run(
                scenarios=test_scenarios.filter(scenario=["ssp126"]),
                climate_models_cfgs={
                    "CiceroSCM": [
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
                    ]
                },
                output_variables=("Surface Air Temperature Change",),
                out_config={"CiceroSCM": ("With ECS",)},
            )

    def test_make_scenario_files(self, test_scenarios):
        npt.assert_string_equal(
            make_scenario_files.unit_name_converter("Mt C/yr"), "Tg C/yr"
        )
        npt.assert_string_equal(
            make_scenario_files.unit_name_converter("kt N2O"), "Gg N2O"
        )
        npt.assert_string_equal(
            make_scenario_files.unit_name_converter("Gt tests"), "Pg tests"
        )
        npt.assert_string_equal(make_scenario_files.unit_name_converter("Test"), "Test")

        self._check_res(
            3.0 / 11 * 1000.0,
            make_scenario_files.unit_conv_factor("Mg_C", "Gg CO2/yr", "CO2_lu"),
            False,
        )
        self._check_res(
            0.636 / 1.0e12,
            make_scenario_files.unit_conv_factor("Pg_N", "kg N2O/yr", "N2O"),
            False,
        )
        self._check_res(
            0.304 / 1.0e12,
            make_scenario_files.unit_conv_factor("Pt_N", "kt NOx/yr", "NOx"),
            False,
        )
        self._check_res(
            0.501,
            make_scenario_files.unit_conv_factor("Tg_S", "Tg SO2/yr", "SO2"),
            False,
        )

    @pytest.mark.parametrize(
        "input,exp",
        (
            ("folder", ("folder",)),
            (os.path.join("folder", "subfolder"), ("folder", "subfolder")),
        ),
    )
    def test_write_parameter_files(self, input, exp):
        assert write_parameter_files.splitall(input) == exp


@pytest.mark.ciceroscm
def test_get_version():
    assert CICEROSCM.get_version() == "v2019vCH4"
