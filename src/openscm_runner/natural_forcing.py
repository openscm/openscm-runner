"""Shared annual solar and volcanic ERF from RCMIP historical rows."""

from __future__ import annotations

from itertools import pairwise
from numbers import Integral
from pathlib import Path

import numpy as np
import pandas as pd


# TODO: put this on the roadmap as something to fix. Is it used?
def read_natural_forcing(path: str | Path, years: list[int]) -> pd.DataFrame:
    """Read World historical forcing in W/m² for the requested annual window.

    Historical rows supply the common trajectory, including future years.
    Whole-year columns label integration years; no half-year offset, baseline
    subtraction, interpolation, or extrapolation is applied.
    """
    if not years or any(
        isinstance(year, bool) or not isinstance(year, Integral) for year in years
    ):
        msg = "Natural forcing years must be nonempty integer years"
        raise ValueError(msg)

    if any(right != left + 1 for left, right in pairwise(years)):
        msg = "Natural forcing years must be consecutive and increasing"
        raise ValueError(msg)

    raw = pd.read_csv(path)
    columns = [str(year) for year in years]
    required = {"Scenario", "Region", "Variable", "Unit", *columns}
    if not required.issubset(raw.columns):
        msg = "Natural forcing requires metadata and all requested years"
        raise ValueError(msg)

    historical = raw.loc[(raw["Scenario"] == "historical") & (raw["Region"] == "World")]
    data = {}
    for component in ("Solar", "Volcanic"):
        variable = f"Effective Radiative Forcing|Natural|{component}"
        selected = historical.loc[historical["Variable"] == variable]
        if len(selected) != 1:
            msg = f"Expected exactly one World historical {variable} row"
            raise ValueError(msg)

        if selected.iloc[0]["Unit"] != "W/m^2":
            msg = f"Natural {component} forcing must use W/m^2"
            raise ValueError(msg)

        values = selected.iloc[0][columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            msg = f"Natural {component} forcing must be finite"
            raise ValueError(msg)

        data[component] = values

    return pd.DataFrame(data, index=pd.Index(years, name="year"))
