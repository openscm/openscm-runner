"""Reader for the canonical RCMIP Phase 3 wide-table CSV bundle.

The bundle is published on Zenodo as record `20430630`_, containing
the protocol spec plus per-scenario wide-table CSVs covering
concentrations, emissions and effective radiative forcing across the
RCMIP3 scenario set (ssp119 / ssp126 / ssp245 / ssp370 / ssp434 /
ssp460 / ssp534-over / ssp585, historical, hist-* attribution runs,
piControl, 1pctCO2 family, abrupt-* family, esm-allGHG-* variants).

All three wide-table CSVs share the same layout:

    Model,Scenario,Region,Variable,Unit,Activity_Id,Type,Priority,Mip_Era,Version,1750,1751,…,2500

One row per ``(Model, Scenario, Variable)`` tuple; year columns are
strings on disk. Variable names use the openscm-runner / IAMC
hierarchical convention with pipe separators, e.g.
``Atmospheric Concentrations|F-Gases|HFC|HFC125``.

The :func:`load_rcmip3` entry point reads one of the three CSV
families and returns a filtered :class:`pandas.DataFrame` in the
wide layout above. Adapters that need a different shape (e.g. FaIR's
``fill_from_pandas`` form) reshape on top of this reader.

.. _20430630: https://zenodo.org/records/20430630
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import pandas as pd

# Metadata columns the RCMIP3 wide-tables carry, in canonical order.
# Year columns (strings on disk: "1750", "1751", …, "2500") follow
# these.
RCMIP3_METADATA_COLS: tuple[str, ...] = (
    "Model",
    "Scenario",
    "Region",
    "Variable",
    "Unit",
    "Activity_Id",
    "Type",
    "Priority",
    "Mip_Era",
    "Version",
)

# Canonical filenames inside the Zenodo bundle.
_KIND_FILENAMES: dict[str, str] = {
    "concentrations": "rcmip_phase3_concentrations_v2.0.0.csv",
    "emissions": "rcmip_phase3_emissions_v2.0.0.csv",
    "forcing": "rcmip_phase3_forcing_v2.0.0.csv",
}

RCMIP3_KIND = Literal["concentrations", "emissions", "forcing"]


def _resolve_path(path: Path | str, kind: RCMIP3_KIND) -> Path:
    """Resolve ``path`` to the requested kind's canonical CSV.

    Accepts either a direct CSV path or a bundle root directory
    containing ``RCMIP3_input_datafiles/<canonical_filename>``.
    """
    p = Path(path)
    if p.is_file():
        return p
    canonical = _KIND_FILENAMES[kind]
    for candidate in (
        p / canonical,
        p / "RCMIP3_input_datafiles" / canonical,
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"RCMIP3 {kind} CSV not found. Looked for "
        f"{p}, {p / canonical}, "
        f"{p / 'RCMIP3_input_datafiles' / canonical}. Download the "
        "bundle from https://zenodo.org/records/20430630 and pass "
        "either the bundle root or the CSV path directly."
    )


def load_rcmip3(
    path: Path | str,
    kind: RCMIP3_KIND,
    scenarios: Iterable[str] | None = None,
    variables: Iterable[str] | None = None,
    region: str | None = "World",
    model: str | None = None,
) -> pd.DataFrame:
    """Load and filter one of the RCMIP3 wide-table CSVs.

    Parameters
    ----------
    path
        Either a path to the CSV directly, or to the bundle root /
        ``RCMIP3_input_datafiles`` subdirectory. :func:`_resolve_path`
        figures out which CSV to read based on ``kind``.
    kind
        Which CSV family to read: ``"concentrations"``, ``"emissions"``
        or ``"forcing"``.
    scenarios
        Restrict output to this set of Scenario names. ``None``
        (default) returns every scenario in the file.
    variables
        Restrict output to this set of Variable names. ``None``
        returns every variable.
    region
        Restrict output to this Region. Defaults to ``"World"``; pass
        ``None`` to keep all regions.
    model
        Restrict output to this Model. ``None`` (default) keeps all
        models. The RCMIP3 forcing CSV carries multiple models per
        scenario (e.g. ``MESSAGE-GLOBIOM`` for SSP-RCP / CMIP6 rows
        and ``emissions_harmonisation_pipeline`` for CMIP7 ScenarioMIP
        rows); use this to disambiguate.

    Returns
    -------
    pandas.DataFrame
        Wide-format frame: metadata columns (
        :data:`RCMIP3_METADATA_COLS`) followed by year columns as
        strings, filtered to the requested subset. Empty frame with
        the right columns if no rows match.
    """
    csv_path = _resolve_path(path, kind)
    df = pd.read_csv(csv_path)

    expected_meta = list(RCMIP3_METADATA_COLS)
    missing_meta = [c for c in expected_meta if c not in df.columns]
    if missing_meta:
        raise ValueError(
            f"RCMIP3 {kind} CSV at {csv_path} is missing expected "
            f"metadata columns: {missing_meta}. Got columns: "
            f"{list(df.columns)[:15]}…"
        )

    if scenarios is not None:
        df = df[df["Scenario"].isin(list(scenarios))]
    if variables is not None:
        df = df[df["Variable"].isin(list(variables))]
    if region is not None:
        df = df[df["Region"] == region]
    if model is not None:
        df = df[df["Model"] == model]

    return df.reset_index(drop=True)


def load_rcmip3_concentrations(
    path: Path | str,
    scenarios: Iterable[str] | None = None,
    variables: Iterable[str] | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Read RCMIP3 concentrations, filtered. See :func:`load_rcmip3`."""
    return load_rcmip3(
        path, "concentrations", scenarios=scenarios, variables=variables,
        **kwargs,
    )


