"""
Acceptance tests for the MAGICC AR6 adapters

MAGICC v7.5.3 with the AR6 probabilistic distribution.
"""

from __future__ import annotations

import functools
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pandas_openscm.comparison import compare_close
from pandas_openscm.io import load_timeseries_csv

from openscm_runner import (
    OutputSpecs,
    run_ar6_scenarios,
    run_ar6_scenarios_anthropogenic_only,
    run_ar6_scenarios_co2_forcing_only,
    run_erf_driven_from_equilibrium,
)
from openscm_runner.adapters.magicc_ar6 import (
    MAGICCAR6AdapterAR6Scenario,
    MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
    MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6AdapterERFDrivenFromEquilibrium,
)

# These are the MAGICC AR6 adapters' tests (see docs/testing.md)
pytestmark = pytest.mark.magicc_ar6

DATA_DIR = Path(__file__).parent / "data"
AR6_SCENARIOS_DIR = Path(__file__).parents[2] / "test-data" / "ar6-scenarios"
AR6_SCENARIO_FILE = AR6_SCENARIOS_DIR / "ar6-aim-cge-2-2-en-npi2020-900f.csv"
AR6_SCENARIO_INDEX_COLUMNS = ["model", "scenario", "region", "variable", "unit"]


@dataclass(frozen=True)
class Tolerance:
    """
    Tolerance for comparing one variable

    Values are close if
    `abs(actual - expected) <= absolute + relative * abs(expected)`.
    Both must be looser than the rounding in the data files
    (six significant figures).
    """

    absolute: float
    relative: float


@dataclass(frozen=True)
class AcceptanceCase:
    """An acceptance test case"""

    experiment: str
    """Name of the sub-directory of `data/` holding this case's expected output"""

    input_file: Path
    """File holding the inputs"""

    index_columns: list[str]
    """Index columns of the input (the expected output also has `ensemble_member`)"""

    run: Callable[..., Any]
    """`run_*` function to run with"""

    input_kwarg: str
    """Name of the `run_*` function's input argument"""

    adapter_cls: type
    """Adapter to test"""

    n_members: int
    """Number of ensemble members (from the start of the distribution) to run"""

    n_workers: int
    """Number of MAGICC copies to run at once"""

    tolerance: Tolerance | Mapping[str, Tolerance]
    """Tolerance for every output variable, or for each one"""

    input_variables: tuple[str, ...] | None = None
    """Variables from the input file to pass to the adapter (all if `None`)"""


ACCEPTANCE_CASES = (
    AcceptanceCase(
        experiment="erf-driven-from-equilibrium",
        input_file=DATA_DIR / "erf-driven-from-equilibrium" / "input.csv",
        index_columns=["scenario", "variable", "region", "unit"],
        run=run_erf_driven_from_equilibrium,
        input_kwarg="erf",
        adapter_cls=MAGICCAR6AdapterERFDrivenFromEquilibrium,
        n_members=1,
        n_workers=1,
        tolerance={
            "Surface Air Temperature Change": Tolerance(absolute=1e-5, relative=1e-5),
            "Effective Radiative Forcing": Tolerance(absolute=1e-6, relative=1e-5),
            "Heat Uptake": Tolerance(absolute=1e-5, relative=1e-5),
        },
    ),
    AcceptanceCase(
        experiment="ar6-scenario",
        # Shared with other tests
        input_file=AR6_SCENARIO_FILE,
        index_columns=AR6_SCENARIO_INDEX_COLUMNS,
        run=run_ar6_scenarios,
        input_kwarg="ar6_scenarios",
        adapter_cls=MAGICCAR6AdapterAR6Scenario,
        n_members=1,
        n_workers=1,
        # The absolute tolerance is for values which cross zero
        # (e.g. stratospheric ozone forcing)
        tolerance=Tolerance(absolute=1e-6, relative=1e-5),
    ),
    AcceptanceCase(
        experiment="ar6-scenario-anthropogenic-only",
        input_file=AR6_SCENARIO_FILE,
        index_columns=AR6_SCENARIO_INDEX_COLUMNS,
        run=run_ar6_scenarios_anthropogenic_only,
        input_kwarg="ar6_scenarios",
        adapter_cls=MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
        n_members=1,
        n_workers=1,
        # As for `ar6-scenario`
        tolerance=Tolerance(absolute=1e-6, relative=1e-5),
    ),
    # This may still change: what is meant by CO2-only is still unclear
    # (e.g. which feedbacks should be included, see decision B16)
    AcceptanceCase(
        experiment="ar6-scenario-co2-forcing-only",
        input_file=AR6_SCENARIO_FILE,
        index_columns=AR6_SCENARIO_INDEX_COLUMNS,
        run=run_ar6_scenarios_co2_forcing_only,
        input_kwarg="ar6_co2_emissions",
        adapter_cls=MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
        n_members=1,
        n_workers=1,
        # As for `ar6-scenario`
        tolerance=Tolerance(absolute=1e-6, relative=1e-5),
        # The adapter only takes the CO2 emissions
        input_variables=("Emissions|CO2|Biosphere", "Emissions|CO2|Fossil"),
    ),
)


