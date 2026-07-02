"""Helpers for validating MAGICC7 against IPCC AR6 Table 7.SM.4.

The "Future Warming (GSAT)" SSP block of AR6 WG1 Table 7.SM.4 is a
concentration-driven, probabilistic reproduction target: each emulator
column is the 5th / 50th / 95th percentile of a calibrated ensemble,
driven from the SSP concentrations, expressed as GSAT relative to the
1995-2014 mean. For MAGICC7 the ensemble is the AR6 probabilistic
drawnset (600 parameter sets) run with MAGICC v7.5.x.

These helpers wire that up so a test (or a notebook) can:

- load the drawnset JSON into openscm-runner MAGICC7 cfgs,
- load the assessed reference table, and
- reduce a run result to per-period GSAT percentiles on the AR6 grid.

The drawnset is licensed (see its README) and is **not** vendored into
this repo; point the loader at a local copy. Reproducing the published
numbers also needs the full RCMIP3 concentration bundle; with only the
mini test bundle this exercises the pipeline (a "smoke" run), not the
published values.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

GSAT_VARIABLE = "Surface Air Temperature Change"
AR6_REFERENCE_PERIOD = range(1995, 2015)  # 1995-2014 inclusive
AR6_PERIODS: dict[str, range] = {
    "2021-2040": range(2021, 2041),
    "2041-2060": range(2041, 2061),
    "2081-2100": range(2081, 2101),
}
AR6_QUANTILES = (0.05, 0.50, 0.95)  # -> (lower, central, upper)


def load_ar6_drawnset(path, n: int | None = None) -> list[dict]:
    """Load the AR6 probabilistic drawnset JSON into MAGICC7 cfgs.

    Each drawnset member is ``{"nml_allcfgs": {...}, "paraset_id": int}``;
    we lower-case the namelist keys (the adapter's convention) and use
    ``paraset_id`` as ``run_id`` so ensemble members stay distinguishable
    through :func:`openscm_runner.utils.calculate_quantiles`.

    Parameters
    ----------
    path
        Path to the drawnset ``.json``.
    n
        If given, take only the first ``n`` members (for smoke runs).
    """
    members = json.loads(Path(path).read_text())["configurations"]
    if n is not None:
        members = members[:n]
    cfgs = []
    for member in members:
        cfg = {k.lower(): v for k, v in member["nml_allcfgs"].items()}
        cfg["run_id"] = member["paraset_id"]
        cfgs.append(cfg)
    return cfgs


def load_table_7sm4(path) -> pd.DataFrame:
    """Load the cleaned AR6 Table 7.SM.4 reference fixture."""
    return pd.read_csv(path)


def assessed_row(table: pd.DataFrame, metric: str, source: str, period_startswith: str = ""):
    """Return ``(lower, central, upper)`` for one metric/source/period."""
    sel = table[(table["metric"] == metric) & (table["source"] == source)]
    if period_startswith:
        sel = sel[sel["period"].fillna("").str.startswith(period_startswith)]
    if len(sel) != 1:
        raise LookupError(
            f"expected exactly one row for metric={metric!r} source={source!r} "
            f"period~{period_startswith!r}, got {len(sel)}"
        )
    row = sel.iloc[0]
    return float(row["lower"]), float(row["central"]), float(row["upper"])


def gsat_percentiles_by_period(
    res,
    periods: dict[str, range] = AR6_PERIODS,
    reference_period: range = AR6_REFERENCE_PERIOD,
    quantiles=AR6_QUANTILES,
) -> dict[str, tuple[float, float, float]]:
    """Reduce a MAGICC run to per-period GSAT percentiles on the AR6 grid.

    Rebases ``Surface Air Temperature Change`` to the ``reference_period``
    mean (matching AR6's "relative to 1995-2014"), takes each ensemble
    member's mean warming over each period, then the cross-member
    percentiles. Returns ``{period_label: (lower, central, upper)}``.
    """
    rebased = res.filter(variable=GSAT_VARIABLE).relative_to_ref_period_mean(
        year=list(reference_period),
    )
    ts = rebased.timeseries()
    out: dict[str, tuple[float, float, float]] = {}
    for label, years in periods.items():
        year_cols = [c for c in ts.columns if int(getattr(c, "year", c)) in years]
        per_member = ts[year_cols].mean(axis=1).to_numpy()
        lo, ce, up = np.percentile(per_member, [q * 100 for q in quantiles])
        out[label] = (float(lo), float(ce), float(up))
    return out
