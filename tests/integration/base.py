from abc import ABC, abstractmethod

import numpy.testing as npt
from scmdata import ScmRun

from openscm_runner import run


class _AdapterTester(ABC):
    """
    Base class for testing adapters.

    All adapters should have a test class which sub-classes this class and
    implements all abstract methods.
    """

    """float: relative tolerance for numeric comparisons"""
    _rtol = 1e-5


    """
    tuple[str]: variable names which are expected to be used by all adapters

    This could be replaced with the RCMIP variables in future (bigger job)
    """
    _common_variables = (
        "Surface Air Temperature Change",
        "Surface Air Ocean Blended Temperature Change",
        "Effective Radiative Forcing",
        "Effective Radiative Forcing|Anthropogenic",
        "Effective Radiative Forcing|Aerosols",
        "Effective Radiative Forcing|Aerosols|Direct Effect",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC AFOLU",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC AFOLU",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC AFOLU",
        "Effective Radiative Forcing|Aerosols|Indirect Effect",
        "Effective Radiative Forcing|Greenhouse Gases",
        "Effective Radiative Forcing|CO2",
        "Effective Radiative Forcing|CH4",
        "Effective Radiative Forcing|N2O",
        "Effective Radiative Forcing|F-Gases",
        "Effective Radiative Forcing|HFC125",
        "Effective Radiative Forcing|HFC134a",
        "Effective Radiative Forcing|HFC143a",
        "Effective Radiative Forcing|HFC227ea",
        "Effective Radiative Forcing|HFC23",
        "Effective Radiative Forcing|HFC245fa",
        "Effective Radiative Forcing|HFC32",
        "Effective Radiative Forcing|HFC4310mee",
        "Effective Radiative Forcing|CF4",
        "Effective Radiative Forcing|C6F14",
        "Effective Radiative Forcing|C2F6",
        "Effective Radiative Forcing|SF6",
        "Heat Uptake",
        "Heat Uptake|Ocean",
        "Atmospheric Concentrations|CO2",
        "Atmospheric Concentrations|CH4",
        "Atmospheric Concentrations|N2O",
        "Net Atmosphere to Land Flux|CO2",
        "Net Atmosphere to Ocean Flux|CO2",
    )

    def _check_res(self, exp, check_val, raise_error):
        try:
            npt.assert_allclose(exp, check_val, rtol=self._rtol)
        except AssertionError:
            if raise_error:
                raise

            print("exp: {}, check_val: {}".format(exp, check_val))

    @abstractmethod
    def test_run(self, test_scenarios):
        """
        Test that the model can be run, ideally with more than one configuration
        """
        # pseudo-code
        res = run(
            climate_models_cfgs={
                "climate_model": [
                    {"para1": "value1", "para2": 1.1},
                    {"para1": "value3", "para2": 1.2},
                    {"para1": "value5", "para2": 1.3},
                ],
            },
            scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
            output_variables=(
                "output",
                "var",
                "list",
            ),
            out_config=None,
        )

        assert isinstance(res, ScmRun)
        assert res["run_id"].min() == 0
        assert res["run_id"].max() == 8

        assert res.get_unique_meta("climate_model", no_duplicates=True) == "model_name"

        assert set(res.get_unique_meta("variable")) == set(
            [
                "expected",
                "output",
                "variables"
            ]
        )

        # output value checks e.g.
        npt.assert_allclose(
            2.31,
            res.filter(
                variable="Surface Air Temperature Change",
                region="World",
                year=2100,
                scenario="ssp126",
            ).values.max(),
            rtol=self._rtol,
        )

    @abstractmethod
    def test_variable_naming(self, test_scenarios):
        """
        Test that variable naming is implemented as expecteds
        """
        # pseudo-code

        # a model might not report all outputs
        missing_variables = (
            "Net Atmosphere to Ocean Flux|CO2",
            "Net Atmosphere to Land Flux|CO2",
        )
        common_variables = [c for c in self._common_variables if c not in missing_variables]

        # run the model and request all common variables the model reportss
        res = run(
            climate_models_cfgs={"climate_model": ({"para1": 3.43},)},
            scenarios=test_scenarios.filter(scenario="ssp126"),
            output_variables=common_variables,
        )

        # check that all expected outputs were returned
        missing_vars = set(common_variables) - set(res["variable"])
        if missing_vars:
            raise AssertionError(missing_vars)