def load_csv(path: Path, index_columns: list[str]) -> pd.DataFrame:
    """Load one of the data files"""
    out = load_timeseries_csv(path, index_columns=index_columns, out_columns_type=int)
    if "ensemble_member" in index_columns:
        # IDs are strings, even if they look like numbers
        out = out.rename(str, level="ensemble_member")

    return out


def split_by_experiment(df: pd.DataFrame, level: str) -> tuple[pd.DataFrame, ...]:
    """Split a dataframe into one dataframe per experiment"""
    return tuple(group for _, group in df.groupby(level=level, sort=False))


def get_first_member_id(ar6_probabilistic_distribution: Path) -> str:
    """
    Get the ID of the first member of the AR6 probabilistic distribution

    Read directly from the file (not via the adapter),
    so we can check the adapter's IDs.
    """
    configurations = json.loads(ar6_probabilistic_distribution.read_text())[
        "configurations"
    ]

    return str(configurations[0]["paraset_id"])


def assert_close(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    tolerance: Tolerance | Mapping[str, Tolerance],
) -> None:
    """
    Check the outputs match the expected outputs

    Labels (index levels, timeseries and years) are compared exactly first,
    then the values with each variable's tolerance.
    """
    assert set(actual.index.names) == set(expected.index.names)
    expected = expected.reorder_levels(actual.index.names)
    assert sorted(actual.index) == sorted(expected.index)
    assert actual.columns.tolist() == expected.columns.tolist()

    for variable in expected.index.get_level_values("variable").unique():
        variable_tolerance = (
            tolerance if isinstance(tolerance, Tolerance) else tolerance[variable]
        )
        comparison = compare_close(
            actual.xs(variable, level="variable", drop_level=False),
            expected.xs(variable, level="variable", drop_level=False),
            left_name="actual",
            right_name="expected",
            isclose=functools.partial(
                np.isclose,
                atol=variable_tolerance.absolute,
                rtol=variable_tolerance.relative,
            ),
        )
        assert comparison.empty, f"{variable}:\n{comparison}"


@pytest.mark.parametrize(
    "case", [pytest.param(c, id=c.experiment) for c in ACCEPTANCE_CASES]
)
def test_acceptance(case: AcceptanceCase) -> None:
    inputs_all = load_csv(case.input_file, case.index_columns)
    if case.input_variables is not None:
        inputs_all = inputs_all.loc[
            inputs_all.index.get_level_values("variable").isin(case.input_variables)
        ]

    inputs = split_by_experiment(inputs_all, level="scenario")
    expected = split_by_experiment(
        load_csv(
            DATA_DIR / case.experiment / "expected-output.csv",
            [*case.index_columns, "ensemble_member"],
        ),
        level="scenario",
    )

    # Request exactly the variables we have expectations for
    output_specs = OutputSpecs(
        output_variables=tuple(
            pd.concat(expected).index.get_level_values("variable").unique()
        )
    )
    configuration = MAGICCAR6AdapterConfiguration.from_environment(
        testing_only_n_members=case.n_members,
        n_workers=case.n_workers,
    )
    adapter = case.adapter_cls(configuration=configuration)

    results = case.run(
        **{case.input_kwarg: inputs},
        adapters=(adapter,),
        output_specs=output_specs,
    )
    results.raise_if_any_failed()
    outputs = results[0].outputs

    assert len(outputs) == len(expected)
    for res, exp in zip(outputs, expected, strict=True):
        res.raise_if_any_failed()
        if case.n_members == 1:
            # We are comparing the member we think we are
            assert [m.ensemble_member for m in res.members] == [
                get_first_member_id(configuration.ar6_probabilistic_distribution)
            ]

        # The expected output only has some years
        assert_close(res.as_df().loc[:, exp.columns], exp, case.tolerance)


