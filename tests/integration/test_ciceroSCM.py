import os

import numpy as np
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
    @pytest.mark.parametrize("shuffle_column_order", (True, False))
    def test_run(
        self,
        test_scenarios,
        test_data_dir,
        update_expected_values,
        shuffle_column_order,
    ):
        expected_output_file = os.path.join(
            test_data_dir,
            "expected-integration-output",
            "expected_ciceroscm_test_run_output.json",
        )

        if shuffle_column_order:
            tmp = test_scenarios.data
            cols = tmp.columns.tolist()
            tmp = tmp[cols[1:] + cols[:1]]
            test_scenarios = ScmRun(test_scenarios)

        res = run(
            scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
            climate_models_cfgs={
                "CICEROSCM": [
                    {
                        "model_end": 2100,
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
                        "model_end": 2100,
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
                "Emissions|CH4",
                "Emissions|N2O",
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
                "Emissions|N2O",
                "Emissions|CH4",
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
        assert (
            res.filter(variable="Emissions|CH4").get_unique_meta("unit", True)
            == "TgCH4 / yr"
        )
        assert (
            res.filter(variable="Emissions|N2O").get_unique_meta("unit", True)
            == "TgN2ON / yr"
        )

        # check that emissions were passed through correctly
        for (scen, variable, unit, exp_val) in (
            ("ssp126", "Emissions|CO2", "PgC/yr", -2.3503),
            ("ssp370", "Emissions|CO2", "PgC/yr", 22.562),
            ("ssp126", "Emissions|CH4", "TgCH4/yr", 122.195),
            ("ssp370", "Emissions|CH4", "TgCH4/yr", 777.732),
            ("ssp126", "Emissions|N2O", "TgN2ON/yr", 5.318),
            ("ssp370", "Emissions|N2O", "TgN2ON/yr", 13.144),
        ):
            res_scen_2100_emms = res.filter(
                variable=variable, year=2100, scenario=scen
            ).convert_unit(unit)
            if res_scen_2100_emms.empty:
                raise AssertionError("No {} data for {}".format(variable, scen))

            npt.assert_allclose(
                res_scen_2100_emms.values, exp_val, rtol=1e-4,
            )
        for (scen, variable, unit, exp_val14, exp_val16) in (
            ("ssp126", "Emissions|CH4", "TgCH4/yr", 387.874, 379.956),
            ("ssp370", "Emissions|CH4", "TgCH4/yr", 387.874, 394.149),
            ("ssp126", "Emissions|N2O", "TgN2ON/yr", 6.911, 6.858),
            ("ssp370", "Emissions|N2O", "TgN2ON/yr", 6.911, 7.0477),
        ):
            res_scen_2014_emms = res.filter(
                variable=variable, year=2014, scenario=scen
            ).convert_unit(unit)
            if res_scen_2014_emms.empty:
                raise AssertionError("No {} data for {}".format(variable, scen))

            res_scen_2016_emms = res.filter(
                variable=variable, year=2016, scenario=scen
            ).convert_unit(unit)
            if res_scen_2016_emms.empty:
                raise AssertionError("No {} data for {}".format(variable, scen))

            npt.assert_allclose(
                res_scen_2014_emms.values, exp_val14, rtol=1e-4,
            )
            npt.assert_allclose(
                res_scen_2016_emms.values, exp_val16, rtol=1e-4,
            )
        for (scen, variable) in (
            ("ssp126", "Effective Radiative Forcing|Aerosols"),
            ("ssp370", "Effective Radiative Forcing|Aerosols"),
        ):
            res_scen_2015_emms = res.filter(variable=variable, year=2015, scenario=scen)
            if res_scen_2015_emms.empty:
                raise AssertionError("No CO2 emissions data for {}".format(scen))

            assert not np.equal(res_scen_2015_emms.values, 0).all()

        ssp245_ghg_erf_2015 = res.filter(
            variable="Effective Radiative Forcing|Greenhouse Gases",
            year=2015,
            scenario="ssp245",
            run_id=1,
        )
        ssp245_ghg_erf_2014 = res.filter(
            variable="Effective Radiative Forcing|Greenhouse Gases",
            year=2014,
            scenario="ssp245",
            run_id=1,
        )
        # check that jump in GHG ERF isn't there
        assert (
            ssp245_ghg_erf_2015.values.squeeze() - ssp245_ghg_erf_2014.values.squeeze()
        ) < 0.1
        ssp245_ch4_conc_2015 = res.filter(
            variable="Atmospheric Concentrations|CH4",
            year=2015,
            scenario="ssp245",
            run_id=1,
        )
        ssp245_ch4_conc_2014 = res.filter(
            variable="Atmospheric Concentrations|CH4",
            year=2014,
            scenario="ssp245",
            run_id=1,
        )
        # ch
        # check that jump in GHG ERF isn't there
        assert (
            ssp245_ch4_conc_2014.values.squeeze()
            - ssp245_ch4_conc_2015.values.squeeze()
        ) < 0.1

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
                            "model_end": 2100,
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
        npt.assert_allclose(
            3.0 / 11.0 * 1000.0,
            make_scenario_files._unit_conv_factor("Gg CO2/yr", "Mg C/ yr"),
        )
        npt.assert_allclose(
            28 / 44 / 1.0e12,
            make_scenario_files._unit_conv_factor("kg N2O / yr", "Pg N2ON / yr"),
        )
        npt.assert_allclose(
            14 / 46 / 1.0e12,
            make_scenario_files._unit_conv_factor("kt NOx / yr", "Pt N / yr"),
        )
        npt.assert_allclose(
            0.5, make_scenario_files._unit_conv_factor("Tg SO2 / yr", "Tg S / yr"),
        )
        npt.assert_allclose(
            1.0,
            make_scenario_files._unit_conv_factor("Gg  Halon1211 / yr", "GgH1211 / yr"),
        )
        npt.assert_allclose(
            1.0,
            make_scenario_files._unit_conv_factor("Gg  Halon2402 / yr", "GgH2402 / yr"),
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
    @pytest.mark.parametrize(
        "name",
        (
            "some super super super super super super super super super super long scenario name which should not explode",
            "another name with some special | . characters which should also work",
            # any other names you want to test
        ),
    )
    def test_run_long_scenario_name(
        self, name, test_scenarios,
    ):
        starting_scenario = test_scenarios.filter(scenario="ssp126").rename(
            {"scenario": {"ssp126": name}}
        )

        res = run(
            scenarios=starting_scenario,
            climate_models_cfgs={"CICEROSCM": [{}]},
            output_variables=("Surface Air Temperature Change",),
        )

        assert res.get_unique_meta("scenario", True) == name
        assert (1.4 < res.filter(year=2100).values < 1.6).all()
        # any other tests you want to add


@pytest.mark.ciceroscm
def test_get_version():
    assert CICEROSCM.get_version() == "v2019vCH4"
