"""
Convert RCMIP-format concentration files into FaIR 2.x's expected shape.

This is the conc-driven counterpart to
:mod:`_emissions_translator`. It reads an RCMIP-format
``{scen}_conc_{gases_ep}.txt`` file (as shipped in Marit's RCMIP
bundle for openscm/openscm-runner#97) and produces a DataFrame
that :meth:`fair.FAIR.fill_from_pandas` will accept with
``mode="concentration"``.

The bundle's RCMIP files look like::

    Component  CO2   CH4   N2O   CFC-11  ...  HFC125  HFC4310mee  cC4F8
    Unit       ppm   ppb   ppb   ppt     ...  ppt     ppt         ppt
    Description ...
    Reference  ...
    1750       277.1 731.4 273.9 ...
    1751       277.1 731.4 273.9 ...
    ...

RCMIP and FaIR mostly agree on species names but FaIR uses
hyphenated forms for HFC / Halon / c-C4F8. The :data:`RCMIP_TO_FAIR2_SPECIES`
map handles the differences; species not in the map are dropped
with a WARNING (typically only ``H-1202`` and ``HCFC-123`` from
the 2024 gaspam, which the AR6 FaIR set does not include).

Units are passed through unchanged (ppm / ppb / ppt match FaIR's
expectations directly per :func:`fair.io.fill_from._concentration_unit_convert`).

Output shape: one row per (scenario, FaIR-species), lowercase
column names so FaIR's ``fill_from_pandas`` doesn't have to
``.str.lower`` first:

    scenario | variable | region | unit | 1750 | 1751 | ... | 2500
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

import pandas as pd

LOGGER = logging.getLogger(__name__)


# RCMIP-side species name -> FaIR 2.x species name. CO2 / CH4 / N2O
# and the CFC / HCFC / SF6 / CF4 / C2F6 / C6F14 species are already
# in matching form across both sides; only the species below need
# explicit translation. Species the FaIR AR6 default set doesn't
# include (e.g. ``H-1202``, ``HCFC-123`` in some bundles) drop out
# silently at the "not in fair_species" check, with a WARNING.
RCMIP_TO_FAIR2_SPECIES = {
    # HFCs: RCMIP uses compact form, FaIR uses hyphenated.
    "HFC125": "HFC-125",
    "HFC134a": "HFC-134a",
    "HFC143a": "HFC-143a",
    "HFC152a": "HFC-152a",
    "HFC227ea": "HFC-227ea",
    "HFC23": "HFC-23",
    "HFC236fa": "HFC-236fa",
    "HFC245fa": "HFC-245fa",
    "HFC32": "HFC-32",
    "HFC365mfc": "HFC-365mfc",
    "HFC4310mee": "HFC-4310mee",
    # Halons: RCMIP uses H- prefix, FaIR uses Halon-.
    "H-1202": "Halon-1202",
    "H-1211": "Halon-1211",
    "H-1301": "Halon-1301",
    "H-2402": "Halon-2402",
    # PFCs / misc.
    "cC4F8": "c-C4F8",
}


def build_concentrations_df_from_scmrun(
    scenario_run,
    fair_species: Iterable[str],
    nystart: int = 1750,
    nyend: int = 2500,
) -> pd.DataFrame:
    """Build a FaIR-compatible concentrations DataFrame from a mixed-mode ScmRun.

    The loader's protocol-strict ED CO2-only path
    (``openscm_runner.scenarios.rcmip3._load_mixed_mode_scenario``)
    emits a single ScmRun containing CO2 emissions plus non-CO2
    Atmospheric Concentrations. This helper extracts the concentration
    half and shapes it for :meth:`fair.FAIR.fill_from_pandas`
    (``mode="concentration"``), mirroring :func:`build_concentrations_df`.

    Variable names are translated from the loader's canonical
    ``Atmospheric Concentrations|{species}`` form (RCMIP-style short
    species names like ``HFC125``) to FaIR's hyphenated species
    (``HFC-125``) via the same :data:`RCMIP_TO_FAIR2_SPECIES` map
    the bundle path uses. Species not in ``fair_species`` are dropped.

    Returns an empty DataFrame when the input has no
    ``Atmospheric Concentrations|*`` rows — caller checks ``.empty``.
    """
    fair_species_set = set(fair_species)
    conc_run = scenario_run.filter(variable="Atmospheric Concentrations|*")
    if conc_run.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    ts = conc_run.timeseries(time_axis="year")
    for index_tuple, values in ts.iterrows():
        meta = dict(zip(ts.index.names, index_tuple))
        variable = meta["variable"]
        # variable is "Atmospheric Concentrations|<species>"; strip the prefix.
        species_short = variable.split("|", 1)[1]
        fair_name = RCMIP_TO_FAIR2_SPECIES.get(species_short, species_short)
        if fair_name not in fair_species_set:
            continue
        row = {
            "scenario": meta.get("scenario"),
            "variable": fair_name,
            "region": meta.get("region", "World"),
            "unit": meta.get("unit"),
        }
        for year, value in values.items():
            if nystart <= int(year) <= nyend:
                row[str(int(year))] = float(value)
        rows.append(row)

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out.columns = [c.lower() if not c.isdigit() else c for c in out.columns]
    return out


def build_concentrations_df_from_rcmip3(
    rcmip3_bundle_path,
    scenario_names: Iterable[str],
    fair_species: Iterable[str],
    nystart: int = 1750,
    nyend: int = 2500,
) -> pd.DataFrame:
    """
    Build a FaIR-compatible concentrations DataFrame from the canonical
    RCMIP3 Zenodo 20430630 bundle.

    Reads ``rcmip_phase3_concentrations_v2.0.0.csv``, filters to the
    requested ``scenario_names``, canonicalises each row's Variable
    via :func:`openscm_runner.io.canonicalise_rcmip3_variable` (strips
    intermediate IAMC categories like ``|F-Gases|HFC|`` so the leaf
    species name ends up adjacent to ``Atmospheric Concentrations|``),
    and translates each leaf species to FaIR's hyphenated form via
    :data:`RCMIP_TO_FAIR2_SPECIES`. Species not in ``fair_species``
    are dropped silently (matches the legacy bundle path).

    Returned shape matches :func:`build_concentrations_df` and
    :func:`build_concentrations_df_from_scmrun`: lowercase metadata
    columns + string-keyed year columns ready for
    ``fair.FAIR.fill_from_pandas(mode="concentration")``.
    """
    from ...io.rcmip3 import (
        canonicalise_rcmip3_variable,
        load_rcmip3_concentrations,
    )

    fair_species_set = set(fair_species)
    df = load_rcmip3_concentrations(
        rcmip3_bundle_path, scenarios=list(scenario_names),
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
    dropped: set[str] = set()
    for _, csv_row in df.iterrows():
        variable = canonicalise_rcmip3_variable(csv_row["Variable"])
        if "|" not in variable:
            continue
        species_short = variable.split("|", 1)[1]
        fair_name = RCMIP_TO_FAIR2_SPECIES.get(species_short, species_short)
        if fair_name not in fair_species_set:
            dropped.add(species_short)
            continue
        row: dict = {
            "scenario": csv_row["Scenario"],
            "variable": fair_name,
            "region": csv_row.get("Region", "World"),
            "unit": csv_row["Unit"],
        }
        for year_str in year_cols:
            row[year_str] = float(csv_row[year_str])
        rows.append(row)

    if dropped:
        LOGGER.info(
            "FaIRv2 RCMIP3 concentrations: %d species in canonical CSV "
            "not in the FaIR species set; dropped: %s",
            len(dropped), sorted(dropped),
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out.columns = [c.lower() if not c.isdigit() else c for c in out.columns]
    return out
