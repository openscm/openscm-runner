"""
Input definitions

CMIP6 and CMIP7 inputs currently have the same shape.
They are still separate definitions
so we can change them independently if we wish
and because the experiments are different
(the adapter branches off a different pre-industrial state).

The variable constants are named after CMIP7 (`CMIP7_*`)
and the CMIP6 definitions re-use them,
rather than implying that one definition applies to every CMIP era.
If the eras' definitions diverge, add `CMIP6_*` constants where needed.
"""

from __future__ import annotations

from typing import TypeAlias

import pandas as pd

from openscm_runner.verification import verify_wide_timeseries_inputs

CMIP6_PRE_INDUSTRIAL_BRANCH_YEAR = 1850
"""First year of runs branching off the CMIP6 pre-industrial state"""

CMIP7_PRE_INDUSTRIAL_BRANCH_YEAR = 1850
"""First year of runs branching off the CMIP7 pre-industrial state"""

CMIP7_CO2_CONCENTRATION_VARIABLES: frozenset[str] = frozenset(
    {"Atmospheric Concentrations|CO2"}
)
"""Variables required for CO2-concentration-driven runs"""

CMIP7_CO2_EMISSION_VARIABLES: frozenset[str] = frozenset({"Emissions|CO2|Fossil"})
"""
Variables required for CO2-emission-driven runs

Fossil CO2 emissions only:
biosphere CO2 emissions are off in the CO2-only experiments
(there is no land-use change).
`Emissions|CO2|Fossil` is the canonical input name, including for idealised
runs such as esm-flat10 where the source data has no fossil/biosphere split.
How adapters should handle CO2 emissions inputs is still to be decided
(decision [A6][a6]).
"""

CMIP7_CONCENTRATION_VARIABLES: frozenset[str] = frozenset(
    {
        "Atmospheric Concentrations|CO2",
        "Atmospheric Concentrations|CH4",
        "Atmospheric Concentrations|N2O",
        "Atmospheric Concentrations|C2F6",
        "Atmospheric Concentrations|C3F8",
        "Atmospheric Concentrations|C4F10",
        "Atmospheric Concentrations|C5F12",
        "Atmospheric Concentrations|C6F14",
        "Atmospheric Concentrations|C7F16",
        "Atmospheric Concentrations|C8F18",
        "Atmospheric Concentrations|cC4F8",
        "Atmospheric Concentrations|CCl4",
        "Atmospheric Concentrations|CF4",
        "Atmospheric Concentrations|CFC11",
        "Atmospheric Concentrations|CFC113",
        "Atmospheric Concentrations|CFC114",
        "Atmospheric Concentrations|CFC115",
        "Atmospheric Concentrations|CFC12",
        "Atmospheric Concentrations|CH2Cl2",
        "Atmospheric Concentrations|CH3Br",
        "Atmospheric Concentrations|CH3CCl3",
        "Atmospheric Concentrations|CH3Cl",
        "Atmospheric Concentrations|CHCl3",
        "Atmospheric Concentrations|Halon1211",
        "Atmospheric Concentrations|Halon1301",
        "Atmospheric Concentrations|Halon2402",
        "Atmospheric Concentrations|HCFC141b",
        "Atmospheric Concentrations|HCFC142b",
        "Atmospheric Concentrations|HCFC22",
        "Atmospheric Concentrations|HFC125",
        "Atmospheric Concentrations|HFC134a",
        "Atmospheric Concentrations|HFC143a",
        "Atmospheric Concentrations|HFC152a",
        "Atmospheric Concentrations|HFC227ea",
        "Atmospheric Concentrations|HFC23",
        "Atmospheric Concentrations|HFC236fa",
        "Atmospheric Concentrations|HFC245fa",
        "Atmospheric Concentrations|HFC32",
        "Atmospheric Concentrations|HFC365mfc",
        "Atmospheric Concentrations|HFC4310mee",
        "Atmospheric Concentrations|NF3",
        "Atmospheric Concentrations|SF6",
        "Atmospheric Concentrations|SO2F2",
    }
)
"""
The 43 concentration species required for CMIP7-style concentration-driven runs
"""

