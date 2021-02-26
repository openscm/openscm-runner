import numpy as np
import numpy.testing as npt
import pytest
from base import _AdapterTester
from scmdata import ScmRun

from openscm_runner import run
from openscm_runner.adapters import FAIR
from openscm_runner.utils import calculate_quantiles


class TestFairAdapter(_AdapterTester):
    def test_run(self, test_scenarios):
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
    # we can't run different start years in the same ensemble as output files will differ in shape. There is a separate test to ensure this does raise an error.
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


def test_forcing_categories(test_scenarios):
    forcing_categories = [
        "Effective Radiative Forcing|CO2",
        "Effective Radiative Forcing|CH4",
        "Effective Radiative Forcing|N2O",
        "Effective Radiative Forcing|CF4",
        "Effective Radiative Forcing|C2F6",
        "Effective Radiative Forcing|C6F14",
        "Effective Radiative Forcing|HFC23",
        "Effective Radiative Forcing|HFC32",
        "Effective Radiative Forcing|HFC125",
        "Effective Radiative Forcing|HFC134a",
        "Effective Radiative Forcing|HFC143a",
        "Effective Radiative Forcing|HFC227ea",
        "Effective Radiative Forcing|HFC245fa",
        "Effective Radiative Forcing|HFC4310mee",
        "Effective Radiative Forcing|SF6",
        "Effective Radiative Forcing|CFC11",
        "Effective Radiative Forcing|CFC12",
        "Effective Radiative Forcing|CFC113",
        "Effective Radiative Forcing|CFC114",
        "Effective Radiative Forcing|CFC115",
        "Effective Radiative Forcing|CCl4",
        "Effective Radiative Forcing|CH3CCl3",
        "Effective Radiative Forcing|HCFC22",
        "Effective Radiative Forcing|HCFC141b",
        "Effective Radiative Forcing|HCFC142b",
        "Effective Radiative Forcing|Halon1211",
        "Effective Radiative Forcing|Halon1202",
        "Effective Radiative Forcing|Halon1301",
        "Effective Radiative Forcing|Halon2402",
        "Effective Radiative Forcing|CH3Br",
        "Effective Radiative Forcing|CH3Cl",
        "Effective Radiative Forcing|Tropospheric Ozone",
        "Effective Radiative Forcing|Stratospheric Ozone",
        "Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O",
        "Effective Radiative Forcing|Contrails",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        "Effective Radiative Forcing|Aerosols|Direct Effect|Secondary Organic Aerosol",
        "Effective Radiative Forcing|Aerosols|Direct Effect|Nitrate",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        "Effective Radiative Forcing|Aerosols|Indirect Effect",
        "Effective Radiative Forcing|Black Carbon on Snow",
        "Effective Radiative Forcing|Land-use Change",
        "Effective Radiative Forcing|Volcanic",
        "Effective Radiative Forcing|Solar",
        "Effective Radiative Forcing",
        "Effective Radiative Forcing|Anthropogenic",
        "Effective Radiative Forcing|Greenhouse Gases",
        "Effective Radiative Forcing|Kyoto Gases",
        "Effective Radiative Forcing|CO2, CH4 and N2O",
        "Effective Radiative Forcing|F-Gases",
        "Effective Radiative Forcing|Montreal Protocol Halogen Gases",
        "Effective Radiative Forcing|Aerosols|Direct Effect",
        "Effective Radiative Forcing|Aerosols",
        "Effective Radiative Forcing|Ozone",
        "Effective Radiative Forcing",
    ]

    res = run(
        climate_models_cfgs={"FaIR":
            [
                {},
            ],
        },
        scenarios=test_scenarios.filter(scenario=["ssp245"]),
        output_variables=tuple(forcing_categories),
        out_config=None,
    )

    # storing results in a dict makes this a bit more compact
    forcing = {}
    for variable in forcing_categories:
        forcing[variable] = res.filter(variable=variable, region="World").values

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|CO2"]
        + forcing["Effective Radiative Forcing|CH4"]
        + forcing["Effective Radiative Forcing|N2O"]
        + forcing["Effective Radiative Forcing|CF4"]
        + forcing["Effective Radiative Forcing|C2F6"]
        + forcing["Effective Radiative Forcing|C6F14"]
        + forcing["Effective Radiative Forcing|HFC23"]
        + forcing["Effective Radiative Forcing|HFC32"]
        + forcing["Effective Radiative Forcing|HFC125"]
        + forcing["Effective Radiative Forcing|HFC134a"]
        + forcing["Effective Radiative Forcing|HFC143a"]
        + forcing["Effective Radiative Forcing|HFC227ea"]
        + forcing["Effective Radiative Forcing|HFC245fa"]
        + forcing["Effective Radiative Forcing|HFC4310mee"]
        + forcing["Effective Radiative Forcing|SF6"]
        + forcing["Effective Radiative Forcing|CFC11"]
        + forcing["Effective Radiative Forcing|CFC12"]
        + forcing["Effective Radiative Forcing|CFC113"]
        + forcing["Effective Radiative Forcing|CFC114"]
        + forcing["Effective Radiative Forcing|CFC115"]
        + forcing["Effective Radiative Forcing|CCl4"]
        + forcing["Effective Radiative Forcing|CH3CCl3"]
        + forcing["Effective Radiative Forcing|HCFC22"]
        + forcing["Effective Radiative Forcing|HCFC141b"]
        + forcing["Effective Radiative Forcing|HCFC142b"]
        + forcing["Effective Radiative Forcing|Halon1211"]
        + forcing["Effective Radiative Forcing|Halon1202"]
        + forcing["Effective Radiative Forcing|Halon1301"]
        + forcing["Effective Radiative Forcing|Halon2402"]
        + forcing["Effective Radiative Forcing|CH3Br"]
        + forcing["Effective Radiative Forcing|CH3Cl"],
        forcing[
            "Effective Radiative Forcing|Greenhouse Gases"
        ],  # should this be "well mixed" greenhouse gases?
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|CO2"]
        + forcing["Effective Radiative Forcing|CH4"]
        + forcing["Effective Radiative Forcing|N2O"]
        + forcing["Effective Radiative Forcing|CF4"]
        + forcing["Effective Radiative Forcing|C2F6"]
        + forcing["Effective Radiative Forcing|C6F14"]
        + forcing["Effective Radiative Forcing|HFC23"]
        + forcing["Effective Radiative Forcing|HFC32"]
        + forcing["Effective Radiative Forcing|HFC125"]
        + forcing["Effective Radiative Forcing|HFC134a"]
        + forcing["Effective Radiative Forcing|HFC143a"]
        + forcing["Effective Radiative Forcing|HFC227ea"]
        + forcing["Effective Radiative Forcing|HFC245fa"]
        + forcing["Effective Radiative Forcing|HFC4310mee"]
        + forcing["Effective Radiative Forcing|SF6"],
        forcing["Effective Radiative Forcing|Kyoto Gases"],
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|CO2"]
        + forcing["Effective Radiative Forcing|CH4"]
        + forcing["Effective Radiative Forcing|N2O"],
        forcing["Effective Radiative Forcing|CO2, CH4 and N2O"],
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|CF4"]
        + forcing["Effective Radiative Forcing|C2F6"]
        + forcing["Effective Radiative Forcing|C6F14"]
        + forcing["Effective Radiative Forcing|HFC23"]
        + forcing["Effective Radiative Forcing|HFC32"]
        + forcing["Effective Radiative Forcing|HFC125"]
        + forcing["Effective Radiative Forcing|HFC134a"]
        + forcing["Effective Radiative Forcing|HFC143a"]
        + forcing["Effective Radiative Forcing|HFC227ea"]
        + forcing["Effective Radiative Forcing|HFC245fa"]
        + forcing["Effective Radiative Forcing|HFC4310mee"]
        + forcing["Effective Radiative Forcing|SF6"],
        forcing["Effective Radiative Forcing|F-Gases"],
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|CFC11"]
        + forcing["Effective Radiative Forcing|CFC12"]
        + forcing["Effective Radiative Forcing|CFC113"]
        + forcing["Effective Radiative Forcing|CFC114"]
        + forcing["Effective Radiative Forcing|CFC115"]
        + forcing["Effective Radiative Forcing|CCl4"]
        + forcing["Effective Radiative Forcing|CH3CCl3"]
        + forcing["Effective Radiative Forcing|HCFC22"]
        + forcing["Effective Radiative Forcing|HCFC141b"]
        + forcing["Effective Radiative Forcing|HCFC142b"]
        + forcing["Effective Radiative Forcing|Halon1211"]
        + forcing["Effective Radiative Forcing|Halon1202"]
        + forcing["Effective Radiative Forcing|Halon1301"]
        + forcing["Effective Radiative Forcing|Halon2402"]
        + forcing["Effective Radiative Forcing|CH3Br"]
        + forcing["Effective Radiative Forcing|CH3Cl"],
        forcing["Effective Radiative Forcing|Montreal Protocol Halogen Gases"],
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|Tropospheric Ozone"]
        + forcing["Effective Radiative Forcing|Stratospheric Ozone"],
        forcing["Effective Radiative Forcing|Ozone"],
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|Aerosols|Direct Effect|SOx"]
        + forcing[
            "Effective Radiative Forcing|Aerosols|Direct Effect|Secondary Organic Aerosol"
        ]
        + forcing["Effective Radiative Forcing|Aerosols|Direct Effect|Nitrate"]
        + forcing["Effective Radiative Forcing|Aerosols|Direct Effect|BC"]
        + forcing["Effective Radiative Forcing|Aerosols|Direct Effect|OC"],
        forcing["Effective Radiative Forcing|Aerosols|Direct Effect"],
    )

    # If up to here is fine, then we only need to check previouly defined aggregates against "super-aggregates"
    npt.assert_allclose(
        forcing["Effective Radiative Forcing|Aerosols|Direct Effect"]
        + forcing["Effective Radiative Forcing|Aerosols|Indirect Effect"],
        forcing["Effective Radiative Forcing|Aerosols"],
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|Greenhouse Gases"]
        + forcing["Effective Radiative Forcing|Ozone"]
        + forcing["Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O"]
        + forcing["Effective Radiative Forcing|Contrails"]
        + forcing["Effective Radiative Forcing|Aerosols"]
        + forcing["Effective Radiative Forcing|Black Carbon on Snow"]
        + forcing["Effective Radiative Forcing|Land-use Change"],
        forcing["Effective Radiative Forcing|Anthropogenic"],
    )

    npt.assert_allclose(
        forcing["Effective Radiative Forcing|Anthropogenic"]
        + forcing["Effective Radiative Forcing|Volcanic"]
        + forcing["Effective Radiative Forcing|Solar"],
        forcing["Effective Radiative Forcing"],
    )
