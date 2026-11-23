"""
Unit tests of the MAGICC AR6 adapters' code paths which don't need MAGICC

Mostly error paths and options our integration tests don't use.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pandas as pd
import pytest
from openscm_runner.adapters.magicc_ar6 import (
    MAGICCAR6AdapterAR6Scenario,
    MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
    MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
    MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6AdapterERFDrivenFromEquilibrium,
    MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial,
    MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial,
    MAGICCAR6AdapterESMFromCMIP6PreIndustrial,
    MAGICCAR6AdapterESMFromCMIP7PreIndustrial,
)
from openscm_runner.adapters.magicc_ar6 import base as base_module
from openscm_runner.adapters.magicc_ar6.ar_scenarios import with_missing_emissions
from openscm_runner.adapters.magicc_ar6.base import (
    MAGICCAR6Experiment,
    _to_member_result,
)
from openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch import (
    ALL_CONCENTRATION_GASES,
    PI_CONTROL_EMISSIONS_GASES,
    get_pi_control_concentrations,
    get_pi_control_emissions,
)
from openscm_runner.adapters.magicc_ar6.ensemble import load_ar6_ensemble
from openscm_runner.adapters.magicc_ar6.naming import EMISSIONS_VARIABLES
from openscm_runner.adapters.magicc_ar6.optional_dependencies import (
    MissingOptionalDependencyError,
    import_optional_dependency,
)
from openscm_runner.adapters.magicc_ar6.pre_industrial import (
    CMIP6_PRE_INDUSTRIAL,
    CMIP7_PRE_INDUSTRIAL,
    PreIndustrialValues,
)
from openscm_runner.adapters.magicc_ar6.running import (
    EnsembleMember,
    MAGICCMemberResult,
)
from openscm_runner.output_specs import OutputSpecs

from openscm_runner.adapter_errors import InvalidInputError

# These are the MAGICC AR6 adapters' tests (see docs/testing.md)
pytestmark = pytest.mark.magicc_ar6

NOT_USED_CONFIGURATION_KWARGS: dict[str, Any] = dict(
    magicc_root=Path("not-used"), ar6_probabilistic_distribution=Path("not-used")
)


@pytest.mark.parametrize(
    "adapter_cls",
    (
        pytest.param(MAGICCAR6AdapterAR6Scenario, id="ar6-scenario"),
        pytest.param(
            MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
            id="ar6-scenario-anthropogenic-only",
        ),
        pytest.param(
            MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
            id="ar6-scenario-co2-forcing-only",
        ),
        pytest.param(
            MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
            id="conc-cmip7",
        ),
        pytest.param(
            MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
            id="conc-cmip6",
        ),
        pytest.param(
            MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
            id="co2-conc-cmip7",
        ),
        pytest.param(
            MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
            id="co2-conc-cmip6",
        ),
        pytest.param(
            MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
            id="co2-emms-cmip7",
        ),
        pytest.param(
            MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
            id="co2-emms-cmip6",
        ),
        pytest.param(MAGICCAR6AdapterESMFromCMIP7PreIndustrial, id="esm-cmip7"),
        pytest.param(MAGICCAR6AdapterESMFromCMIP6PreIndustrial, id="esm-cmip6"),
        pytest.param(
            MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial, id="esm-all-ghg-cmip7"
        ),
        pytest.param(
            MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial, id="esm-all-ghg-cmip6"
        ),
        pytest.param(MAGICCAR6AdapterERFDrivenFromEquilibrium, id="erf"),
    ),
)
def test_run_checks_false_skips_the_input_checks(adapter_cls: type) -> None:
    """
    Without the checks, invalid input gets past the adapter's input checks

    Here, it then fails on the unsupported output variable,
    which the adapters check before they need MAGICC.
    """
    invalid_input = (pd.DataFrame(),)
    output_specs = OutputSpecs(output_variables=("Not a variable",))

    with_checks = adapter_cls(
        configuration=MAGICCAR6AdapterConfiguration(**NOT_USED_CONFIGURATION_KWARGS)
    )
    with pytest.raises(InvalidInputError):
        with_checks(invalid_input, output_specs=output_specs)

    without_checks = adapter_cls(
        configuration=MAGICCAR6AdapterConfiguration(
            **NOT_USED_CONFIGURATION_KWARGS, run_checks=False
        )
    )
    with pytest.raises(ValueError, match="aren't supported by this adapter"):
        without_checks(invalid_input, output_specs=output_specs)


# Just actually load all the ensemble members and check that all 600 are loaded,
# don't check the loaded values.
def test_load_ensemble_all_members(monkeypatch: pytest.MonkeyPatch) -> None:
    ensemble = tuple(EnsembleMember(id=str(i), configuration={}) for i in range(5))
    monkeypatch.setattr(base_module, "load_ar6_ensemble", lambda path: ensemble)

    configuration = MAGICCAR6AdapterConfiguration(**NOT_USED_CONFIGURATION_KWARGS)
    assert configuration.load_ensemble() == ensemble

    first_two = MAGICCAR6AdapterConfiguration(
        **NOT_USED_CONFIGURATION_KWARGS, testing_only_n_members=2
    )
    assert first_two.load_ensemble() == ensemble[:2]


def test_load_ar6_ensemble_wrong_file(tmp_path: Path) -> None:
    path = tmp_path / "not-the-distribution.json"
    path.write_text('{"configurations": []}')

    with pytest.raises(ValueError, match="isn't the AR6 probabilistic distribution"):
        load_ar6_ensemble(path)


def test_member_result_output_conversion_failure() -> None:
    """If MAGICC's output can't be converted, that member fails (not the run)"""
    experiment = MAGICCAR6Experiment(
        files={},
        settings={},
        start_year=1850,
        end_year=1855,
        output_first_year=1850,
        output_last_year=1850,
        output_variables={"Surface Air Temperature Change": "SURFACE_TEMP"},
        experiment_levels={},
    )
    # No SURFACE_TEMP in the output
    raw = pd.DataFrame(
        [[0.0]],
        index=pd.MultiIndex.from_tuples(
            [("CO2_CONC", "GLOBAL", "ppm")], names=["variable", "region", "unit"]
        ),
        columns=[1850],
    )

    res = _to_member_result(
        MAGICCMemberResult(member_id="0", data=raw), experiment=experiment
    )

    assert not res.succeeded
    assert isinstance(res.error, KeyError)


def test_with_missing_emissions_nothing_missing() -> None:
    emissions = pd.DataFrame(
        [[1.0, 1.0] for _ in EMISSIONS_VARIABLES.values()],
        index=pd.MultiIndex.from_tuples(
            [(spec.gas, spec.unit) for spec in EMISSIONS_VARIABLES.values()],
            names=["variable", "unit"],
        ),
        columns=[2015, 2016],
    )

    res = with_missing_emissions(emissions, fill_values={})

    pd.testing.assert_frame_equal(res, emissions)


def test_get_pi_control_emissions_only_co2() -> None:
    """piControl CO2 emissions are zero, so with only CO2, everything is zero"""
    pre_industrial = PreIndustrialValues(
        name="only-co2",
        pi_control_concentrations=CMIP7_PRE_INDUSTRIAL.pi_control_concentrations,
        historical_emissions_1850=MappingProxyType(
            {
                "Emissions|CO2|Fossil": (1.0, "Gt C/yr"),
                "Emissions|CO2|Biosphere": (1.0, "Gt C/yr"),
            }
        ),
    )

    assert get_pi_control_emissions(pre_industrial) == dict.fromkeys(
        PI_CONTROL_EMISSIONS_GASES, 0.0
    )


def test_get_pi_control_values_converted_to_magicc() -> None:
    """The pre-industrial values are converted to MAGICC's names and units"""
    concentrations = get_pi_control_concentrations(CMIP6_PRE_INDUSTRIAL)
    assert list(concentrations) == list(ALL_CONCENTRATION_GASES)
    assert concentrations["CO2"] == pytest.approx(284.3169987996419)
    assert concentrations["CH3CL"] == pytest.approx(457.00000254313153)
    # Not in the CMIP datasets
    assert concentrations["HALON1202"] == 0.0

    emissions = get_pi_control_emissions(CMIP6_PRE_INDUSTRIAL)
    assert list(emissions) == list(PI_CONTROL_EMISSIONS_GASES)
    # CO2 is zero (see roadmap item B19)
    assert emissions["CO2I"] == 0.0
    assert emissions["CO2B"] == 0.0
    # 13.46 Mt NOx (as NO2) / yr
    assert emissions["NOX"] == pytest.approx(4.095479910026472)
    # 4.54 Mt SO2 / yr
    assert emissions["SOX"] == pytest.approx(2.272231887773452)
    # 559 kt N2O / yr
    assert emissions["N2O"] == pytest.approx(0.3557483535357818)
    # 9.60 Mt NH3 / yr
    assert emissions["NH3"] == pytest.approx(7.909310341080795)
    assert emissions["NMVOC"] == pytest.approx(66.78304875030415)
    assert emissions["CH3CL"] == pytest.approx(4267.6083)