CMIP7_NATURAL_FORCING_VARIABLES: frozenset[str] = frozenset(
    {
        "Effective Radiative Forcing|Solar",
        "Effective Radiative Forcing|Volcanic",
    }
)
"""
Natural forcing variables required for CMIP-style concentration-driven runs

Experiments like historical prescribe solar and volcanic forcing too,
so they can be part of the input.

/// warning | What zero natural forcing means still has to be decided
E.g. RCMIP phase 3's natural ERF isn't zero in 1850
(e.g. volcanic 0.18 (CMIP6) or 0.21 (CMIP7) W/m^2),
and CMIP's piControl uses averages
(e.g. of solar over a solar cycle, of volcanic over the historical period).
So "relative to piControl" needs to be defined (decision [B19][b19]).
///

Whether the input should be ERF (as here)
or something closer to what CMIP provides,
and whether adapters may scale it, is still to be decided (decision [B22][b22]).
Units are not checked yet, W/m^2 is assumed (roadmap [W04][w04]).
"""

CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES: frozenset[str] = frozenset(
    {
        "Emissions|BC",
        "Emissions|CO",
        "Emissions|NH3",
        "Emissions|NMVOC",
        "Emissions|NOx",
        "Emissions|OC",
        "Emissions|SOx",
    }
)
"""
Aerosol and aerosol/ozone precursor emissions required for some CMIP-style runs

CMIP's concentration-driven experiments prescribe these as emissions
(ESMs calculate aerosols and, if they have interactive chemistry, ozone from them).
These are the totals (anthropogenic plus open biomass burning).
"""

CMIP7_CONCENTRATION_DRIVEN_VARIABLES: frozenset[str] = (
    CMIP7_CONCENTRATION_VARIABLES
    | CMIP7_NATURAL_FORCING_VARIABLES
    | CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES
)
"""
Variables required for CMIP-style concentration-driven runs
"""

CMIP7_CO2_ESM_EMISSION_VARIABLES: frozenset[str] = frozenset(
    {"Emissions|CO2|Fossil", "Emissions|CO2|Biosphere"}
)
"""
CO2 emissions variables required for CMIP esm-style runs

Unlike the CO2-only runs, land-use change is on,
so biosphere (AFOLU) CO2 emissions are needed too.
"""

CMIP7_ESM_VARIABLES: frozenset[str] = (
    CMIP7_CO2_ESM_EMISSION_VARIABLES
    | (CMIP7_CONCENTRATION_VARIABLES - CMIP7_CO2_CONCENTRATION_VARIABLES)
    | CMIP7_NATURAL_FORCING_VARIABLES
    | CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES
)
"""
Variables required for CMIP esm-style runs (emission-driven CO2)
"""

CMIP7_GHG_EMISSION_VARIABLES: frozenset[str] = (
    CMIP7_CO2_ESM_EMISSION_VARIABLES
    | frozenset(
        f"Emissions|{v.removeprefix('Atmospheric Concentrations|')}"
        for v in CMIP7_CONCENTRATION_VARIABLES - CMIP7_CO2_CONCENTRATION_VARIABLES
    )
)
"""
GHG emissions variables required for CMIP esm-allGHG-style runs

Emissions of every species in [CMIP7_CONCENTRATION_VARIABLES][(m).]
(with CO2 split into fossil and biosphere,
as in [CMIP7_CO2_ESM_EMISSION_VARIABLES][(m).]).

The emissions of halogenated species are totals,
i.e. they include natural emissions (e.g. of CH3Cl and CH3Br).
"""

CMIP7_ESM_ALL_GHG_VARIABLES: frozenset[str] = (
    CMIP7_GHG_EMISSION_VARIABLES
    | CMIP7_NATURAL_FORCING_VARIABLES
    | CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES
)
"""
Variables required for CMIP esm-allGHG-style runs (emission-driven GHGs)
"""

