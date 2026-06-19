"""
Translate RCMIP3 + user-overlay concentrations into MAGICC7 inputs.

This module is the conc-driven sibling to the SCEN7-writing path in
:mod:`magicc7`. The strategy mirrors the FaIR2 / CICEROSCMPY2
adapters: load a baseline from the canonical RCMIP3 Zenodo bundle
(record `20430630`_) and overlay any ``Atmospheric Concentrations|*``
rows the caller supplies on top, then write one MAGICC ``CONC.IN``
file per (scenario, species) and emit cfg patches pointing MAGICC at
those files.

Per-gas mixed-mode: a species qualifies for conc-driven only when
*every* scenario in the batch supplies an ``Atmospheric Concentrations|<species>``
trajectory (either directly in the user ScmRun, or — failing that —
via the RCMIP3 baseline). Species the batch doesn't fully cover fall
back silently to the SCEN7 emissions-driven path. This matches the
FaIR2 mixed-mode logic at
``fair2_adapter._run_one_calibration`` (intersection over scenarios).

.. _20430630: https://zenodo.org/records/20430630
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from ._compat import pymagicc

LOGGER = logging.getLogger(__name__)


# RCMIP3-side short species name -> MAGICC7-side short species name.
# Most of CO2/CH4/N2O/SF6/CF4 round-trip unchanged; this map only
# covers cases where the canonical RCMIP3 CSV's leaf species (after
# stripping intermediate IAMC categories via
# :func:`openscm_runner.io.rcmip3.canonicalise_rcmip3_variable`) does
# NOT match MAGICC's species name.
#
# Halons: RCMIP3 uses ``H-1211``; MAGICC uses ``HALON1211``.
# HFC4310mee: this repo's existing magicc7 ``_VARIABLE_MAP`` already
# folds the ``mee`` suffix away on the emissions path, so we mirror
# that here for the concentrations path.
RCMIP_TO_MAGICC_SPECIES: dict[str, str] = {
    "H-1202": "HALON1202",
    "H-1211": "HALON1211",
    "H-1301": "HALON1301",
    "H-2402": "HALON2402",
    "HFC4310mee": "HFC4310",
    "cC4F8": "CC4F8",
}


# Default fall-back concentration units, used when
# ``pymagicc.definitions.MAGICC7_CONCENTRATIONS_UNITS`` does not list
# a species (e.g. on older pymagicc versions). The triplet ppm/ppb/ppt
# is the long-standing MAGICC convention: CO2 -> ppm, CH4 / N2O ->
# ppb, all halocarbons / PFCs / SF6 -> ppt.
_FALLBACK_CONC_UNITS: dict[str, str] = {
    "CO2": "ppm",
    "CH4": "ppb",
    "N2O": "ppb",
}


# MAGICC7 namelist exposes per-gas concentration-driving flags
# (``FILE_<gas>_CONC`` + ``<gas>_SWITCHFROMCONC2EMIS_YEAR``) only for
# the three main WMGHGs. F-gases and Montreal halocarbons share
# bundled-array flags (``FGAS_FILES_CONC`` indexed positionally by
# ``FGAS_NAMES``, ``MHALO_FILES_CONC`` indexed by ``MHALO_NAMES``,
# each with a single shared ``*_SWITCHFROMCONC2EMIS_YEAR``) which
# this v1 implementation does not yet write; user overlays for those
# species are logged and ignored, with the SCEN7 emissions path
# handling them as today. Extension is a follow-up.
SUPPORTED_PER_GAS_CONC_SPECIES: frozenset[str] = frozenset({"CO2", "CH4", "N2O"})


def cfg_keys_for_species(magicc_species: str) -> tuple[str, str]:
    """
    Return the ``(file_<gas>_conc, <gas>_switchfromconc2emis_year)``
    MAGICC cfg flag pair for a given MAGICC-side species name.

    Only valid for species in :data:`SUPPORTED_PER_GAS_CONC_SPECIES`
    (``CO2`` / ``CH4`` / ``N2O``); raises :class:`ValueError`
    otherwise. F-gases / Montreal halocarbons use bundled-array
    flags handled separately.
    """
    if magicc_species not in SUPPORTED_PER_GAS_CONC_SPECIES:
        raise ValueError(
            f"MAGICC7 conc-driven v1 supports only "
            f"{sorted(SUPPORTED_PER_GAS_CONC_SPECIES)}; got {magicc_species!r}."
        )
    name = magicc_species.lower()
    return (f"file_{name}_conc", f"{name}_switchfromconc2emis_year")


def _conc_units_lookup() -> dict[str, str]:
    """
    Build an openscm-variable -> magicc concentration-unit lookup.

    Prefer pymagicc's shipped ``MAGICC7_CONCENTRATIONS_UNITS`` table
    where available (so unit names track the installed pymagicc
    version); fall back to the CO2/CH4/N2O defaults if the table is
    missing or doesn't list a species. Callers convert per-species
    values to these units before writing the ``.IN`` file.
    """
    if pymagicc is None:
        return dict(_FALLBACK_CONC_UNITS)
    table = getattr(
        pymagicc.definitions, "MAGICC7_CONCENTRATIONS_UNITS", None,
    )
    if table is None:
        return dict(_FALLBACK_CONC_UNITS)
    lookup: dict[str, str] = {}
    for _, row in table.iterrows():
        magicc_var = row.get("magicc_variable")
        unit = row.get("concentration_unit") or row.get("unit")
        if not magicc_var or not unit:
            continue
        if magicc_var.endswith("_CONC"):
            magicc_var = magicc_var[: -len("_CONC")]
        lookup[magicc_var] = unit
    return lookup


def build_concentrations_overlay(
    scenario_run,
    rcmip3_bundle_path,
    scenario_names: Iterable[str],
    nystart: int = 1750,
    nyend: int = 2500,
) -> pd.DataFrame:
    """
    Build per-(scenario, MAGICC-species) overlay rows for conc-driven mode.

    Reads ``rcmip_phase3_concentrations_v2.0.0.csv`` for the baseline,
    overlays any ``Atmospheric Concentrations|*`` rows the caller
    supplied in ``scenario_run``, and applies the per-gas mixed-mode
    filter: a species survives only when every scenario in
    ``scenario_names`` supplies a trajectory for it (the FaIR2 batch-
    consistency rule).

    Returns a DataFrame with one row per (scenario, MAGICC-species):

        scenario | magicc_species | unit | series

    where ``series`` is a :class:`pandas.Series` indexed by integer
    year holding the concentration trajectory. Returns an empty
    DataFrame if nothing qualifies (e.g. the caller's batch covers a
    scenario the RCMIP3 baseline does not).
    """
    scenario_names = list(scenario_names)
    if not scenario_names:
        return pd.DataFrame()

    # Caller overlay first (so it can shadow the RCMIP3 baseline
    # year-by-year if both are present for the same species).
    user_rows: list[dict] = []
    if scenario_run is not None and not scenario_run.empty:
        conc_run = scenario_run.filter(
            variable="Atmospheric Concentrations|*", log_if_empty=False,
        )
        if not conc_run.empty:
            ts = conc_run.timeseries(time_axis="year")
            for index_tuple, values in ts.iterrows():
                meta = dict(zip(ts.index.names, index_tuple))
                scenario = meta.get("scenario")
                if scenario not in scenario_names:
                    continue
                variable = meta["variable"]
                species_short = variable.split("|", 1)[1]
                magicc_species = RCMIP_TO_MAGICC_SPECIES.get(
                    species_short, species_short,
                )
                series = pd.Series({
                    int(year): float(val)
                    for year, val in values.items()
                    if nystart <= int(year) <= nyend
                    and pd.notna(val)
                })
                if series.empty:
                    continue
                user_rows.append({
                    "scenario": scenario,
                    "magicc_species": magicc_species,
                    "unit": meta.get("unit"),
                    "series": series,
                })

    user_df = pd.DataFrame(user_rows)

    # RCMIP3 baseline second. Cells the caller also supplies are
    # merged year-by-year (user values win), so a sparse user override
    # (e.g. CO2 for 2050+2100 only) does NOT replace the full
    # historical trajectory with a 2-year stub.
    base_df = _load_rcmip3_baseline(
        Path(rcmip3_bundle_path), scenario_names, nystart, nyend,
    )

    if user_df.empty and base_df.empty:
        return pd.DataFrame()

    if user_df.empty:
        merged = base_df
    elif base_df.empty:
        merged = user_df
    else:
        base_by_key = {
            (r["scenario"], r["magicc_species"]): r
            for _, r in base_df.iterrows()
        }
        merged_rows: list[dict] = []
        user_keys: set[tuple[str, str]] = set()
        for _, urow in user_df.iterrows():
            key = (urow["scenario"], urow["magicc_species"])
            user_keys.add(key)
            brow = base_by_key.get(key)
            if brow is None:
                merged_rows.append(dict(urow))
                continue
            combined = brow["series"].copy()
            combined.update(urow["series"])
            merged_rows.append({
                "scenario": urow["scenario"],
                "magicc_species": urow["magicc_species"],
                "unit": urow["unit"] or brow["unit"],
                "series": combined.sort_index(),
            })
        for key, brow in base_by_key.items():
            if key not in user_keys:
                merged_rows.append(dict(brow))
        merged = pd.DataFrame(merged_rows)

    # v1 supports only the WMGHGs that MAGICC exposes via per-gas
    # ``FILE_<gas>_CONC`` cfg flags. F-gases / Montreal halocarbons
    # fall through to the SCEN7 emissions-driven path until the
    # bundled-array (``FGAS_FILES_CONC`` / ``MHALO_FILES_CONC``)
    # support lands.
    unsupported = (
        set(merged["magicc_species"].unique())
        - SUPPORTED_PER_GAS_CONC_SPECIES
    )
    if unsupported:
        LOGGER.info(
            "MAGICC7 conc-driven v1: dropping %d species without per-gas "
            "cfg flag support; they will be driven by SCEN7 emissions "
            "instead. Bundled-array F-gas / Montreal-halocarbon support "
            "is a follow-up. Dropped: %s",
            len(unsupported), sorted(unsupported),
        )
    merged = merged[
        merged["magicc_species"].isin(SUPPORTED_PER_GAS_CONC_SPECIES)
    ].copy()
    if merged.empty:
        return pd.DataFrame()

    # Per-gas mixed-mode filter: a species qualifies only when all
    # batch scenarios supply a trajectory for it. Drop the rest so the
    # SCEN7 emissions-driven path handles them uniformly.
    species_per_scenario = (
        merged.groupby("scenario")["magicc_species"].agg(set).to_dict()
    )
    if not species_per_scenario:
        return pd.DataFrame()
    common_species: set[str] = set.intersection(
        *(species_per_scenario.get(s, set()) for s in scenario_names)
    )
    dropped = {
        sp
        for spset in species_per_scenario.values()
        for sp in spset
    } - common_species
    if dropped:
        LOGGER.info(
            "MAGICC7 conc-driven: %d species dropped from concentration "
            "overlay (not present in every batch scenario); will be "
            "driven by emissions instead: %s",
            len(dropped), sorted(dropped),
        )
    if not common_species:
        return pd.DataFrame()

    LOGGER.info(
        "MAGICC7 conc-driven: %d species driven by concentration: %s",
        len(common_species), sorted(common_species),
    )

    merged = merged[merged["magicc_species"].isin(common_species)].copy()

    # Apply MAGICC's canonical concentration units. Conversion from
    # the RCMIP3 / user-supplied unit is currently a no-op assumption
    # (RCMIP3 ships ppm/ppb/ppt directly); revisit if a bundle ever
    # ships something else for a given species.
    unit_lookup = _conc_units_lookup()
    merged["unit"] = merged["magicc_species"].apply(
        lambda sp: unit_lookup.get(sp, _FALLBACK_CONC_UNITS.get(sp, "1")),
    )

    return merged.reset_index(drop=True)


def _load_rcmip3_baseline(
    rcmip3_bundle_path: Path,
    scenario_names: list[str],
    nystart: int,
    nyend: int,
) -> pd.DataFrame:
    """
    Read the RCMIP3 baseline for the batch's scenarios.

    Returns a frame with the same column layout as the caller-overlay
    half of :func:`build_concentrations_overlay`. Empty frame if the
    bundle has no rows for any of the requested scenarios.
    """
    from ...io.rcmip3 import (
        canonicalise_rcmip3_variable,
        load_rcmip3_concentrations,
    )

    df = load_rcmip3_concentrations(
        rcmip3_bundle_path, scenarios=scenario_names,
    )
    if df.empty:
        return pd.DataFrame()

    year_cols = [
        c
        for c in df.columns
        if isinstance(c, str) and c.isdigit()
        and nystart <= int(c) <= nyend
    ]

    rows: list[dict] = []
    for _, csv_row in df.iterrows():
        variable = canonicalise_rcmip3_variable(csv_row["Variable"])
        if "|" not in variable:
            continue
        species_short = variable.split("|", 1)[1]
        magicc_species = RCMIP_TO_MAGICC_SPECIES.get(
            species_short, species_short,
        )
        series = pd.Series({
            int(year): float(csv_row[year])
            for year in year_cols
            if pd.notna(csv_row[year])
        })
        if series.empty:
            continue
        rows.append({
            "scenario": csv_row["Scenario"],
            "magicc_species": magicc_species,
            "unit": csv_row["Unit"],
            "series": series,
        })
    return pd.DataFrame(rows)


def write_conc_in_file(
    out_path: str,
    scenario: str,
    species: str,
    unit: str,
    series: pd.Series,
    magicc_version: str,
) -> str:
    """
    Write a single MAGICC ``CONC.IN`` file via pymagicc and return its path.

    Wraps :class:`pymagicc.io.MAGICCData` with the right per-gas
    metadata. pymagicc derives ``THISFILE_FIRSTYEAR`` / ``LASTYEAR``
    from the series index and sets ``THISFILE_REGIONMODE`` /
    ``THISFILE_DATTYPE`` automatically for concentration files; we
    only need to set the variable name, unit and region.
    """
    if series.empty:
        raise ValueError(
            f"Cannot write concentration .IN for {scenario}/{species}: "
            "trajectory is empty.",
        )
    frame = pd.DataFrame({
        "model": ["unspecified"],
        "scenario": [scenario],
        "region": ["World"],
        "variable": [f"Atmospheric Concentrations|{species}"],
        "unit": [unit],
        "todo": ["SET"],
        **{int(year): [float(value)] for year, value in series.items()},
    })
    writer = pymagicc.io.MAGICCData(frame)
    writer.metadata = {
        "header": (
            f"CONC.IN file written by openscm_runner for the "
            f"{scenario} scenario, species {species}"
        ),
    }
    writer.write(out_path, magicc_version=magicc_version)
    return out_path