def test_pre_industrial_unknown_concentration() -> None:
    pre_industrial = PreIndustrialValues(
        name="unknown-concentration",
        pi_control_concentrations=MappingProxyType(
            {"Atmospheric Concentrations|NOT_A_GAS": (1.0, "ppt")}
        ),
        historical_emissions_1850=MappingProxyType({}),
    )
    with pytest.raises(ValueError, match="NOT_A_GAS"):
        get_pi_control_concentrations(pre_industrial)


def test_pre_industrial_unknown_emissions() -> None:
    pre_industrial = PreIndustrialValues(
        name="unknown-emissions",
        pi_control_concentrations=MappingProxyType({}),
        historical_emissions_1850=MappingProxyType(
            {"Emissions|NOT_A_GAS": (1.0, "kt NOT_A_GAS/yr")}
        ),
    )
    with pytest.raises(ValueError, match="NOT_A_GAS"):
        get_pi_control_emissions(pre_industrial)


def test_missing_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import_module = importlib.import_module

    def import_module(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "f90nml":
            raise ImportError(name)

        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", import_module)

    with pytest.raises(
        MissingOptionalDependencyError,
        match=r"`read_namelist` requires f90nml to be installed",
    ):
        import_optional_dependency(
            "f90nml", requirement="f90nml", callable_name="read_namelist"
        )
