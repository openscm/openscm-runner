"""
The verify functions catch invalid inputs when called via the `run_*` functions

The adapter must never be called when the inputs are invalid.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pytest

from openscm_runner import (
    InvalidInputError,
    OutputSpecs,
    UnsupportedOutputError,
    run_ar6_scenarios,
    run_ar6_scenarios_anthropogenic_only,
    run_ar6_scenarios_co2_forcing_only,
    run_ar7_scenarios,
    run_co2_concentration_driven_from_cmip6_pre_industrial,
    run_co2_concentration_driven_from_cmip7_pre_industrial,
    run_co2_emission_driven_from_cmip6_pre_industrial,
    run_co2_emission_driven_from_cmip7_pre_industrial,
    run_concentration_driven_from_cmip6_pre_industrial,
    run_concentration_driven_from_cmip7_pre_industrial,
    run_erf_driven_from_equilibrium,
    run_esm_all_ghg_from_cmip6_pre_industrial,
    run_esm_all_ghg_from_cmip7_pre_industrial,
    run_esm_from_cmip6_pre_industrial,
    run_esm_from_cmip7_pre_industrial,
)
from openscm_runner.ar_scenarios.inputs import (
    AR6_SCENARIO_CO2_EMISSIONS_VARIABLES,
    AR6_SCENARIO_EMISSIONS_VARIABLES,
    AR7_SCENARIO_EMISSIONS_VARIABLES,
)
from openscm_runner.cmip_pre_industrial_branch.inputs import (
    CMIP_CONCENTRATION_DRIVEN_VARIABLES,
    CMIP_ESM_ALL_GHG_VARIABLES,
    CMIP_ESM_VARIABLES,
    CO2_CONCENTRATION_VARIABLES,
    CO2_EMISSION_VARIABLES,
)
from openscm_runner.output import EnsembleMemberResult, OpenSCMRunnerOutput

OUTPUT_SPECS = OutputSpecs(output_variables=("Surface Air Temperature Change",))


class RecordingAdapter:
    """Fake adapter that records whether it was called"""

    supported_output_variables = frozenset(OUTPUT_SPECS.output_variables)

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> tuple[OpenSCMRunnerOutput, ...]:
        self.calls.append(kwargs)
        (inputs,) = (v for k, v in kwargs.items() if k != "output_specs")
        return tuple(
            OpenSCMRunnerOutput(members=(EnsembleMemberResult.from_success("0", inp),))
            for inp in inputs
        )


@dataclass(frozen=True)
class Case:
    """An experiment type, its run function and how to make a valid input"""

    id: str
    run: Callable[..., Any]
    input_kwarg: str
    variables: frozenset[str]
    first_year: int
    first_year_fixed: bool
    last_year_at_most: int | None

    def make_valid_input(self, scenario: str = "scen") -> pd.DataFrame:
        variables = sorted(self.variables)
        years = list(range(self.first_year, self.first_year + 5))
        index = pd.MultiIndex.from_arrays(
            [
                ["model"] * len(variables),
                [scenario] * len(variables),
                variables,
                ["World"] * len(variables),
                ["unit"] * len(variables),
            ],
            names=["model", "scenario", "variable", "region", "unit"],
        )
        return pd.DataFrame(
            np.arange(len(variables) * len(years), dtype=float).reshape(
                len(variables), len(years)
            ),
            index=index,
            columns=years,
        )

    def call_run(self, inputs: Any, adapter: RecordingAdapter) -> Any:
        return self.run(
            **{self.input_kwarg: inputs},
            adapters=(adapter,),
            output_specs=OUTPUT_SPECS,
        )


CASES = (
    Case("ar7", run_ar7_scenarios, "ar7_scenarios", AR7_SCENARIO_EMISSIONS_VARIABLES,
         2023, True, 2500),
    Case("ar6", run_ar6_scenarios, "ar6_scenarios", AR6_SCENARIO_EMISSIONS_VARIABLES,
         2015, True, None),
    Case("ar6-anthropogenic-only", run_ar6_scenarios_anthropogenic_only,
         "ar6_scenarios", AR6_SCENARIO_EMISSIONS_VARIABLES, 2015, True, None),
    Case("ar6-co2-forcing-only", run_ar6_scenarios_co2_forcing_only,
         "ar6_co2_emissions", AR6_SCENARIO_CO2_EMISSIONS_VARIABLES, 2015, True, None),
    Case("co2-conc-cmip7", run_co2_concentration_driven_from_cmip7_pre_industrial,
         "co2_concentrations", CO2_CONCENTRATION_VARIABLES, 1850, True, None),
    Case("co2-conc-cmip6", run_co2_concentration_driven_from_cmip6_pre_industrial,
         "co2_concentrations", CO2_CONCENTRATION_VARIABLES, 1850, True, None),
    Case("conc-cmip7", run_concentration_driven_from_cmip7_pre_industrial,
         "concentrations", CMIP_CONCENTRATION_DRIVEN_VARIABLES, 1850, True, None),
    Case("conc-cmip6", run_concentration_driven_from_cmip6_pre_industrial,
         "concentrations", CMIP_CONCENTRATION_DRIVEN_VARIABLES, 1850, True, None),
    Case("co2-emms-cmip7", run_co2_emission_driven_from_cmip7_pre_industrial,
         "co2_emissions", CO2_EMISSION_VARIABLES, 1850, True, None),
    Case("co2-emms-cmip6", run_co2_emission_driven_from_cmip6_pre_industrial,
         "co2_emissions", CO2_EMISSION_VARIABLES, 1850, True, None),
    Case("esm-cmip7", run_esm_from_cmip7_pre_industrial,
         "esm_inputs", CMIP_ESM_VARIABLES, 1850, True, None),
    Case("esm-cmip6", run_esm_from_cmip6_pre_industrial,
         "esm_inputs", CMIP_ESM_VARIABLES, 1850, True, None),
    Case("esm-all-ghg-cmip7", run_esm_all_ghg_from_cmip7_pre_industrial,
         "esm_all_ghg_inputs", CMIP_ESM_ALL_GHG_VARIABLES, 1850, True, None),
    Case("esm-all-ghg-cmip6", run_esm_all_ghg_from_cmip6_pre_industrial,
         "esm_all_ghg_inputs", CMIP_ESM_ALL_GHG_VARIABLES, 1850, True, None),
    # ERF can start in any year, 1750 is arbitrary
    Case("erf", run_erf_driven_from_equilibrium, "erf",
         frozenset({"Effective Radiative Forcing"}),
         1750, False, None),
)  # fmt: skip


@dataclass(frozen=True)
class Invalidation:
    """A way of making a valid input invalid"""

    id: str
    apply: Callable[[Case, pd.DataFrame], pd.DataFrame]
    match: str
    applies_to: Callable[[Case], bool] = lambda case: True


def _drop_first_year(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return df.iloc[:, 1:]


def _add_year_before_start(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.insert(0, case.first_year - 1, 0.0)
    return out


def _extend_past_cap(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    assert case.last_year_at_most is not None
    years = range(df.columns[-1] + 1, case.last_year_at_most + 2)
    extension = pd.DataFrame(0.0, index=df.index, columns=list(years))
    return pd.concat([df, extension], axis="columns")


def _drop_variable(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return df.iloc[1:, :]


def _add_variable(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    extra = df.iloc[:1, :].rename(lambda v: "Emissions|Unobtainium", level="variable")
    return pd.concat([df, extra])


def _change_region(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(lambda r: "R5ASIA", level="region")


def _set_nan(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.iloc[0, 1] = np.nan
    return out


def _set_inf(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.iloc[0, 1] = np.inf
    return out


def _make_gap(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=df.columns[2])


def _string_years(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=str)


def _duplicate_row(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([df, df.iloc[:1, :]])


def _two_scenarios(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([df, case.make_valid_input(scenario="other")])


def _drop_unit_level(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return df.droplevel("unit")


def _non_numeric(case: Case, df: pd.DataFrame) -> pd.DataFrame:
    return df.astype(str)


INVALIDATIONS = (
    Invalidation(
        "first-year-too-late",
        _drop_first_year,
        "first year must be",
        applies_to=lambda case: case.first_year_fixed,
    ),
    Invalidation(
        "data-before-first-year",
        _add_year_before_start,
        "first year must be",
        applies_to=lambda case: case.first_year_fixed,
    ),
    Invalidation(
        "past-last-year-cap",
        _extend_past_cap,
        "last year must be at most",
        applies_to=lambda case: case.last_year_at_most is not None,
    ),
    # (For inputs with a single variable this empties the input,
    # which is also an error.)
    Invalidation("missing-variable", _drop_variable, "missing variables|is empty"),
    Invalidation("extra-variable", _add_variable, "unexpected variables"),
    Invalidation("non-world-region", _change_region, "unexpected regions"),
    Invalidation("nan", _set_nan, "must be finite"),
    Invalidation("inf", _set_inf, "must be finite"),
    Invalidation("gap-in-years", _make_gap, "must be consecutive years"),
    Invalidation("string-years", _string_years, "must be integer years"),
    Invalidation("duplicate-timeseries", _duplicate_row, "duplicate timeseries"),
    Invalidation(
        "more-than-one-experiment-in-one-input",
        _two_scenarios,
        "index level 'scenario' must have a single value",
    ),
    Invalidation("missing-index-level", _drop_unit_level, "missing index levels"),
    Invalidation("non-numeric-values", _non_numeric, "values must be numeric"),
)

CASE_INVALIDATION_PAIRS = [
    pytest.param(case, invalidation, id=f"{case.id}-{invalidation.id}")
    for case in CASES
    for invalidation in INVALIDATIONS
    if invalidation.applies_to(case)
]


@pytest.mark.parametrize("case, invalidation", CASE_INVALIDATION_PAIRS)
def test_invalid_input_is_caught(case: Case, invalidation: Invalidation) -> None:
    valid = case.make_valid_input()
    adapter = RecordingAdapter()

    # Control: the unmodified input passes,
    # so the error below really comes from the invalidation.
    results = case.call_run((valid,), adapter)
    assert results.all_succeeded
    assert len(adapter.calls) == 1
    adapter.calls.clear()

    # Invalid inputs either side of a valid one:
    # every input is verified and all problems are reported together
    invalid = invalidation.apply(case, valid)
    with pytest.raises(InvalidInputError, match=invalidation.match) as exc_info:
        case.call_run((invalid, valid, invalid), adapter)

    message = str(exc_info.value)
    assert "input 0:" in message
    assert "input 1:" not in message
    assert "input 2:" in message

    assert not adapter.calls


@pytest.mark.parametrize("case", [pytest.param(c, id=c.id) for c in CASES])
def test_empty_inputs_are_caught(case: Case) -> None:
    adapter = RecordingAdapter()
    with pytest.raises(InvalidInputError, match="nothing to run"):
        case.call_run((), adapter)

    assert not adapter.calls


@pytest.mark.parametrize("case", [pytest.param(c, id=c.id) for c in CASES])
def test_non_tuple_inputs_are_caught(case: Case) -> None:
    adapter = RecordingAdapter()
    with pytest.raises(InvalidInputError, match="must be a tuple"):
        # A common mistake: passing a single dataframe rather than a tuple
        case.call_run(case.make_valid_input(), adapter)

    assert not adapter.calls


@pytest.mark.parametrize("case", [CASES[0]], ids=["ar7"])
def test_scenario_inputs_do_not_require_halon1202(case: Case) -> None:
    valid = case.make_valid_input()
    adapter = RecordingAdapter()
    assert case.call_run((valid,), adapter).all_succeeded

    halon = valid.iloc[:1, :].rename(lambda _: "Emissions|Halon1202", level="variable")
    with pytest.raises(InvalidInputError, match=r"unexpected variables.*Halon1202"):
        case.call_run((pd.concat([valid, halon]),), adapter)

    assert len(adapter.calls) == 1


@pytest.mark.parametrize("case", [pytest.param(c, id=c.id) for c in CASES])
@pytest.mark.parametrize(
    "variables",
    [("Unsupported Diagnostic",)],
)
def test_output_variable_requests_checked_by_every_runner(case, variables):
    adapter = RecordingAdapter()
    inputs = (case.make_valid_input(),)
    specs = OutputSpecs(variables)
    results = case.run(
        **{case.input_kwarg: inputs}, adapters=(adapter,), output_specs=specs
    )
    assert not adapter.calls
    assert isinstance(results[0].error, UnsupportedOutputError)
    with pytest.raises(UnsupportedOutputError):
        _ = results[0].outputs

    unchecked = case.run(
        **{case.input_kwarg: inputs},
        adapters=(adapter,),
        output_specs=specs,
        run_checks=False,
    )
    assert unchecked.all_succeeded
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["output_specs"] is specs
