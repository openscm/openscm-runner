"""
Shared helpers for the `verify_*` functions

Each input definition (e.g. [AR7Scenario][openscm_runner.ar_scenarios.inputs.])
has its own "verify" function
(e.g. [verify_ar7_scenarios][openscm_runner.ar_scenarios.inputs.])
and that function is the definition of the input's shape.
Most of them check the same kind of thing
(wide timeseries, required species, first/last year),
so they can share [verify_wide_timeseries_inputs][(m).].

The verify functions are the specification,
and they are free to do extra checks (or not use this helper at all)
if an input needs something different.

The `get_*_problems` functions return a list of problems rather than raising,
so that every problem with every input can be reported in one go.
"""

from __future__ import annotations

from collections.abc import Collection

import numpy as np
import pandas as pd

from openscm_runner.errors import InvalidInputError

# TODO FUTURE: reconsider hard-coding
TIMESERIES_LEVELS: tuple[str, ...] = ("variable", "region", "unit")
"""
Index levels that describe each timeseries

All other index levels identify the experiment.
They must have a single value within each input
(each input in the tuple is exactly one experiment).
"""


def verify_wide_timeseries_inputs(  # noqa: PLR0913
    inputs: tuple[pd.DataFrame, ...],
    *,
    input_name: str,
    required_variables: Collection[str],
    first_year: int | None,
    last_year_at_most: int | None,
    regions: Collection[str] = ("World",),
) -> None:
    """
    Verify that inputs are wide timeseries that match a definition

    The rules:

    - `inputs` is a non-empty tuple of dataframes
      (each element is exactly one experiment)
    - each dataframe is non-empty and has (at least) the index levels
      in [TIMESERIES_LEVELS][(m).]
    - any other index level has a single value within each dataframe
    - columns are consecutive integer years
    - the first year is `first_year` (if not `None`)
    - the last year is at most `last_year_at_most` (if not `None`)
    - values are numeric and finite (no NaN or inf)
    - no duplicate timeseries
    - the variables are exactly `required_variables` (none missing, none extra)
    - the regions are all in `regions`

    Every input is checked and all problems are reported together.

    Parameters
    ----------
    inputs
        Inputs to verify

    input_name
        Name of the input definition, used in error messages

    required_variables
        Variables each input must have (no more, no less)

    first_year
        Required first year. If `None`, any first year is allowed.

    last_year_at_most
        Latest allowed last year. If `None`, there is no cap.

    regions
        Allowed regions

    Raises
    ------
    InvalidInputError
        At least one input doesn't match the definition.
        The message lists every problem found.
    """
    # TODO: check units (needs a unit registry wired in, default openscm-units).
    # Runtime check for callers who don't use a type checker
    if not isinstance(inputs, tuple):
        msg = (  # type: ignore[unreachable]
            f"{input_name} inputs must be a tuple of dataframes "
            f"(one per experiment), received {type(inputs)}"
        )
        raise InvalidInputError(msg)

    if not inputs:
        msg = f"No {input_name} inputs were given, so there is nothing to run"
        raise InvalidInputError(msg)

    problems = [
        f"input {i}: {problem}"
        for i, inp in enumerate(inputs)
        for problem in get_wide_timeseries_problems(
            inp,
            required_variables=required_variables,
            first_year=first_year,
            last_year_at_most=last_year_at_most,
            regions=regions,
        )
    ]
    if problems:
        problems_str = "\n".join(f"- {p}" for p in problems)
        msg = (
            f"{len(problems)} problem(s) with the {input_name} inputs:\n{problems_str}"
        )
        raise InvalidInputError(msg)


