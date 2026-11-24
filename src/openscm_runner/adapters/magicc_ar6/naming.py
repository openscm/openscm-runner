"""
Translating between our names (and units) and MAGICC's

The gas names and units MAGICC uses are copied (no dependency) from
`tests/regression/scripts/processing.py` in the MAGICC repository.
Unit conversions are done with openscm-units (via pandas-openscm).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from openscm_runner.optional_dependencies import import_optional_dependency

FGAS_NAMES: tuple[str, ...] = (
    "CF4",
    "C2F6",
    "C3F8",
    "C4F10",
    "C5F12",
    "C6F14",
    "C7F16",
    "C8F18",
    "CC4F8",
    "HFC23",
    "HFC32",
    "HFC4310",
    "HFC125",
    "HFC134A",
    "HFC143A",
    "HFC152A",
    "HFC227EA",
    "HFC236FA",
    "HFC245FA",
    "HFC365MFC",
    "NF3",
    "SF6",
    "SO2F2",
)
"""
MAGICC's F-gases, in the order of MAGICC v7.5.3's `FGAS_NAMES` setting

The order matters: MAGICC matches the F-gas input files to gases by position.
We don't pass `FGAS_NAMES` to MAGICC
(we don't think MAGICC respects a changed order),
so this has to be MAGICC's own order.
The integration tests check it against the installation's defaults.
"""

MHALO_NAMES: tuple[str, ...] = (
    "CFC11",
    "CFC12",
    "CFC113",
    "CFC114",
    "CFC115",
    "HCFC22",
    "HCFC141B",
    "HCFC142B",
    "CH3CCL3",
    "CCL4",
    "CH3CL",
    "CH2CL2",
    "CHCL3",
    "CH3BR",
    "HALON1211",
    "HALON1301",
    "HALON2402",
    "HALON1202",
)
"""
MAGICC's Montreal Protocol gases, in the order of MAGICC v7.5.3's `MHALO_NAMES`

As for [FGAS_NAMES][(m).], the order has to be MAGICC's own order.
"""

HALOGENATED_GAS_NAMES: dict[str, str] = {
    "CF4": "CF4",
    "C2F6": "C2F6",
    "C3F8": "C3F8",
    "C4F10": "C4F10",
    "C5F12": "C5F12",
    "C6F14": "C6F14",
    "C7F16": "C7F16",
    "C8F18": "C8F18",
    "cC4F8": "CC4F8",
    "HFC23": "HFC23",
    "HFC32": "HFC32",
    "HFC4310mee": "HFC4310",
    "HFC125": "HFC125",
    "HFC134a": "HFC134A",
    "HFC143a": "HFC143A",
    "HFC152a": "HFC152A",
    "HFC227ea": "HFC227EA",
    "HFC236fa": "HFC236FA",
    "HFC245fa": "HFC245FA",
    "HFC365mfc": "HFC365MFC",
    "NF3": "NF3",
    "SF6": "SF6",
    "SO2F2": "SO2F2",
    "CFC11": "CFC11",
    "CFC12": "CFC12",
    "CFC113": "CFC113",
    "CFC114": "CFC114",
    "CFC115": "CFC115",
    "HCFC22": "HCFC22",
    "HCFC141b": "HCFC141B",
    "HCFC142b": "HCFC142B",
    "CH3CCl3": "CH3CCL3",
    "CCl4": "CCL4",
    "CH3Cl": "CH3CL",
    "CH2Cl2": "CH2CL2",
    "CHCl3": "CHCL3",
    "CH3Br": "CH3BR",
    "Halon1211": "HALON1211",
    "Halon1301": "HALON1301",
    "Halon2402": "HALON2402",
    "Halon1202": "HALON1202",
}
"""
Our name for each halogenated gas (as it appears in variable names) to MAGICC's
"""

GAS_NAMES: dict[str, str] = {
    "CO2": "CO2",
    "CH4": "CH4",
    "N2O": "N2O",
    **HALOGENATED_GAS_NAMES,
}
"""
Our name for each well-mixed greenhouse gas to MAGICC's

Every gas MAGICC can be driven with (by emissions or concentrations) is here.
Anything else isn't something MAGICC knows.
"""


def to_magicc_gas(gas: str) -> str:
    """
    Get MAGICC's name for a well-mixed greenhouse gas

    Parameters
    ----------
    gas
        Gas, as it appears in our variable names (e.g. `"HFC4310mee"`)

    Returns
    -------
    :
        MAGICC's name (e.g. `"HFC4310"`)

    Raises
    ------
    ValueError
        `gas` isn't a gas MAGICC knows
    """
    try:
        return GAS_NAMES[gas]
    except KeyError:
        msg = f"{gas!r} isn't a gas MAGICC knows. Known gases: {sorted(GAS_NAMES)}"
        raise ValueError(msg) from None


# In-line this
EMISSIONS_UNIT_CONVERSION_CONTEXTS: tuple[str, ...] = (
    "NOx_conversions",
    "NH3_conversions",
)
"""
openscm-units contexts needed to convert emissions to MAGICC's units

MAGICC has NOx and NH3 emissions as N.
openscm-units only converts between these with a context
(for NOx, this treats NOx as NO2).
"""


def convert_units(
    timeseries: pd.DataFrame,
    desired_units: Iterable[str],
    *,
    callable_name: str,
    contexts: Iterable[str] | None = None,
) -> pd.DataFrame:
    """
    Convert units using openscm-units

    Parameters
    ----------
    timeseries
        Timeseries to convert, with a `unit` index level

    desired_units
        Unit to convert each row of `timeseries` to (in order)

    callable_name
        Name of the callable doing the conversion (used in error messages)

    contexts
        openscm-units contexts to convert with (if `None`, none)

    Returns
    -------
    :
        `timeseries` in `desired_units`

    Raises
    ------
    pint.DimensionalityError
        A unit can't be converted to the desired unit
    """
    openscm_units = import_optional_dependency(
        "openscm_units",
        requirement="openscm-units",
        callable_name=callable_name,
        extra="magicc-ar6",
    )
    unit_conversion = import_optional_dependency(
        "pandas_openscm.unit_conversion",
        requirement="pandas-openscm",
        callable_name=callable_name,
        extra="magicc-ar6",
    )
    ur = openscm_units.unit_registry

    desired = pd.Series(list(desired_units), index=timeseries.index.droplevel("unit"))
    with ur.context(*contexts) if contexts else contextlib.nullcontext():
        res: pd.DataFrame = unit_conversion.convert_unit(timeseries, desired, ur=ur)

    return res


def get_unique_variable_timeseries(
    inp: pd.DataFrame, *, description: str
) -> pd.DataFrame:
    """
    Get timeseries with only `variable` and `unit` index levels

    Parameters
    ----------
    inp
        Input. All index levels other than `variable` and `unit` are dropped.

    description
        Description of the input (used in error messages)

    Returns
    -------
    :
        `inp` with only `variable` and `unit` index levels

    Raises
    ------
    ValueError
        A variable appears more than once
        (e.g. in more than one region, which we don't support yet)
    """
    out = inp.droplevel([n for n in inp.index.names if n not in ("variable", "unit")])
    variables = out.index.get_level_values("variable")
    duplicated = sorted(set(variables[variables.duplicated()]))
    if duplicated:
        msg = (
            f"Each variable can only appear once in the {description}. "
            f"These appear more than once: {duplicated}"
        )
        raise ValueError(msg)

    return out


def _raise_if_unknown(
    variables: Iterable[str], known: Mapping[str, Any], *, description: str
) -> None:
    unknown = sorted(set(variables) - set(known))
    if unknown:
        msg = (
            f"These {description} variables aren't supported for MAGICC: {unknown}. "
            f"Supported: {sorted(known)}"
        )
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Emissions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MAGICCEmissions:
    """How one of our emissions variables is given to MAGICC"""

    gas: str
    """MAGICC's name for the gas"""

    unit: str
    """Unit to convert to (understood by openscm-units)"""

    magicc_unit: str
    """
    MAGICC's name for the unit

    Same as [unit][(c).] except for halogenated gases,
    where it uses MAGICC's name for the gas.
    """


EMISSIONS_VARIABLES: dict[str, MAGICCEmissions] = {
    "Emissions|CO2|Fossil": MAGICCEmissions("CO2I", "Gt C / yr", "Gt C / yr"),
    "Emissions|CO2|Biosphere": MAGICCEmissions("CO2B", "Gt C / yr", "Gt C / yr"),
    "Emissions|CH4": MAGICCEmissions("CH4", "Mt CH4 / yr", "Mt CH4 / yr"),
    "Emissions|N2O": MAGICCEmissions("N2O", "Mt N2ON / yr", "Mt N2ON / yr"),
    "Emissions|SOx": MAGICCEmissions("SOX", "Mt S / yr", "Mt S / yr"),
    "Emissions|NOx": MAGICCEmissions("NOX", "Mt N / yr", "Mt N / yr"),
    "Emissions|NH3": MAGICCEmissions("NH3", "Mt N / yr", "Mt N / yr"),
    "Emissions|CO": MAGICCEmissions("CO", "Mt CO / yr", "Mt CO / yr"),
    "Emissions|NMVOC": MAGICCEmissions("NMVOC", "Mt NMVOC / yr", "Mt NMVOC / yr"),
    "Emissions|BC": MAGICCEmissions("BC", "Mt BC / yr", "Mt BC / yr"),
    "Emissions|OC": MAGICCEmissions("OC", "Mt OC / yr", "Mt OC / yr"),
    **{
        f"Emissions|{gas}": MAGICCEmissions(
            magicc_gas, f"kt {gas} / yr", f"kt {magicc_gas} / yr"
        )
        for gas, magicc_gas in HALOGENATED_GAS_NAMES.items()
    },
}
"""
Emissions variables MAGICC can be given and how they are given to MAGICC

Note MAGICC's conventions: CO2 as C, N2O as N2ON, NOx and NH3 as N, SOx as S.
Every species other than CO2 is a total
(MAGICC splits these into fossil and biomass burning internally).
"""


def to_magicc_emissions(emissions: pd.DataFrame) -> pd.DataFrame:
    """
    Convert emissions to MAGICC's names and units

    Parameters
    ----------
    emissions
        Emissions with `variable` and `unit` index levels
        (other levels are dropped), years as columns.
        Variables are e.g. `"Emissions|CO2|Fossil"`, `"Emissions|HFC4310mee"`.

    Returns
    -------
    :
        Emissions with `variable` (MAGICC's gas name)
        and `unit` (MAGICC's unit) index levels

    Raises
    ------
    ValueError
        A variable isn't one MAGICC can be given or appears more than once

    pint.DimensionalityError
        A unit can't be converted to the unit MAGICC needs
    """
    timeseries = get_unique_variable_timeseries(emissions, description="emissions")
    variables = timeseries.index.get_level_values("variable")
    _raise_if_unknown(variables, EMISSIONS_VARIABLES, description="emissions")

    specs = [EMISSIONS_VARIABLES[v] for v in variables]
    out = convert_units(
        timeseries,
        [s.unit for s in specs],
        callable_name="to_magicc_emissions",
        contexts=EMISSIONS_UNIT_CONVERSION_CONTEXTS,
    )
    out.index = pd.MultiIndex.from_tuples(
        [(s.gas, s.magicc_unit) for s in specs], names=["variable", "unit"]
    )

    return out


# ---------------------------------------------------------------------------
# Concentrations
# ---------------------------------------------------------------------------

CONCENTRATION_UNITS: dict[str, str] = {
    "CO2": "ppm",
    "CH4": "ppb",
    "N2O": "ppb",
    **dict.fromkeys((*FGAS_NAMES, *MHALO_NAMES), "ppt"),
}
"""The units MAGICC's concentrations are in, keyed by MAGICC's name"""

CONCENTRATION_VARIABLES: dict[str, str] = {
    f"Atmospheric Concentrations|{gas}": magicc_gas
    for gas, magicc_gas in GAS_NAMES.items()
}
"""Concentration variables MAGICC can be given and MAGICC's name for each gas"""


def to_magicc_concentrations(concentrations: pd.DataFrame) -> pd.DataFrame:
    """
    Convert concentrations to MAGICC's names and units

    Parameters
    ----------
    concentrations
        Concentrations with `variable` and `unit` index levels
        (other levels are dropped), years as columns.
        Variables are e.g. `"Atmospheric Concentrations|CO2"`.

    Returns
    -------
    :
        Concentrations in [CONCENTRATION_UNITS][(m).],
        indexed by MAGICC's gas name (index name `variable`)

    Raises
    ------
    ValueError
        A variable isn't one MAGICC can be given or appears more than once

    pint.DimensionalityError
        A unit can't be converted to the unit MAGICC needs
    """
    timeseries = get_unique_variable_timeseries(
        concentrations, description="concentrations"
    )
    variables = timeseries.index.get_level_values("variable")
    _raise_if_unknown(variables, CONCENTRATION_VARIABLES, description="concentration")

    gases = [CONCENTRATION_VARIABLES[v] for v in variables]
    out = convert_units(
        timeseries,
        [CONCENTRATION_UNITS[g] for g in gases],
        callable_name="to_magicc_concentrations",
    )
    out.index = pd.Index(gases, name="variable")

    return out


# ---------------------------------------------------------------------------
# Natural forcing
# ---------------------------------------------------------------------------

NATURAL_FORCING_VARIABLES: dict[str, str] = {
    "Effective Radiative Forcing|Solar": "SOLAR",
    "Effective Radiative Forcing|Volcanic": "VOLCANIC",
}
"""Natural forcing input variables, and MAGICC's name for each"""

NATURAL_FORCING_UNIT = "W/m^2"
"""Unit MAGICC's natural forcing inputs are in"""


def split_natural_forcing(
    inp: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.Series[float]]]:
    """
    Split natural forcing (solar, volcanic) out of an input (converting units)

    Parameters
    ----------
    inp
        Input with `variable` and `unit` index levels, years as columns

    Returns
    -------
    rest :
        Everything that isn't natural forcing

    natural_forcing :
        MAGICC's name (e.g. `"SOLAR"`) to forcing (W/m^2), years as the index.
        Only the natural forcing variables in the input are included.

    Raises
    ------
    ValueError
        A natural forcing variable appears more than once

    pint.DimensionalityError
        A unit can't be converted to W/m^2
    """
    is_natural = inp.index.get_level_values("variable").isin(
        list(NATURAL_FORCING_VARIABLES)
    )
    natural = get_unique_variable_timeseries(
        inp[is_natural], description="natural forcing"
    )
    natural = convert_units(
        natural,
        [NATURAL_FORCING_UNIT] * natural.shape[0],
        callable_name="split_natural_forcing",
    )

    return inp[~is_natural], {
        NATURAL_FORCING_VARIABLES[str(variable)]: natural.iloc[i].astype(float)
        for i, variable in enumerate(natural.index.get_level_values("variable"))
    }


def split_emissions(inp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split emissions out of an input

    Parameters
    ----------
    inp
        Input with a `variable` index level

    Returns
    -------
    rest :
        Everything that isn't emissions

    emissions :
        Emissions (variables that start with `"Emissions|"`)
    """
    is_emissions = inp.index.get_level_values("variable").str.startswith("Emissions|")

    return inp[~is_emissions], inp[is_emissions]


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

OUTPUT_VARIABLES: dict[str, str] = {
    "Surface Air Temperature Change": "DAT_SURFACE_TEMP",
    "Effective Radiative Forcing": "DAT_TOTAL_INCLVOLCANIC_ERF",
    "Effective Radiative Forcing|Anthropogenic": "DAT_TOTAL_ANTHRO_ERF",
    "Effective Radiative Forcing|CO2": "DAT_CO2_ERF",
    "Effective Radiative Forcing|CH4": "DAT_CH4_ERF",
    "Effective Radiative Forcing|N2O": "DAT_N2O_ERF",
    "Effective Radiative Forcing|F-Gases": "DAT_FGASSUM_ERF",
    "Effective Radiative Forcing|Montreal Protocol Halogen Gases": "DAT_MHALOSUM_ERF",
    "Effective Radiative Forcing|Aerosols": "DAT_AEROSOL_ERF",
    "Effective Radiative Forcing|Tropospheric Ozone": "DAT_TROPOZ_ERF",
    "Effective Radiative Forcing|Stratospheric Ozone": "DAT_STRATOZ_ERF",
    "Effective Radiative Forcing|Land-use Change": "DAT_LANDUSE_ERF",
    "Effective Radiative Forcing|Solar": "DAT_SOLAR_ERF",
    "Effective Radiative Forcing|Volcanic": "DAT_VOLCANIC_ANNUAL_ERF",
    "Atmospheric Concentrations|CO2": "DAT_CO2_CONC",
    "Atmospheric Concentrations|CH4": "DAT_CH4_CONC",
    "Atmospheric Concentrations|N2O": "DAT_N2O_CONC",
    "Heat Uptake": "DAT_HEATUPTAKE_EBALANCE_TOTAL",
}
"""
Output variables we know how to get from MAGICC, and MAGICC's name for each

The units come from MAGICC's output
(see [MAGICC_OUTPUT_UNITS][(m).]).

TODO: agree output variable names across adapters.
"""

MAGICC_OUTPUT_UNITS: dict[str, str] = {}
"""
Our name for the units in MAGICC's output, where they differ from MAGICC's

Units not in here are passed through as MAGICC writes them.
"""

MAGICC_GLOBAL_REGION = "GLOBAL"
"""MAGICC's name for the global-mean region in its output"""


def get_output_variables(
    requested: Iterable[str], supported: Iterable[str]
) -> dict[str, str]:
    """
    Get MAGICC's name for each requested output variable

    Parameters
    ----------
    requested
        Our names for the requested outputs

    supported
        Our names for the outputs this adapter supports

    Returns
    -------
    :
        Our name to MAGICC's name for each requested output

    Raises
    ------
    ValueError
        A requested output isn't supported
    """
    requested = tuple(requested)
    supported = tuple(supported)
    unsupported = [v for v in requested if v not in supported]
    if unsupported:
        msg = (
            f"Output variables {unsupported!r} aren't supported by this adapter. "
            f"Supported: {list(supported)!r}"
        )
        raise ValueError(msg)

    return {v: OUTPUT_VARIABLES[v] for v in requested}


def from_magicc_output(
    raw: pd.DataFrame,
    *,
    output_variables: Mapping[str, str],
    first_year: int,
    last_year: int,
    experiment_levels: Mapping[str, Any],
) -> pd.DataFrame:
    """
    Convert MAGICC's output to our names

    Parameters
    ----------
    raw
        Output read by [read_binout][openscm_runner.adapters.magicc_ar6.io.]

    output_variables
        Our name to MAGICC's name for each output

    first_year
        First year to keep
        (MAGICC may be started before the experiment, e.g. in a piControl year)

    last_year
        Last year to keep
        (MAGICC is run a few years past the end of the input,
        because it does odd things in the last year of a run)

    experiment_levels
        Index levels (and their values) that identify the experiment.
        These are added to the output (as the first levels).

    Returns
    -------
    :
        Output with `variable`, `region` and `unit` index levels
        (plus the experiment's levels), years as columns
    """
    global_raw = raw.xs(MAGICC_GLOBAL_REGION, level="region")
    rows = []
    for variable, magicc_variable in output_variables.items():
        selected = global_raw.xs(magicc_variable, level="variable", drop_level=False)
        if selected.shape[0] != 1:
            msg = (
                f"Expected exactly one {magicc_variable} {MAGICC_GLOBAL_REGION} "
                f"timeseries in MAGICC's output, found {selected.shape[0]}"
            )
            raise ValueError(msg)

        (magicc_unit,) = selected.index.get_level_values("unit")
        selected_series = selected.iloc[0]
        unit = MAGICC_OUTPUT_UNITS.get(magicc_unit, magicc_unit)
        rows.append(
            ((variable, "World", unit), selected_series.loc[first_year:last_year])
        )

    out = pd.DataFrame(
        [values for _, values in rows],
        index=pd.MultiIndex.from_tuples(
            [key for key, _ in rows], names=["variable", "region", "unit"]
        ),
    )
    out.columns = out.columns.astype(int)

    if experiment_levels:
        index_manipulation = import_optional_dependency(
            "pandas_openscm.index_manipulation",
            requirement="pandas-openscm",
            callable_name="from_magicc_output",
            extra="magicc-ar6",
        )
        out = index_manipulation.set_index_levels_func(
            out, levels_to_set=dict(experiment_levels)
        )
        out = out.reorder_levels([*experiment_levels, "variable", "region", "unit"])

    return out
