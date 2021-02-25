import numpy as np
import numpy.testing as npt
import pytest
from base import _AdapterTester
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.adapters import FAIR
from openscm_runner.utils import calculate_quantiles


class TestFairAdapter(_AdapterTester):
    @pytest.mark.parametrize("nworkers", (1, 4))
    def test_run(self, test_scenarios, monkeypatch, nworkers):
        monkeypatch.setenv("FAIR_WORKER_NUMBER", "{}".format(nworkers))
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
                "Surface Air Temperature Change",
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
        assert res.get_unique_meta(
            "climate_model", no_duplicates=True
        ) == "FaIRv{}".format(FAIR.get_version())

        assert set(res.get_unique_meta("variable")) == set(
            [
                "Surface Air Temperature Change",
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
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
            ).values.max(),
            rtol=self._rtol,
        )
        npt.assert_allclose(
            1.6255017914500822,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
            ).values.min(),
            rtol=self._rtol,
        )

        npt.assert_allclose(
            4.645930053608295,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
            ).values.max(),
            rtol=self._rtol,
        )
        npt.assert_allclose(
            3.927009494888895,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
            ).values.min(),
            rtol=self._rtol,
        )

        # check we can also calcluate quantiles
        quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

        npt.assert_allclose(
            1.6410216803638293,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
                quantile=0.05,
            ).values,
            rtol=self._rtol,
        )
        npt.assert_allclose(
            1.9816384713833952,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
                quantile=0.95,
            ).values,
            rtol=self._rtol,
        )

        npt.assert_allclose(
            3.9423565896925803,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
                quantile=0.05,
            ).values,
            rtol=self._rtol,
        )
        npt.assert_allclose(
            4.58938509254004,
            quantiles.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp370",
                quantile=0.95,
            ).values,
            rtol=self._rtol,
        )

    def test_variable_naming(self, test_scenarios):
        missing_from_fair = (
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC AFOLU",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC AFOLU",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC AFOLU",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
            "Net Atmosphere to Ocean Flux|CO2",
            "Net Atmosphere to Land Flux|CO2",
        )
        common_variables = [
            c for c in self._common_variables if c not in missing_from_fair
        ]
        res = run(
            climate_models_cfgs={"FaIR": ({"startyear": 1750},)},
            scenarios=test_scenarios.filter(scenario="ssp126"),
            output_variables=common_variables,
        )

        missing_vars = set(common_variables) - set(res["variable"])
        if missing_vars:
            raise AssertionError(missing_vars)


def test_fair_ocean_factors(test_scenarios):
    res_default_factors = run(
        climate_models_cfgs={"FaIR": [{}]},
        scenarios=test_scenarios.filter(scenario=["ssp585"]),
        output_variables=(
            "Surface Air Ocean Blended Temperature Change",
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
            "Surface Air Ocean Blended Temperature Change",
            "Heat Uptake|Ocean",
            "Heat Content|Ocean",
        ),
    )

    assert (
        res_default_factors.filter(
            variable="Surface Air Ocean Blended Temperature Change",
            region="World",
            year=2100,
            scenario="ssp585",
        ).values
        != res_custom_factors.filter(
            variable="Surface Air Ocean Blended Temperature Change",
            region="World",
            year=2100,
            scenario="ssp585",
        ).values
    )


def test_startyear(test_scenarios, test_scenarios_2600):
    # we can't run different start years in the same ensemble as output files will differ in shape.
    # There is a separate test to ensure this does raise an error.
    res_1850 = run(
        climate_models_cfgs={"FaIR": [{"startyear": 1850}]},
        scenarios=test_scenarios.filter(scenario=["ssp245"]),
        output_variables=("Surface Air Temperature Change",),
        out_config=None,
    )

    res_1750 = run(
        climate_models_cfgs={"FaIR": [{"startyear": 1750}]},
        scenarios=test_scenarios.filter(scenario=["ssp245"]),
        output_variables=("Surface Air Temperature Change",),
        out_config=None,
    )

    res_default = run(
        climate_models_cfgs={"FaIR": [{}]},
        scenarios=test_scenarios.filter(scenario=["ssp245"]),
        output_variables=("Surface Air Temperature Change",),
        out_config=None,
    )

    gsat2100_start1850 = res_1850.filter(
        variable="Surface Air Temperature Change", region="World", year=2100,
    ).values

    gsat2100_start1750 = res_1750.filter(
        variable="Surface Air Temperature Change", region="World", year=2100,
    ).values

    gsat2100_startdefault = res_default.filter(
        variable="Surface Air Temperature Change", region="World", year=2100,
    ).values

    assert gsat2100_start1850 != gsat2100_start1750
    assert gsat2100_start1750 == gsat2100_startdefault

    with pytest.raises(ValueError):
        run(
            climate_models_cfgs={"FaIR": [{"startyear": 1650}]},
            scenarios=test_scenarios.filter(scenario=["ssp245"]),
            output_variables=("Surface Air Temperature Change",),
            out_config=None,
        )

    with pytest.raises(ValueError):
        run(
            climate_models_cfgs={"FaIR": [{}]},
            scenarios=test_scenarios_2600.filter(scenario=["ssp245"]),
            output_variables=("Surface Air Temperature Change",),
            out_config=None,
        )

    with pytest.raises(ValueError):
        run(
            climate_models_cfgs={"FaIR": [{"startyear": 1750}, {"startyear": 1850}]},
            scenarios=test_scenarios.filter(scenario=["ssp245"]),
            output_variables=("Surface Air Temperature Change",),
            out_config=None,
        )