def get_wide_timeseries_problems(
    inp: object,
    *,
    required_variables: Collection[str],
    first_year: int | None,
    last_year_at_most: int | None,
    regions: Collection[str],
    # TODO: switch to problem container with a __repr__ method or something
    # throughout this module rather than plain strings
) -> list[str]:
    """
    Get the problems with one input

    See [verify_wide_timeseries_inputs][(m).] for the rules.
    Some problems stop further checks on that input
    (e.g. if it isn't a dataframe, nothing else can be checked).

    Parameters
    ----------
    inp
        Input to check

    required_variables
        Variables the input must have (no more, no less)

    first_year
        Required first year. If `None`, any first year is allowed.

    last_year_at_most
        Latest allowed last year. If `None`, there is no cap.

    regions
        Allowed regions

    Returns
    -------
    :
        Problems found (empty if there are none)
    """
    if not isinstance(inp, pd.DataFrame):
        return [f"must be a pandas DataFrame, received {type(inp)}"]

    if inp.empty:
        return ["is empty"]

    index_problems = get_index_level_problems(inp)
    if index_problems:
        # Everything below needs the index levels
        return index_problems

    problems = [
        *get_time_axis_problems(
            inp, first_year=first_year, last_year_at_most=last_year_at_most
        ),
        *get_value_problems(inp),
    ]

    if inp.index.has_duplicates:
        duplicates = inp.index[inp.index.duplicated()].unique().tolist()
        problems.append(f"has duplicate timeseries: {duplicates!r}")

    variables = set(inp.index.get_level_values("variable"))
    required = set(required_variables)
    missing = required - variables
    if missing:
        problems.append(f"is missing variables: {sorted(missing)!r}")

    extra = variables - required
    if extra:
        problems.append(f"has unexpected variables: {sorted(extra)!r}")

    allowed_regions = set(regions)
    unexpected_regions = set(inp.index.get_level_values("region")) - allowed_regions
    if unexpected_regions:
        problems.append(
            f"has unexpected regions: {sorted(unexpected_regions)!r} "
            f"(allowed: {sorted(allowed_regions)!r})"
        )

    return problems


def get_index_level_problems(inp: pd.DataFrame) -> list[str]:
    """
    Get the problems with the index levels of one input

    The timeseries levels must be present.
    Any other level identifies the experiment,
    so it must have a single value.

    Parameters
    ----------
    inp
        Input to check

    Returns
    -------
    :
        Problems found (empty if there are none)
    """
    names = list(inp.index.names)
    if any(name is None for name in names):
        return [f"all index levels must be named, received {names!r}"]

    problems = []
    missing_levels = [level for level in TIMESERIES_LEVELS if level not in names]
    if missing_levels:
        problems.append(f"is missing index levels: {missing_levels!r}")

    for i, level in enumerate(names):
        if level in TIMESERIES_LEVELS:
            continue

        values = inp.index.get_level_values(i).unique().tolist()
        if len(values) != 1:
            problems.append(
                f"index level {level!r} must have a single value "
                "(each input is exactly one experiment), "
                f"received {values!r}"
            )

    return problems


def get_time_axis_problems(
    inp: pd.DataFrame,
    *,
    first_year: int | None,
    last_year_at_most: int | None,
) -> list[str]:
    """
    Get the problems with the time axis (columns) of one input

    Parameters
    ----------
    inp
        Input to check

    first_year
        Required first year. If `None`, any first year is allowed.

    last_year_at_most
        Latest allowed last year. If `None`, there is no cap.

    Returns
    -------
    :
        Problems found (empty if there are none)
    """
    if not pd.api.types.is_integer_dtype(inp.columns):
        # The other checks need integer years
        return [f"columns must be integer years, received dtype {inp.columns.dtype}"]

    problems = []
    years = [int(y) for y in inp.columns]
    if years != list(range(years[0], years[-1] + 1)):
        problems.append(
            "columns must be consecutive years in increasing order, "
            f"received {years[0]}-{years[-1]} with gaps or out of order"
        )

    if first_year is not None and years[0] != first_year:
        problems.append(f"first year must be {first_year}, received {years[0]}")

    if last_year_at_most is not None and years[-1] > last_year_at_most:
        problems.append(
            f"last year must be at most {last_year_at_most}, received {years[-1]}"
        )

    return problems


def get_value_problems(inp: pd.DataFrame) -> list[str]:
    """
    Get the problems with the values of one input

    Values must be numeric and finite.

    Parameters
    ----------
    inp
        Input to check

    Returns
    -------
    :
        Problems found (empty if there are none)
    """
    non_numeric = [
        str(dtype)
        for dtype in inp.dtypes.unique()
        if not pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_bool_dtype(dtype)
    ]
    if non_numeric:
        # Can't check whether non-numeric values are finite
        return [f"values must be numeric, received dtypes {non_numeric!r}"]

    not_finite = ~np.isfinite(inp.to_numpy(dtype=float))
    if not_finite.any():
        rows = inp.index[np.any(not_finite, axis=1)].tolist()
        return [f"values must be finite (no NaN or inf), check rows {rows!r}"]

    return []