AR6_N_MEMBERS = 600

# AR6's post-processing settings
# (gcages' `AR6PostProcessor.from_ar6_config`, gcages commit abd4575)
AR6_QUANTILES = (0.05, 0.10, 1.0 / 6.0, 0.33, 0.50, 0.67, 5.0 / 6.0, 0.90, 0.95)
AR6_PRE_INDUSTRIAL_PERIOD = (1850, 1900)
AR6_ASSESSMENT_PERIOD = (1995, 2014)
AR6_ASSESSED_WARMING = 0.85
"""Assessed median warming over `AR6_ASSESSMENT_PERIOD`, relative to pre-industrial"""

AR6_PERCENTILE_VARIABLE = (
    "AR6 climate diagnostics|Surface Temperature (GSAT)|MAGICCv7.5.3|"
    "{percentile:.1f}th Percentile"
)


def to_ar6_temperature_percentiles(temperatures: pd.DataFrame) -> pd.DataFrame:
    """
    Post-process one scenario's raw temperatures as AR6 did

    Copied from gcages' `AR6PostProcessor` (gcages commit abd4575),
    so gcages isn't a dependency of our tests:
    relative to pre-industrial, shifted so the ensemble's median warming
    over the assessment period is the assessed warming,
    then percentiles across the ensemble.
    """
    rel_pi = temperatures.sub(
        temperatures.loc[:, slice(*AR6_PRE_INDUSTRIAL_PERIOD)].mean(axis="columns"),
        axis="rows",
    )
    assessment_period_median = (
        rel_pi.loc[:, slice(*AR6_ASSESSMENT_PERIOD)].mean(axis="columns").median()
    )
    assessed = rel_pi - assessment_period_median + AR6_ASSESSED_WARMING

    (model,) = temperatures.index.get_level_values("model").unique()
    (scenario,) = temperatures.index.get_level_values("scenario").unique()
    (unit,) = temperatures.index.get_level_values("unit").unique()

    return pd.DataFrame(
        [assessed.quantile(q) for q in AR6_QUANTILES],
        index=pd.MultiIndex.from_tuples(
            [
                (
                    model,
                    scenario,
                    "World",
                    AR6_PERCENTILE_VARIABLE.format(percentile=q * 100),
                    unit,
                )
                for q in AR6_QUANTILES
            ],
            names=AR6_SCENARIO_INDEX_COLUMNS,
        ),
    )


@pytest.mark.slow
def test_ar6_scenario_full_ensemble_matches_ar6() -> None:
    """The full ensemble reproduces AR6's published temperature percentiles"""
    scenario = load_csv(AR6_SCENARIO_FILE, AR6_SCENARIO_INDEX_COLUMNS)
    expected = load_csv(
        AR6_SCENARIOS_DIR / "ar6-aim-cge-2-2-en-npi2020-900f-ar6-gsat-percentiles.csv",
        AR6_SCENARIO_INDEX_COLUMNS,
    )
    # The first years are empty in the published data
    expected = expected.dropna(axis="columns", how="all")

    results = run_ar6_scenarios(
        (scenario,),
        adapters=(
            MAGICCAR6AdapterAR6Scenario(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    n_workers=os.cpu_count() or 1
                )
            ),
        ),
        output_specs=OutputSpecs(output_variables=("Surface Air Temperature Change",)),
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    assert len(output.members) == AR6_N_MEMBERS

    res = to_ar6_temperature_percentiles(
        output.as_df().xs("Surface Air Temperature Change", level="variable")
    )

    assert_close(
        res.loc[:, expected.columns],
        expected,
        tolerance=Tolerance(absolute=0.0, relative=1e-5),
    )