CMIP7PreIndustrialBranchCO2Concentrations: TypeAlias = pd.DataFrame
"""
CO2 concentrations for a run branching off the CMIP7 pre-industrial state

[verify_cmip7_pre_industrial_branch_co2_concentrations][(m).] defines the shape.
"""


def verify_cmip7_pre_industrial_branch_co2_concentrations(
    co2_concentrations: tuple[CMIP7PreIndustrialBranchCO2Concentrations, ...],
) -> None:
    """
    Verify inputs for CO2-concentration-driven runs from CMIP7 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    co2_concentrations
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        co2_concentrations,
        input_name="CMIP7PreIndustrialBranchCO2Concentrations",
        required_variables=CMIP7_CO2_CONCENTRATION_VARIABLES,
        first_year=CMIP7_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP6PreIndustrialBranchCO2Concentrations: TypeAlias = pd.DataFrame
"""
CO2 concentrations for a run branching off the CMIP6 pre-industrial state

[verify_cmip6_pre_industrial_branch_co2_concentrations][(m).] defines the shape.
"""


def verify_cmip6_pre_industrial_branch_co2_concentrations(
    co2_concentrations: tuple[CMIP6PreIndustrialBranchCO2Concentrations, ...],
) -> None:
    """
    Verify inputs for CO2-concentration-driven runs from CMIP6 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    co2_concentrations
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        co2_concentrations,
        input_name="CMIP6PreIndustrialBranchCO2Concentrations",
        required_variables=CMIP7_CO2_CONCENTRATION_VARIABLES,
        first_year=CMIP6_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP7PreIndustrialBranchConcentrationDrivenInput: TypeAlias = pd.DataFrame
"""
Concentrations for a run branching off the CMIP7 pre-industrial state

[verify_cmip7_pre_industrial_branch_concentrations][(m).] defines the shape.
"""


def verify_cmip7_pre_industrial_branch_concentrations(
    concentrations: tuple[CMIP7PreIndustrialBranchConcentrationDrivenInput, ...],
) -> None:
    """
    Verify inputs for CMIP-style concentration-driven runs from CMIP7 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    concentrations
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        concentrations,
        input_name="CMIP7PreIndustrialBranchConcentrationDrivenInput",
        required_variables=CMIP7_CONCENTRATION_DRIVEN_VARIABLES,
        first_year=CMIP7_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP6PreIndustrialBranchConcentrationDrivenInput: TypeAlias = pd.DataFrame
"""
CMIP-style concentrations for a run branching off the CMIP6 pre-industrial state

[verify_cmip6_pre_industrial_branch_concentrations][(m).] defines the shape.
"""


def verify_cmip6_pre_industrial_branch_concentrations(
    concentrations: tuple[CMIP6PreIndustrialBranchConcentrationDrivenInput, ...],
) -> None:
    """
    Verify inputs for CMIP-style concentration-driven runs from CMIP6 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    concentrations
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        concentrations,
        input_name="CMIP6PreIndustrialBranchConcentrationDrivenInput",
        # CMIP6 and CMIP7 have the same input set
        required_variables=CMIP7_CONCENTRATION_DRIVEN_VARIABLES,
        first_year=CMIP6_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP7PreIndustrialBranchCO2Emissions: TypeAlias = pd.DataFrame
"""
CO2 emissions for a run branching off the CMIP7 pre-industrial state

[verify_cmip7_pre_industrial_branch_co2_emissions][(m).] defines the shape.
"""


def verify_cmip7_pre_industrial_branch_co2_emissions(
    co2_emissions: tuple[CMIP7PreIndustrialBranchCO2Emissions, ...],
) -> None:
    """
    Verify inputs for CO2-emission-driven runs from CMIP7 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    co2_emissions
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        co2_emissions,
        input_name="CMIP7PreIndustrialBranchCO2Emissions",
        required_variables=CMIP7_CO2_EMISSION_VARIABLES,
        first_year=CMIP7_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP6PreIndustrialBranchCO2Emissions: TypeAlias = pd.DataFrame
"""
CO2 emissions for a run branching off the CMIP6 pre-industrial state

