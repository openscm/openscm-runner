"""
Input definition
"""

from __future__ import annotations

from typing import TypeAlias

import pandas as pd

from openscm_runner.verification import verify_wide_timeseries_inputs

ERF: TypeAlias = pd.DataFrame
"""
Total effective radiative forcing (ERF) for a run starting from equilibrium

[verify_erf][(m).] defines the shape.
"""


def verify_erf(erf: tuple[ERF, ...]) -> None:
    """
    Verify inputs for ERF-driven runs starting from equilibrium

    Parameters
    ----------
    erf
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        erf,
        input_name="ERF",
        # Total ERF only
        required_variables={"Effective Radiative Forcing"},
        # Can start in any year
        first_year=None,
        last_year_at_most=None,
    )
