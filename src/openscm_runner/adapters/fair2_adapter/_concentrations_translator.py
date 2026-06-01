"""
Convert CICERO-format concentration files into FaIR 2.x's expected shape.

This is the conc-driven counterpart to
:mod:`_emissions_translator`. It reads a CICERO-format
``{scen}_conc_{gases_ep}.txt`` file (as shipped in Marit's RCMIP
bundle) and produces a DataFrame that
:meth:`fair.FAIR.fill_from_pandas` will accept with
``mode="concentration"``.

The bundle's CICERO files look like::

    Component  CO2   CH4   N2O   CFC-11  ...  HFC125  HFC4310mee  cC4F8
    Unit       ppm   ppb   ppb   ppt     ...  ppt     ppt         ppt
    Description ...
    Reference  ...
    1750       277.1 731.4 273.9 ...
    1751       277.1 731.4 273.9 ...
    ...

CICERO and FaIR mostly agree on species names but FaIR uses
hyphenated forms for HFC / Halon / c-C4F8. The :data:`CICERO_TO_FAIR2_SPECIES`
map handles the differences; species not in the map are dropped
with a WARNING (typically only ``H-1202`` and ``HCFC-123`` from
the CICERO 2024 gaspam, which the AR6 FaIR set does not include).

Units are passed through unchanged (ppm / ppb / ppt match FaIR's
expectations directly per :func:`fair.io.fill_from._concentration_unit_convert`).

Output shape: one row per (scenario, FaIR-species), lowercase
column names so FaIR's ``fill_from_pandas`` doesn't have to
``.str.lower`` first:

    scenario | variable | region | unit | 1750 | 1751 | ... | 2500
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable

import pandas as pd

LOGGER = logging.getLogger(__name__)


# CICERO-side species name -> FaIR 2.x species name. CO2 / CH4 / N2O
# and the CFC / HCFC / SF6 / CF4 / C2F6 / C6F14 species are already
# in matching form across both sides; only the species below need
# explicit translation. Species the FaIR AR6 default set doesn't
# include (e.g. ``H-1202``, ``HCFC-123`` in some bundles) drop out
# silently at the "not in fair_species" check, with a WARNING.
CICERO_TO_FAIR2_SPECIES = {
    # HFCs: CICERO uses compact form, FaIR uses hyphenated.
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
    # Halons: CICERO uses H- prefix, FaIR uses Halon-.
    "H-1202": "Halon-1202",
    "H-1211": "Halon-1211",
    "H-1301": "Halon-1301",
    "H-2402": "Halon-2402",
    # PFCs / misc.
    "cC4F8": "c-C4F8",
}


def _read_cicero_conc_file(path: str) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Parse a CICERO-format concentration file.

    Returns (df, column_units):
    - ``df``: year-indexed DataFrame with CICERO species names as
      columns and float values.
    - ``column_units``: dict mapping each species column to its CICERO
      unit string (typically ``ppm``, ``ppb``, ``ppt``).
    """
    df = (
        pd.read_csv(path, delimiter="\t", index_col=0, skiprows=[1, 2, 3])
        .rename(columns=lambda x: x.strip())
        .astype(float)
    )
    df.index = df.index.astype(int)

    # Pull units from header line 2 ("Unit \t ppm\t ppb\t ...").
    with open(path) as fh:
        _ = next(fh)  # "Component" row
        unit_line = next(fh)
    unit_tokens = [t.strip() for t in unit_line.rstrip("\n").split("\t")]
    # First token is "Unit" label; the rest line up positionally with df.columns.
    column_units = dict(zip(df.columns, unit_tokens[1:]))
    return df, column_units


def build_concentrations_df(  # noqa: PLR0913
    bundle_dir: str,
    gases_ep: str,
    scenario_names: Iterable[str],
    fair_species: Iterable[str],
    nystart: int = 1750,
    nyend: int = 2500,
) -> pd.DataFrame:
    """
    Build a FaIR-compatible concentrations DataFrame from CICERO bundle files.

    One file per scenario is read from ``{bundle_dir}/{scen}_conc_{gases_ep}``,
    with fallback to ``{bundle_dir}/historical_conc_{gases_ep}`` for
    scenarios the bundle has no scen-specific file for (mirrors the
    fallback logic in
    :func:`openscm_runner.adapters.ciceroscm_py2_adapter._build_scendata_list_bundle`
    so CICERO and FaIR see the same concentration trajectory per scenario).

    ``fair_species`` filters the output to species the FaIR FAIR
    instance actually has defined; species in the CICERO file but not
    in FaIR's species list are silently dropped. Species in the
    CICERO_TO_FAIR2_SPECIES map are translated before this filter.

    The returned DataFrame has the shape ``fill_from_pandas(mode="concentration")``
    wants: one row per ``(scenario, variable)`` with ``scenario``,
    ``variable``, ``region``, ``unit`` columns and one column per year
    in ``[nystart, nyend]``. Column names are lowercased to match
    upstream's expectation.
    """
    fair_species_set = set(fair_species)
    rows: list[dict] = []
    dropped: set[str] = set()

    for scenario_name in scenario_names:
        conc_path = _pick_conc_file(bundle_dir, scenario_name, gases_ep)
        if conc_path is None:
            LOGGER.warning(
                "FaIRv2 conc-driven: no bundle conc file for scenario %r "
                "(and no historical_conc fallback). Skipping.",
                scenario_name,
            )
            continue

        df, column_units = _read_cicero_conc_file(conc_path)
        df = df.loc[nystart:nyend]

        for cicero_name in df.columns:
            fair_name = CICERO_TO_FAIR2_SPECIES.get(cicero_name, cicero_name)
            if fair_name not in fair_species_set:
                dropped.add(cicero_name)
                continue
            row = {
                "scenario": scenario_name,
                "variable": fair_name,
                "region": "World",
                "unit": column_units[cicero_name],
            }
            # Year columns as strings to match fair's str.lower-friendly form.
            for year in df.index:
                row[str(year)] = float(df.at[year, cicero_name])
            rows.append(row)

    if dropped:
        LOGGER.info(
            "FaIRv2 conc-driven: %d CICERO species in the bundle conc file "
            "are not in the FaIR species set and were dropped: %s",
            len(dropped),
            sorted(dropped),
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # Lowercase columns the way fair.fill_from_pandas does internally.
    out.columns = [c.lower() if not c.isdigit() else c for c in out.columns]
    return out


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
    ``Atmospheric Concentrations|{species}`` form (CICERO-style short
    species names like ``HFC125``) to FaIR's hyphenated species
    (``HFC-125``) via the same :data:`CICERO_TO_FAIR2_SPECIES` map
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
        fair_name = CICERO_TO_FAIR2_SPECIES.get(species_short, species_short)
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


def _pick_conc_file(bundle_dir: str, scenario_name: str, gases_ep: str):
    """Scenario-specific bundle conc file, falling back to historical."""
    for candidate in (
        f"{scenario_name}_conc_{gases_ep}",
        f"historical_conc_{gases_ep}",
    ):
        path = os.path.join(bundle_dir, candidate)
        if os.path.exists(path):
            return path
    return None
