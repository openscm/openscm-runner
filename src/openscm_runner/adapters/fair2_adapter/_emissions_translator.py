"""
Convert ScmRun emissions into FaIR 2.x's expected DataFrame shape.

Pivots an openscm-runner :class:`scmdata.ScmRun` into the horizontal
DataFrame that :meth:`fair.FAIR.fill_from_pandas` expects, and splices
the user's scenario data on top of the calibration bundle's historical
emissions.

Shape expected by FaIR 2.x (lowercase column names; FaIR lowercases
them itself but we produce them lowercase up-front for clarity):

    scenario | variable | region | unit | 1750 | 1751 | ... | 2100
    ssp245   | CO2 FFI  | World  | ...  |  ... | ...  |     | ...

One row per (scenario, FaIR-species) combination. Time columns are
years (integers); FaIR interpolates to its own timepoints internally,
so the input grid does not have to align with FaIR's.

Splice rules:

- Bundle historical CSV is used as the baseline for every user scenario.
  The bundle's own "scenario" label (typically "historical") is
  relabelled to each user scenario in turn.
- For each (user_scenario, species) pair where the user provides data,
  the user's values overwrite the bundle's in the overlapping years
  (typically ~2015 onwards for IAMC scenarios). Years before the user's
  data start are taken from the bundle; years after are taken from the
  user.
- Species the user does not provide stay at bundle-historical values
  (and FaIR's defaults for any future years the bundle doesn't cover).
  Unmapped openscm-runner variables (anything not in the
  :data:`OPENSCM_TO_FAIR2_SPECIES` map) are logged at WARNING and
  ignored.

Unit conversion is left to FaIR 2.x (it has its own conversion tables
in :mod:`fair.io.fill_from`). We pass the openscm-runner unit string
through unchanged and trust FaIR to recognise it; FaIR raises a clear
``UnitParseError`` if it does not.

This module deliberately uses pandas directly rather than going through
scmdata.ScmRun helpers (which currently lean on the broken
``ScmRun.convert_unit`` -> groupby path on pandas 3.x; see openscm/scmdata#318
and benmsanderson/openscm-runner#6). Aligns with the long-term direction
of leaning less on scmdata.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

import pandas as pd

LOGGER = logging.getLogger(__name__)


# Suffix-match openscm-runner variable names to FaIR 2.x species names.
#
# Suffix-match lets callers use the full hierarchical IAMC names
# ("Emissions|CO2|MAGICC Fossil and Industrial",
# "Emissions|F-Gases|HFC|HFC152a", ...) interchangeably with the
# leaf-only forms. Most differences from openscm-runner's names are
# the hyphens FaIR 2.x uses for CFC/HCFC/Halon/HFC families (e.g.
# "CFC11" -> "CFC-11", "HFC4310mee" -> "HFC-4310mee", "Halon1211"
# -> "Halon-1211").
#
# Covers all 49 emissions-input species in the FaIR 2.x AR6 default
# set (those with input_mode="emissions" in fair.io.read_properties).
# Solar and Volcanic are forcing-mode in FaIR 2.x and provided by the
# calibration bundle, not user-supplied here.
OPENSCM_TO_FAIR2_SPECIES = {
    # CO2 emissions are split into FFI and AFOLU sources in both
    # naming conventions. FaIR 2.x computes the "CO2" total internally.
    "|CO2|MAGICC Fossil and Industrial": "CO2 FFI",
    "|CO2|MAGICC AFOLU": "CO2 AFOLU",
    # Direct GHGs
    "|CH4": "CH4",
    "|N2O": "N2O",
    # Short-lived climate forcers and aerosol precursors
    "|Sulfur": "Sulfur",
    "|SOx": "Sulfur",  # MAGICC adapter alias
    "|BC": "BC",
    "|OC": "OC",
    "|NH3": "NH3",
    "|NOx": "NOx",
    "|VOC": "VOC",
    "|NMVOC": "VOC",  # MAGICC adapter alias
    "|CO": "CO",
    # Montreal Protocol halogens (CFCs, HCFCs, halons, miscellaneous
    # halogenated species). FaIR 2.x uses hyphenated names.
    "|CFC11": "CFC-11",
    "|CFC12": "CFC-12",
    "|CFC113": "CFC-113",
    "|CFC114": "CFC-114",
    "|CFC115": "CFC-115",
    "|CCl4": "CCl4",
    "|CH3CCl3": "CH3CCl3",
    "|CHCl3": "CHCl3",
    "|CH2Cl2": "CH2Cl2",
    "|CH3Cl": "CH3Cl",
    "|CH3Br": "CH3Br",
    "|HCFC22": "HCFC-22",
    "|HCFC141b": "HCFC-141b",
    "|HCFC142b": "HCFC-142b",
    "|Halon1202": "Halon-1202",
    "|Halon1211": "Halon-1211",
    "|Halon1301": "Halon-1301",
    "|Halon2402": "Halon-2402",
    # F-gases: PFCs
    "|CF4": "CF4",
    "|C2F6": "C2F6",
    "|C3F8": "C3F8",
    "|cC4F8": "c-C4F8",
    "|C4F10": "C4F10",
    "|C5F12": "C5F12",
    "|C6F14": "C6F14",
    "|C7F16": "C7F16",
    "|C8F18": "C8F18",
    # F-gases: other
    "|NF3": "NF3",
    "|SF6": "SF6",
    "|SO2F2": "SO2F2",
    # F-gases: HFCs
    "|HFC23": "HFC-23",
    "|HFC32": "HFC-32",
    "|HFC125": "HFC-125",
    "|HFC134a": "HFC-134a",
    "|HFC143a": "HFC-143a",
    "|HFC152a": "HFC-152a",
    "|HFC227ea": "HFC-227ea",
    "|HFC236fa": "HFC-236fa",
    "|HFC245fa": "HFC-245fa",
    "|HFC365mfc": "HFC-365mfc",
    "|HFC4310mee": "HFC-4310mee",
}


def _openscm_to_fair2_species(variable: str) -> str | None:
    for suffix, species in OPENSCM_TO_FAIR2_SPECIES.items():
        if variable.endswith(suffix):
            return species
    return None


# FaIR species names whose unit conversion needs a non-default pint
# context. NOx is the canonical case: openscm-units stores mass-of-NO2
# unless you opt into the NOx_conversions context, which lets the same
# number round-trip cleanly between MtN/yr and MtNO2/yr.
#
# These keys are FaIR 2.x species names (the post-translation form),
# because `_splice_bundle_with_user` operates on rows whose `variable`
# column has already been mapped to FaIR names.
_UNIT_CONTEXTS = {
    "NOx": "NOx_conversions",
    "NH3": "NH3_conversions",
}


def _context_for(species_name: str) -> str | None:
    return _UNIT_CONTEXTS.get(species_name)


def _unit_scale(
    from_unit: object, to_unit: object, variable: str
) -> float:
    """
    Return the multiplicative factor that converts ``from_unit`` into
    ``to_unit`` for ``variable``, using openscm-units.

    Equal units (or missing user unit) returns ``1.0``. Unparseable
    or dimensionally incompatible units raise (via openscm-units /
    pint) rather than silently disabling the overlay.
    """
    if from_unit is None or pd.isna(from_unit):
        return 1.0
    from_str = str(from_unit).strip()
    to_str = str(to_unit).strip() if to_unit is not None else from_str
    if from_str == to_str:
        return 1.0
    import openscm_units

    # Unit-conversion failure here is a real bug: either the species
    # mapping has the wrong target unit or the user ScmRun ships an
    # unparseable unit string. Let pint's
    # ``UndefinedUnitError`` / ``DimensionalityError`` propagate so
    # the caller fails loudly rather than silently leaving the
    # bundle value in place (Marit's PR97 "AI cover all your bases"
    # objection).
    context = _context_for(variable)
    if context is not None:
        with openscm_units.unit_registry.context(context):
            return float(
                openscm_units.unit_registry(from_str).to(to_str).magnitude
            )
    return float(
        openscm_units.unit_registry(from_str).to(to_str).magnitude
    )


def _scmrun_to_fair2_rows(scmrun, scenario_names: Iterable[str]) -> pd.DataFrame:
    """
    Pivot the user's ScmRun into one row per (scenario, species).

    Unmapped variables are dropped with a warning. Years are integer
    column labels. ``unit`` is preserved verbatim (FaIR converts).
    """
    ts = scmrun.timeseries(time_axis="year")
    rows = []
    unmapped: set[str] = set()
    mapped_scenarios = set(scenario_names)

    # Use named index lookups so we do not depend on the order or
    # presence of meta columns (different callers carry different sets).
    index_names = list(ts.index.names)
    for index_values, series in ts.iterrows():
        meta = dict(zip(index_names, index_values))
        variable = meta.get("variable")
        species = _openscm_to_fair2_species(variable) if variable else None
        if species is None:
            if variable is not None:
                unmapped.add(variable)
            continue
        scenario = meta.get("scenario")
        if scenario not in mapped_scenarios:
            # Caller passed a subset of scenarios. Skip rows for scenarios
            # we are not running.
            continue
        years = [int(y) for y in series.index]
        row = {
            "scenario": scenario,
            "variable": species,
            "region": meta.get("region", "World"),
            "unit": meta.get("unit"),
        }
        for year, value in zip(years, series.values):
            row[year] = value
        rows.append(row)

    if unmapped:
        LOGGER.warning(
            "FaIRv2 adapter v1 emissions mapping covers %s. "
            "Unmapped variables (bundle defaults will be used instead): %s",
            sorted(OPENSCM_TO_FAIR2_SPECIES.values()),
            sorted(unmapped),
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _splice_bundle_with_user(
    bundle_df: pd.DataFrame,
    user_df: pd.DataFrame,
    scenario_names: Iterable[str],
) -> pd.DataFrame:
    """
    Take the canonical RCMIP3 baseline as the per-scenario starting
    point and overwrite with user data.

    The bundle DataFrame is already per-scenario (one row per
    ``(scenario, variable)`` covering 1750-2500, as produced by
    :func:`_rcmip3_to_fair_emissions_df`). Filter to rows whose
    ``scenario`` is in ``scenario_names``; user-supplied rows then
    overlay on the matching ``(scenario, variable)`` pair with unit
    scaling so the bundle's unit is preserved.
    """
    # Normalise bundle column names; FaIR is case-insensitive on them.
    bundle_df = bundle_df.copy()
    bundle_df.columns = [
        c.lower() if isinstance(c, str) else c for c in bundle_df.columns
    ]
    bundle_year_cols = [c for c in bundle_df.columns if isinstance(c, (int, float))]
    bundle_year_cols += [
        c
        for c in bundle_df.columns
        if isinstance(c, str) and c.isdigit() and int(c) not in bundle_year_cols
    ]
    # FaIR's _check_csv expects year columns; if they came in as strings
    # (common when reading CSV without parse), coerce here so downstream
    # selection works on integer keys.
    rename_map = {
        c: int(c) for c in bundle_df.columns if isinstance(c, str) and c.isdigit()
    }
    if rename_map:
        bundle_df = bundle_df.rename(columns=rename_map)

    if not user_df.empty:
        user_df.columns = [
            c.lower() if isinstance(c, str) else c for c in user_df.columns
        ]

    spliced_df = bundle_df[
        bundle_df["scenario"].isin(list(scenario_names))
    ].reset_index(drop=True)
    if spliced_df.empty:
        return user_df.reset_index(drop=True)

    if user_df.empty:
        return spliced_df

    # Overlay user data on top, per (scenario, variable) row.
    #
    # The unit story: bundle and user often disagree on the prefix
    # (Gt vs Mt vs kt). Bundle's CO2 FFI is "Gt CO2/yr" while typical
    # IAM output is "Mt CO2/yr"; if we just write the user's numbers
    # into the bundle row and overwrite the unit string, the row ends
    # up mixing bundle's Gt-scale historicals (1750-2023) with user's
    # Mt-scale numbers (2015-2100) under a single "Mt CO2/yr" label.
    # FaIR's downstream unit conversion then divides everything by
    # 1000 and the historicals get destroyed.
    #
    # Fix: convert the user's values into the bundle's unit before
    # writing them, and keep the bundle's unit on the row. If the
    # conversion fails (unknown unit / species pair), log a warning
    # and skip the overlay for that row.
    user_year_cols = [c for c in user_df.columns if isinstance(c, int)]
    for _, user_row in user_df.iterrows():
        mask = (spliced_df["scenario"] == user_row["scenario"]) & (
            spliced_df["variable"] == user_row["variable"]
        )
        if not mask.any():
            # User provided a species the bundle didn't cover. Append
            # the row as-is so FaIR sees it (bundle baseline will be NaN
            # for the early years; FaIR's interpolator handles that with
            # bounds_error=False, leaving NaN, which the model may not
            # like; user can fill in their own historical if needed).
            spliced_df = pd.concat(
                [spliced_df, pd.DataFrame([user_row])], ignore_index=True
            )
            continue

        bundle_unit = spliced_df.loc[mask, "unit"].iloc[0]
        user_unit = user_row.get("unit")
        scale = _unit_scale(user_unit, bundle_unit, user_row["variable"])

        for year in user_year_cols:
            value = user_row[year]
            if pd.notna(value):
                spliced_df.loc[mask, year] = value * scale
        # Keep the bundle's unit (already there); don't overwrite with
        # user's unit since we just converted the values.

    # SCIENTIFIC CHOICE: forward-fill NaN year cells.
    #
    # When the user's scenario adds year columns the bundle did not
    # cover (e.g. user supplies decadal future emissions for CO2 FFI,
    # so columns 2030/2040/... get added globally), the rows for
    # species the user did NOT provide (e.g. CFC-11) end up with NaN
    # in those new columns. FaIR's interp1d then propagates the NaN
    # downstream and the simulation refuses to start.
    #
    # We forward-fill across the year axis per row so that any species
    # the user does not supply for the future is held constant at its
    # last historical value (typically the 2023 bundle value).
    # Alternatives considered: zero-fill (wrong for slowly-decaying
    # species like CFCs), linear extrapolation (hard to defend across
    # 60+ species with different baseline dynamics). The forward-fill
    # is a deliberately conservative choice and will be made
    # configurable when a real use case asks.
    year_cols_sorted = sorted(
        c for c in spliced_df.columns if isinstance(c, int)
    )
    if year_cols_sorted:
        spliced_df[year_cols_sorted] = spliced_df[year_cols_sorted].ffill(axis=1)

    # Year columns must end up in strictly monotonic order so FaIR's
    # ``_check_csv`` accepts the frame. When the user introduces year
    # columns the bundle did not cover (e.g. user supplies 2015-2100
    # decadal but the bundle ships 1750/1850/1900/...), pd.concat
    # parks the user's new columns at the right edge in user-row
    # order, which generally is not monotonic relative to the bundle
    # tail (e.g. bundle ends 2100, user adds 2015,2020,...).
    meta_cols = [c for c in spliced_df.columns if not isinstance(c, int)]
    spliced_df = spliced_df[meta_cols + year_cols_sorted]

    return spliced_df


def _rcmip3_to_fair_emissions_df(
    rcmip3_bundle_path,
    scenario_names: Iterable[str],
) -> pd.DataFrame:
    """
    Read canonical RCMIP3 emissions and reshape to FaIR-rows.

    Returns a DataFrame in the same horizontal layout that
    :func:`_scmrun_to_fair2_rows` produces (one row per
    ``(scenario, FaIR-species)``, integer year columns), keyed by user
    scenario rather than a single bundle ``"historical"`` row -- so
    :func:`_splice_bundle_with_user` must be called with
    ``bundle_per_scenario=True``.

    Variable names from the canonical CSV are canonicalised via
    :func:`openscm_runner.io.canonicalise_rcmip3_variable` (strips
    intermediate IAMC categories, maps CO2 sub-sectors to the
    MAGICC-style names :data:`OPENSCM_TO_FAIR2_SPECIES` is keyed by)
    before going through :func:`_openscm_to_fair2_species`.
    """
    from ...io.rcmip3 import (
        canonicalise_rcmip3_variable,
        load_rcmip3_emissions,
    )

    scenario_list = list(scenario_names)
    df = load_rcmip3_emissions(rcmip3_bundle_path, scenarios=scenario_list)
    if df.empty:
        return pd.DataFrame()

    year_cols = [c for c in df.columns if isinstance(c, str) and c.isdigit()]
    rows: list[dict] = []
    unmapped: set[str] = set()
    for _, csv_row in df.iterrows():
        canonical_variable = canonicalise_rcmip3_variable(csv_row["Variable"])
        species = _openscm_to_fair2_species(canonical_variable)
        if species is None:
            unmapped.add(csv_row["Variable"])
            continue
        row: dict = {
            "scenario": csv_row["Scenario"],
            "variable": species,
            "region": csv_row.get("Region", "World"),
            "unit": csv_row["Unit"],
        }
        for year_str in year_cols:
            row[int(year_str)] = float(csv_row[year_str])
        rows.append(row)

    if unmapped:
        LOGGER.info(
            "FaIRv2 RCMIP3 emissions: %d canonical variables had no "
            "FaIR species mapping; dropped: %s",
            len(unmapped), sorted(unmapped),
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def build_emissions_df(
    scmrun,
    rcmip3_bundle_path,
    scenario_names: Iterable[str],
    co2_only_scenarios: Iterable[str] = (),
) -> pd.DataFrame:
    """
    Build the FaIR 2.x-shaped emissions DataFrame.

    Splices the canonical RCMIP3 baseline (Zenodo 20430630
    ``rcmip_phase3_emissions_v2.0.0.csv``) with the user's scenario
    data and returns one row per (scenario, species) in the horizontal
    form FaIR's :meth:`fair.FAIR.fill_from_pandas` expects. Variable
    names from the canonical CSV are canonicalised via
    :func:`openscm_runner.io.canonicalise_rcmip3_variable` before going
    through :func:`_openscm_to_fair2_species`.

    Parameters
    ----------
    scmrun : scmdata.ScmRun or None
        The user's emissions scenarios. When ``None`` or empty, the
        returned DataFrame is just the canonical baseline (useful for
        reproducing canonical RCMIP3 runs without further input).
    rcmip3_bundle_path : path-like
        Directory of the canonical Zenodo 20430630 RCMIP3 bundle.
        Required.
    scenario_names : iterable of str
        FaIR scenario labels to populate.
    co2_only_scenarios : iterable of str
        Scenarios whose non-CO2 species should be zeroed out across all
        years after the splice. The RCMIP3 idealised CO2 experiments
        (``esm-flat*``, ``esm-bell*``, ``1pctCO2*``, ``abrupt-*``) only
        supply CO2 emissions in the protocol CSV, expecting non-CO2
        forcings to stay at pre-industrial. Without this list, the
        baseline's historical non-CO2 values leak through (forward-
        filled at 2023 by the splice) and contaminate the diagnostics.

    Returns
    -------
    pandas.DataFrame
        Horizontal-form emissions DataFrame ready to pass to
        ``fair.FAIR.fill_from_pandas(mode="emissions", df=...)``.
    """
    bundle_df = _rcmip3_to_fair_emissions_df(
        rcmip3_bundle_path, scenario_names,
    )

    user_df = (
        _scmrun_to_fair2_rows(scmrun, scenario_names)
        if scmrun is not None
        else pd.DataFrame()
    )

    if bundle_df.empty and user_df.empty:
        return pd.DataFrame()

    spliced = _splice_bundle_with_user(bundle_df, user_df, scenario_names)

    co2_only_set = set(co2_only_scenarios)
    if co2_only_set:
        year_cols = [c for c in spliced.columns if isinstance(c, int)]
        # CO2 in the spliced DataFrame appears under either the bundle's
        # FaIR-native names ("CO2 FFI", "CO2 AFOLU") or the user-side
        # MAGICC names ("Emissions|CO2|MAGICC Fossil and Industrial").
        # Match both so the zero-out doesn't accidentally zero CO2.
        variable = spliced["variable"].astype(str)
        is_co2 = (
            variable.str.startswith("Emissions|CO2")
            | variable.str.startswith("CO2 ")
            | (variable == "CO2")
        )
        mask = spliced["scenario"].isin(co2_only_set) & ~is_co2
        if mask.any() and year_cols:
            spliced.loc[mask, year_cols] = 0.0

    # FaIR 2.x's fill_from_pandas runs `df.columns.str.lower()` on the
    # DataFrame, which silently replaces non-string column labels with
    # NaN under a mixed-type Index (str metadata + int years). Convert
    # year columns back to strings here so FaIR sees them. We use ints
    # internally during the splice because `.loc[mask, year] = value`
    # is easier to reason about with int keys; the string round-trip is
    # a one-liner at the boundary.
    spliced.columns = [
        str(c) if isinstance(c, int) else c for c in spliced.columns
    ]
    return spliced
