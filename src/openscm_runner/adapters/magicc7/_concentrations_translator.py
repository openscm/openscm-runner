"""
Translate RCMIP3 + user-overlay concentrations into MAGICC7 inputs.

This module is the conc-driven sibling to the SCEN7-writing path in
:mod:`magicc7`. The strategy mirrors the FaIR2 / CICEROSCMPY2
adapters: load a baseline from the canonical RCMIP3 Zenodo bundle
(record `20430630`_) and overlay any ``Atmospheric Concentrations|*``
rows the caller supplies on top, then write one MAGICC ``CONC.IN``
file per (scenario, species) and emit cfg patches pointing MAGICC at
those files.

Per-scenario mixed-mode: a gas is concentration-driven for a given
scenario iff that scenario supplies an
``Atmospheric Concentrations|<species>`` trajectory (either directly
in the user ScmRun, or — failing that — via the RCMIP3 baseline).
Because MAGICC writes an independent cfg + ``CONC.IN`` files per
``(scenario, model)``, the decision is genuinely per-scenario: a gas
can be conc-driven in one scenario and emissions-driven in another in
the same batch. This differs from the FaIR2 adapter, whose
``input_mode`` is a per-species flag shared across the whole FaIR
*instance* (all scenarios), forcing a batch-consistency rule that
MAGICC does not need. Species not supplied for a scenario fall back
silently to that scenario's SCEN7 emissions-driven path.

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


# MAGICC's namelist binds the bundled-array concentration flags
# (``FGAS_FILES_CONC`` / ``MHALO_FILES_CONC``) *positionally* to these
# species-name lists, taken verbatim from ``MAGCFG_DEFAULTALL.CFG``.
# They are hardcoded (rather than read from the run dir) so this
# translator stays binary-free and unit-testable; a
# ``@pytest.mark.magicc`` cross-check test asserts they still match the
# installed binary's ``fgas_names`` / ``mhalo_names``. Order matters:
# the writer fills one array slot per name below.
FGAS_NAMES: tuple[str, ...] = (
    "CF4", "C2F6", "C3F8", "C4F10", "C5F12", "C6F14", "C7F16", "C8F18",
    "CC4F8", "HFC23", "HFC32", "HFC4310", "HFC125", "HFC134A", "HFC143A",
    "HFC152A", "HFC227EA", "HFC236FA", "HFC245FA", "HFC365MFC", "NF3",
    "SF6", "SO2F2",
)
MHALO_NAMES: tuple[str, ...] = (
    "CFC11", "CFC12", "CFC113", "CFC114", "CFC115", "HCFC22", "HCFC141B",
    "HCFC142B", "CH3CCL3", "CCL4", "CH3CL", "CH2CL2", "CHCL3", "CH3BR",
    "HALON1211", "HALON1301", "HALON2402", "HALON1202",
)
_FGAS_SET: frozenset[str] = frozenset(FGAS_NAMES)
_MHALO_SET: frozenset[str] = frozenset(MHALO_NAMES)


def to_magicc_species(species_short: str) -> str:
    """
    Map an RCMIP3 leaf species name to its MAGICC-side name.

    Applies the explicit :data:`RCMIP_TO_MAGICC_SPECIES` renames first
    (halons ``H-1211`` -> ``HALON1211``, ``HFC4310mee`` -> ``HFC4310``,
    ``cC4F8`` -> ``CC4F8``), then falls back to an upper-casing rule for
    pure case differences: RCMIP3 ships mixed-case leaves (``HFC134a``,
    ``CCl4``, ``CH3Cl``, ``Halon1211``) whereas MAGICC's
    ``FGAS_NAMES`` / ``MHALO_NAMES`` are upper-case. Anything else
    round-trips unchanged.
    """
    if species_short in RCMIP_TO_MAGICC_SPECIES:
        return RCMIP_TO_MAGICC_SPECIES[species_short]
    upper = species_short.upper()
    if upper in _FGAS_SET or upper in _MHALO_SET:
        return upper
    return species_short


# Default fall-back concentration units, used when
# ``pymagicc.definitions.MAGICC7_CONCENTRATIONS_UNITS`` does not list
# a species (e.g. on older pymagicc versions). The triplet ppm/ppb/ppt
# is the long-standing MAGICC convention: CO2 -> ppm, CH4 / N2O ->
# ppb, all halocarbons / PFCs / SF6 -> ppt.
_FALLBACK_CONC_UNITS: dict[str, str] = {
    "CO2": "ppm",
    "CH4": "ppb",
    "N2O": "ppb",
    # All F-gases / PFCs / SF6 / Montreal halocarbons report in ppt.
    **{sp: "ppt" for sp in FGAS_NAMES},
    **{sp: "ppt" for sp in MHALO_NAMES},
}


# MAGICC7 exposes per-gas concentration-driving flags
# (``FILE_<gas>_CONC`` + ``<gas>_SWITCHFROMCONC2EMIS_YEAR``) only for
# the three main WMGHGs. F-gases and Montreal halocarbons instead share
# bundled-array flags (``FGAS_FILES_CONC`` indexed positionally by
# :data:`FGAS_NAMES`, ``MHALO_FILES_CONC`` by :data:`MHALO_NAMES`, each
# with a single shared ``*_SWITCHFROMCONC2EMIS_YEAR``). :func:`classify_conc_species`
# routes a species to the right path; everything else is unsupported and
# falls back to the SCEN7 emissions path.
PER_GAS_CONC_SPECIES: frozenset[str] = frozenset({"CO2", "CH4", "N2O"})
SUPPORTED_PER_GAS_CONC_SPECIES: frozenset[str] = (
    PER_GAS_CONC_SPECIES | _FGAS_SET | _MHALO_SET
)


def classify_conc_species(magicc_species: str) -> str | None:
    """
    Classify a MAGICC-side species into its conc-driving cfg mechanism.

    Returns ``"per_gas"`` for CO2/CH4/N2O (per-gas ``FILE_<gas>_CONC``
    flags), ``"fgas"`` / ``"mhalo"`` for species in the bundled-array
    groups, or ``None`` if MAGICC has no concentration-driving path for
    it (caller should fall back to SCEN7 emissions).
    """
    if magicc_species in PER_GAS_CONC_SPECIES:
        return "per_gas"
    if magicc_species in _FGAS_SET:
        return "fgas"
    if magicc_species in _MHALO_SET:
        return "mhalo"
    return None


def cfg_keys_for_species(magicc_species: str) -> tuple[str, str]:
    """
    Return the ``(file_<gas>_conc, <gas>_switchfromconc2emis_year)``
    MAGICC cfg flag pair for a given MAGICC-side species name.

    Only valid for the per-gas WMGHGs (``CO2`` / ``CH4`` / ``N2O``);
    raises :class:`ValueError` otherwise. F-gases / Montreal halocarbons
    use bundled-array flags handled separately (see
    :func:`classify_conc_species`).
    """
    if magicc_species not in PER_GAS_CONC_SPECIES:
        raise ValueError(
            f"cfg_keys_for_species only handles per-gas species "
            f"{sorted(PER_GAS_CONC_SPECIES)}; got {magicc_species!r}. "
            f"F-gases / Montreal halocarbons use the bundled-array path."
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

    Reads ``rcmip_phase3_concentrations_v2.0.0.csv`` for the baseline
    and overlays any ``Atmospheric Concentrations|*`` rows the caller
    supplied in ``scenario_run``. The decision is per-scenario: every
    ``(scenario, species)`` for which a trajectory exists (baseline or
    overlay) and which MAGICC can concentration-drive
    (:func:`classify_conc_species`) survives. There is no
    batch-consistency requirement — a gas can be conc-driven in one
    scenario and emissions-driven in another in the same batch.

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
                magicc_species = to_magicc_species(species_short)
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

    # Keep only species MAGICC can concentration-drive (per-gas WMGHGs
    # plus the bundled-array F-gas / Montreal-halocarbon groups).
    # Anything else falls through to the SCEN7 emissions-driven path.
    unsupported = (
        set(merged["magicc_species"].unique())
        - SUPPORTED_PER_GAS_CONC_SPECIES
    )
    if unsupported:
        LOGGER.info(
            "MAGICC7 conc-driven: dropping %d species MAGICC cannot "
            "concentration-drive; they will be driven by SCEN7 emissions "
            "instead: %s",
            len(unsupported), sorted(unsupported),
        )
    merged = merged[
        merged["magicc_species"].isin(SUPPORTED_PER_GAS_CONC_SPECIES)
    ].copy()
    if merged.empty:
        return pd.DataFrame()

    # No batch-consistency filter: every surviving (scenario, species)
    # row is conc-driven for that scenario. MAGICC writes an independent
    # cfg + CONC.IN per (scenario, model), so unlike FaIR2 a gas need
    # not be supplied by every scenario in the batch.
    for scenario in scenario_names:
        species = sorted(
            merged.loc[merged["scenario"] == scenario, "magicc_species"]
        )
        if species:
            LOGGER.info(
                "MAGICC7 conc-driven: scenario %s — %d species driven by "
                "concentration: %s",
                scenario, len(species), species,
            )

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
        magicc_species = to_magicc_species(species_short)
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


# MAGICC7 reads every ``*_CONC.IN`` file as a contiguous *annual*
# series spanning its full internal integration window: the binary's
# own shipped concentration files (e.g. ``SSP245_CO2_CONC.IN``) all
# carry ``THISFILE_ANNUALSTEPS = 1`` over 1700-2500 (801 rows). Feeding
# it a sparse / shorter series makes the Fortran ``readdata`` routine
# hit end-of-file. We therefore resample whatever (possibly sparse)
# trajectory we have onto this grid before writing.
MAGICC_CONC_FIRSTYEAR = 1700
MAGICC_CONC_LASTYEAR = 2500


def _to_annual_magicc_grid(series: pd.Series) -> pd.Series:
    """
    Resample a (year-indexed) concentration series onto MAGICC's
    annual 1700-2500 grid.

    Values are linearly interpolated between supplied years and held
    constant (the nearest endpoint) outside the supplied range, so a
    bundle that only covers, say, 1750-2100 still yields a file MAGICC
    can read end to end.
    """
    s = series.copy()
    s.index = s.index.astype(int)
    s = s.sort_index()
    annual = pd.Index(range(MAGICC_CONC_FIRSTYEAR, MAGICC_CONC_LASTYEAR + 1))
    return (
        s.reindex(s.index.union(annual))
        .interpolate(method="index")
        .reindex(annual)
        .ffill()
        .bfill()
    )


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
    metadata. The trajectory is first resampled onto MAGICC's annual
    1700-2500 grid (see :func:`_to_annual_magicc_grid`); pymagicc then
    derives ``THISFILE_FIRSTYEAR`` / ``LASTYEAR`` / ``ANNUALSTEPS`` from
    that index and sets ``THISFILE_REGIONMODE`` / ``THISFILE_DATTYPE``
    automatically for concentration files; we only need to set the
    variable name, unit and region.
    """
    if series.empty:
        raise ValueError(
            f"Cannot write concentration .IN for {scenario}/{species}: "
            "trajectory is empty.",
        )
    series = _to_annual_magicc_grid(series)
    # pymagicc cross-checks the data variable against the one it parses
    # back out of the filename, and it uses its own openscm naming
    # (``HFC134a``, ``Halon1211``, ``CCl4``) rather than MAGICC's
    # upper-case species token. Derive that canonical name so the check
    # passes; for CO2/CH4/N2O it is identical to ``species``.
    openscm_variable = pymagicc.definitions.convert_magicc7_to_openscm_variables(
        f"{species}_CONC",
    )
    frame = pd.DataFrame({
        "model": ["unspecified"],
        "scenario": [scenario],
        "region": ["World"],
        "variable": [openscm_variable],
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