[verify_cmip6_pre_industrial_branch_co2_emissions][(m).] defines the shape.
"""


def verify_cmip6_pre_industrial_branch_co2_emissions(
    co2_emissions: tuple[CMIP6PreIndustrialBranchCO2Emissions, ...],
) -> None:
    """
    Verify inputs for CO2-emission-driven runs from CMIP6 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    co2_emissions
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        co2_emissions,
        input_name="CMIP6PreIndustrialBranchCO2Emissions",
        required_variables=CMIP7_CO2_EMISSION_VARIABLES,
        first_year=CMIP6_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP7PreIndustrialBranchESMInput: TypeAlias = pd.DataFrame
"""
Input for a CMIP esm-style run branching off the CMIP7 pre-industrial state

[verify_cmip7_pre_industrial_branch_esm_inputs][(m).] defines the shape.
"""


def verify_cmip7_pre_industrial_branch_esm_inputs(
    esm_inputs: tuple[CMIP7PreIndustrialBranchESMInput, ...],
) -> None:
    """
    Verify inputs for CMIP esm-style runs from CMIP7 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    esm_inputs
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        esm_inputs,
        input_name="CMIP7PreIndustrialBranchESMInput",
        required_variables=CMIP7_ESM_VARIABLES,
        first_year=CMIP7_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP7PreIndustrialBranchESMAllGHGInput: TypeAlias = pd.DataFrame
"""
Input for a CMIP esm-allGHG-style run branching off the CMIP7 pre-industrial state

[verify_cmip7_pre_industrial_branch_esm_all_ghg_inputs][(m).] defines the shape.
"""


def verify_cmip7_pre_industrial_branch_esm_all_ghg_inputs(
    esm_all_ghg_inputs: tuple[CMIP7PreIndustrialBranchESMAllGHGInput, ...],
) -> None:
    """
    Verify inputs for CMIP esm-allGHG-style runs from CMIP7 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    esm_all_ghg_inputs
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        esm_all_ghg_inputs,
        input_name="CMIP7PreIndustrialBranchESMAllGHGInput",
        required_variables=CMIP7_ESM_ALL_GHG_VARIABLES,
        first_year=CMIP7_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP6PreIndustrialBranchESMInput: TypeAlias = pd.DataFrame
"""
Input for a CMIP esm-style run branching off the CMIP6 pre-industrial state

[verify_cmip6_pre_industrial_branch_esm_inputs][(m).] defines the shape.
"""


def verify_cmip6_pre_industrial_branch_esm_inputs(
    esm_inputs: tuple[CMIP6PreIndustrialBranchESMInput, ...],
) -> None:
    """
    Verify inputs for CMIP esm-style runs from CMIP6 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    esm_inputs
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        esm_inputs,
        input_name="CMIP6PreIndustrialBranchESMInput",
        required_variables=CMIP7_ESM_VARIABLES,
        first_year=CMIP6_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )


CMIP6PreIndustrialBranchESMAllGHGInput: TypeAlias = pd.DataFrame
"""
Input for a CMIP esm-allGHG-style run branching off the CMIP6 pre-industrial state

[verify_cmip6_pre_industrial_branch_esm_all_ghg_inputs][(m).] defines the shape.
"""


def verify_cmip6_pre_industrial_branch_esm_all_ghg_inputs(
    esm_all_ghg_inputs: tuple[CMIP6PreIndustrialBranchESMAllGHGInput, ...],
) -> None:
    """
    Verify inputs for CMIP esm-allGHG-style runs from CMIP6 pre-industrial

    There is deliberately no harmonisation check:
    the inputs don't have to start from the piControl state,
    so you can run abrupt-change experiments (e.g. abrupt-4xCO2).

    Parameters
    ----------
    esm_all_ghg_inputs
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    verify_wide_timeseries_inputs(
        esm_all_ghg_inputs,
        input_name="CMIP6PreIndustrialBranchESMAllGHGInput",
        required_variables=CMIP7_ESM_ALL_GHG_VARIABLES,
        first_year=CMIP6_PRE_INDUSTRIAL_BRANCH_YEAR,
        last_year_at_most=None,
    )
