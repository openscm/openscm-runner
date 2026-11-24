"""Direct tests of the shared verification helpers"""

import re

import pandas as pd
import pytest

from openscm_runner.errors import InvalidInputError
from openscm_runner.verification import verify_wide_timeseries_inputs

LEVELS = ("variable", "region", "unit")


def make_input(extra_level: str | None = None) -> pd.DataFrame:
    names = ["scenario", "variable", "region", "unit"]
    row = ["test", "Emissions|CO2", "World", "Gt C / yr"]
    if extra_level is not None:
        names.append(extra_level)
        row.append("a")

    return pd.DataFrame(
        [[1.0, 2.0]],
        index=pd.MultiIndex.from_tuples([tuple(row)], names=names),
        columns=[2000, 2001],
    )


VERIFY_KWARGS = dict(
    input_name="Test",
    required_variables={"Emissions|CO2"},
    first_year=2000,
    last_year_at_most=None,
)


def test_timeseries_levels_are_required_index_levels():
    verify_wide_timeseries_inputs(
        (make_input(),), **VERIFY_KWARGS, timeseries_levels=LEVELS
    )

    with pytest.raises(InvalidInputError, match=r"missing index levels: \['unit'\]"):
        verify_wide_timeseries_inputs(
            (make_input().droplevel("unit"),),
            **VERIFY_KWARGS,
            timeseries_levels=LEVELS,
        )


def test_extra_timeseries_level():
    levels = (*LEVELS, "sector")
    inp = make_input(extra_level="sector")
    # If it isn't a timeseries level, "sector" identifies the experiment,
    # which is fine because it has a single value
    verify_wide_timeseries_inputs((inp,), **VERIFY_KWARGS, timeseries_levels=LEVELS)
    verify_wide_timeseries_inputs((inp,), **VERIFY_KWARGS, timeseries_levels=levels)

    # As a timeseries level, it is required
    with pytest.raises(InvalidInputError, match=r"missing index levels: \['sector'\]"):
        verify_wide_timeseries_inputs(
            (make_input(),), **VERIFY_KWARGS, timeseries_levels=levels
        )

    # As a timeseries level, it can have several values within an input
    two_sectors = pd.concat([inp, inp.rename(index={"a": "b"}, level="sector")])
    with pytest.raises(InvalidInputError, match="'sector' must have a single value"):
        verify_wide_timeseries_inputs(
            (two_sectors,), **VERIFY_KWARGS, timeseries_levels=LEVELS
        )
    verify_wide_timeseries_inputs(
        (two_sectors,), **VERIFY_KWARGS, timeseries_levels=levels
    )


@pytest.mark.parametrize(
    "levels, missing",
    [
        (("region", "unit"), "variable"),
        (("variable", "unit"), "region"),
    ],
)
@pytest.mark.parametrize("valid_input", [True, False])
def test_checked_levels_must_be_timeseries_levels(levels, missing, valid_input):
    # The definition problem is raised whatever the input
    # (even if the input is too broken to reach the variable or region checks)
    inp = make_input() if valid_input else "not a dataframe"
    with pytest.raises(
        ValueError, match=re.escape(f"needs {missing!r} to be a timeseries level")
    ):
        verify_wide_timeseries_inputs((inp,), **VERIFY_KWARGS, timeseries_levels=levels)