def load_rcmip3_emissions(
    path: Path | str,
    scenarios: Iterable[str] | None = None,
    variables: Iterable[str] | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Read RCMIP3 emissions, filtered. See :func:`load_rcmip3`."""
    return load_rcmip3(
        path, "emissions", scenarios=scenarios, variables=variables,
        **kwargs,
    )


def load_rcmip3_forcings(
    path: Path | str,
    scenarios: Iterable[str] | None = None,
    variables: Iterable[str] | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Read RCMIP3 effective radiative forcings, filtered.

    See :func:`load_rcmip3`. Note the canonical CSV ships per-scenario
    ``Effective Radiative Forcing|Anthropogenic|Albedo Change`` (lumped
    land use + irrigation) for the SSP-RCP scenarios; the
    ``|Land Use`` / ``|Irrigation`` breakdown is only published for
    ``historical``. Callers that need the breakdown must reach into
    the bundle's ``input_datafiles_generation/data/Forcing_AFOLU_CO2.csv``
    and ``Forcing_irrigation_population_scale.csv`` directly (those
    files are keyed by CMIP7 scenario category VL / LN / L / ML / M /
    H / HL, not by SSP-RCP scenario name; see
    :func:`load_rcmip3_albedo_categories`).
    """
    return load_rcmip3(
        path, "forcing", scenarios=scenarios, variables=variables,
        **kwargs,
    )


_RCMIP3_TO_OPENSCM_CO2_SECTOR: dict[str, str] = {
    "AFOLU": "MAGICC AFOLU",
    "Energy and Industrial Processes": "MAGICC Fossil and Industrial",
}

_RCMIP3_INTERMEDIATE_CATEGORIES: frozenset[str] = frozenset({
    "F-Gases",
    "PFC",
    "HFC",
    "Montreal Gases",
    "CFC",
    "HCFC",
    "Halon",
})


def canonicalise_rcmip3_variable(variable: str) -> str:
    """Translate a canonical RCMIP3 variable name to openscm-runner conventions.

    The canonical RCMIP3 CSV uses a few variable-name conventions that
    differ from the MAGICC-style names openscm-runner adapters (FaIR2,
    CICEROSCMPY2) work with internally. Specifically:

    * CO2 sub-sectors carry RCMIP-native labels in the canonical CSV
      (``Emissions|CO2|AFOLU``,
      ``Emissions|CO2|Energy and Industrial Processes``). MAGICC-style
      labels are ``Emissions|CO2|MAGICC AFOLU`` and
      ``Emissions|CO2|MAGICC Fossil and Industrial``.
    * F-gases, PFCs, HFCs, Montreal Gases, CFCs, HCFCs and Halons
      carry intermediate IAMC categories in the canonical CSV (e.g.
      ``Emissions|PFC|C2F6``,
      ``Atmospheric Concentrations|F-Gases|HFC|HFC125``). openscm-runner
      uses flat names (``Emissions|C2F6``,
      ``Atmospheric Concentrations|HFC125``).

    This helper canonicalises the name by applying the rewrite. Names
    that don't need translation (e.g. ``Emissions|CH4``,
    ``Effective Radiative Forcing|Natural|Solar``) round-trip unchanged.
    """
    parts = variable.split("|")
    if len(parts) < 3:
        return variable

    prefix = parts[0]

    if (
        parts[1] == "CO2"
        and len(parts) == 3
        and parts[2] in _RCMIP3_TO_OPENSCM_CO2_SECTOR
    ):
        return f"{prefix}|CO2|{_RCMIP3_TO_OPENSCM_CO2_SECTOR[parts[2]]}"

    if any(p in _RCMIP3_INTERMEDIATE_CATEGORIES for p in parts[1:-1]):
        return f"{prefix}|{parts[-1]}"

    return variable


# Scenario-category mapping used by the RCMIP3 upstream generation
# script (input_datafiles_generation/loop_through_protocol_and_make_input_csvs.py),
# which feeds per-category CMIP7 ScenarioMIP runs into the canonical
# wide-tables. Captured here for callers that need the per-category
# irrigation / land-use albedo split. Coverage matches the
# "scen7-{category}" forms in the upstream generator dictionary.
_RCMIP3_CMIP7_CATEGORY_TO_SSP: dict[str, str] = {
    "VL": "SSP1",
    "LN": "SSP2",
    "L": "SSP2",
    "ML": "SSP2",
    "M": "SSP2",
    "H": "SSP3",
    "HL": "SSP5",
}


# Default SSP-RCP scenario → CMIP7 ScenarioMIP category mapping for
# the canonical per-category irrigation / land-use albedo split.
# There is no canonical SSP-RCP → category mapping (the categories
# are a separate scenario hierarchy in CMIP7 ScenarioMIP, not a
# rename of SSP-RCP); the defaults below pick the category whose
# underlying SSP + emissions intensity best matches each SSP-RCP
# scenario. Callers can override per-cfg via the
# ``scenario_to_category`` cfg key passed to FaIR2 / CICEROSCMPY2.
RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY: dict[str, str] = {
    # SSP1: very low emissions / 1.9 W/m^2 stabilisation -> VL.
    "ssp119": "VL",
    "ssp126": "VL",
    # SSP2: middle of the road. ssp245 is the canonical "medium"
    # IMAGE -> M; ssp434 / ssp460 are SSP4 with no direct CMIP7
    # category match, mapped to the closest SSP2 intensity surrogate.
    "ssp245": "M",
    "ssp434": "L",
    "ssp460": "ML",
    "ssp534-over": "LN",
    # SSP3: high baseline -> H (GCAM).
    "ssp370": "H",
    # SSP5: fossil-fuelled development. HL is "Medium-Low SSP5" —
    # only the SSP5 category in the CMIP7 set; closest by SSP.
    "ssp585": "HL",
}


def resolve_scenario_category(
    scenario: str,
    overrides: dict[str, str] | None = None,
) -> str | None:
    """Resolve an openscm-runner scenario name to a CMIP7 category.

    Returns the category key (``"VL"``, ``"LN"``, ``"L"``, ``"ML"``,
    ``"M"``, ``"H"`` or ``"HL"``) suitable for
    :func:`load_rcmip3_albedo_categories`. Returns ``None`` for
    scenarios that should be handled outside the category lookup
    (``"historical"`` and ``"historical-cmip6"``, which have their own
    per-component breakdown in the canonical forcing CSV).

    Lookup order:

    1. ``overrides`` (per-cfg user mapping), if provided.
    2. Native CMIP7 category names (``"scen7-M"`` → ``"M"`` etc.).
    3. :data:`RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY`.

    Raises
    ------
    KeyError
        Scenario isn't in any of the three sources and isn't a
        recognised historical alias. Caller should either add an
        override or skip the scenario as idealised.
    """
    if overrides and scenario in overrides:
        return overrides[scenario]
    if scenario in ("historical", "historical-cmip6"):
        return None
    if scenario.startswith("scen7-"):
        candidate = scenario.split("scen7-", 1)[1]
        if candidate in _RCMIP3_CMIP7_CATEGORY_TO_SSP:
            return candidate
    if scenario in RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY:
        return RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY[scenario]
    raise KeyError(
        f"No CMIP7 ScenarioMIP category mapping for {scenario!r}. "
        "Either pass a `scenario_to_category` override on the cfg "
        f"(e.g. `{{{scenario!r}: 'M'}}`), or set the scenario's "
        "`protocol_land_use_forcing` meta to 'constant_zero' so "
        "Land use + Irrigation are zeroed instead of category-looked-up."
    )


def load_rcmip3_albedo_categories(
    path: Path | str,
    category: str,
) -> pd.DataFrame:
    """Read per-category land-use + irrigation ERF time series.

    The canonical RCMIP3 forcing CSV only publishes the lumped
    ``Albedo Change`` ERF for SSP-RCP scenarios. The per-component
    breakdown comes from the bundle's upstream
    ``Forcing_AFOLU_CO2.csv`` (land-use albedo) and
    ``Forcing_irrigation_population_scale.csv`` (irrigation) under
    ``input_datafiles_generation/data/``, keyed by CMIP7 ScenarioMIP
    category (``VL`` / ``LN`` / ``L`` / ``ML`` / ``M`` / ``H`` /
    ``HL``).

    Parameters
    ----------
    path
        Either the bundle root or the ``input_datafiles_generation/data``
        subdir.
    category
        One of ``VL``, ``LN``, ``L``, ``ML``, ``M``, ``H``, ``HL``.

    Returns
    -------
    pandas.DataFrame
        Year-indexed DataFrame with two columns, ``"Land Use"`` and
        ``"Irrigation"``, both in W/m^2.
    """
    if category not in _RCMIP3_CMIP7_CATEGORY_TO_SSP:
        raise ValueError(
            f"Unknown RCMIP3 CMIP7 scenario category {category!r}; "
            f"expected one of {sorted(_RCMIP3_CMIP7_CATEGORY_TO_SSP)}."
        )
    p = Path(path)
    for prefix in (p, p / "input_datafiles_generation" / "data"):
        luc_path = prefix / "Forcing_AFOLU_CO2.csv"
        irr_path = prefix / "Forcing_irrigation_population_scale.csv"
        if luc_path.is_file() and irr_path.is_file():
            break
    else:
        raise FileNotFoundError(
            f"Could not find Forcing_AFOLU_CO2.csv and "
            "Forcing_irrigation_population_scale.csv under "
            f"{p} or {p / 'input_datafiles_generation' / 'data'}."
        )
    luc = pd.read_csv(luc_path, index_col=0)[[category]].rename(
        columns={category: "Land Use"}
    )
    irr = pd.read_csv(irr_path, index_col=0)[[category]].rename(
        columns={category: "Irrigation"}
    )
    out = luc.join(irr)
    out.index = out.index.astype(int)
    return out
