"""
Input definitions
"""

from __future__ import annotations

from typing import TypeAlias

import pandas as pd

from openscm_runner.verification import verify_wide_timeseries_inputs

CO2_CONCENTRATION_VARIABLES: frozenset[str] = frozenset(
    {"Atmospheric Concentrations|CO2"}
)
"""Variables required for CO2-concentration-driven runs"""

CO2_EMISSION_VARIABLES: frozenset[str] = frozenset({"Emissions|CO2|Fossil"})
"""
Variables required for CO2-emission-driven runs

Fossil CO2 emissions only:
biosphere CO2 emissions are off in the CO2-only experiments
(there is no land-use change).
`Emissions|CO2|Fossil` is the canonical input name, including for idealised
runs such as esm-flat10 where the source data has no fossil/biosphere split.
"""
# TODO: roadmap item cross-ref re naming and setup

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

CMIP_NATURAL_FORCING_VARIABLES: frozenset[str] = frozenset(
    {
        "Effective Radiative Forcing|Solar",
        "Effective Radiative Forcing|Volcanic",
    }
)
"""
Natural forcing variables required for CMIP-style concentration-driven runs

Experiments like historical prescribe solar and volcanic forcing too,
so they can be part of the input.

!!! warning "What zero natural forcing means still has to be decided"

    E.g. RCMIP phase 3's natural ERF isn't zero in 1850
    (e.g. volcanic 0.18 (CMIP6) or 0.21 (CMIP7) W/m^2),
    and CMIP's piControl uses averages
    (e.g. of solar over a solar cycle, of volcanic over the historical period).
    So "relative to piControl" needs to be defined (decision B19).

TODO: decide whether the input should be ERF (as here)
or something closer to what CMIP provides,
and whether adapters may scale it.
TODO: units are not checked yet (W/m^2 is assumed).
TODO: roadmap items for the above
"""

# TODO: rename to CMIP_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES
CMIP_AEROSOL_EMISSIONS_VARIABLES: frozenset[str] = frozenset(
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

# TODO: fix up naming throughout.
# All of these constants should probably be CMIP7*,
# which we can then just use for CMIP6 definitions too
# rather than claiming
# that there is one CMIP definition which will apply for all projects.
CMIP_CONCENTRATION_DRIVEN_VARIABLES: frozenset[str] = (
    CMIP7_CONCENTRATION_VARIABLES
    | CMIP_NATURAL_FORCING_VARIABLES
    | CMIP_AEROSOL_EMISSIONS_VARIABLES
)
"""
Variables required for CMIP-style concentration-driven runs
"""

CO2_ESM_EMISSION_VARIABLES: frozenset[str] = frozenset(
    {"Emissions|CO2|Fossil", "Emissions|CO2|Biosphere"}
)
"""
CO2 emissions variables required for CMIP esm-style runs

Unlike the CO2-only runs, land-use change is on,
so biosphere (AFOLU) CO2 emissions are needed too.
"""

CMIP_ESM_VARIABLES: frozenset[str] = (
    CO2_ESM_EMISSION_VARIABLES
    | (CMIP7_CONCENTRATION_VARIABLES - CO2_CONCENTRATION_VARIABLES)
    | CMIP_NATURAL_FORCING_VARIABLES
    | CMIP_AEROSOL_EMISSIONS_VARIABLES
)
"""
Variables required for CMIP esm-style runs (emission-driven CO2)
"""

CMIP_GHG_EMISSION_VARIABLES: frozenset[str] = CO2_ESM_EMISSION_VARIABLES | frozenset(
    f"Emissions|{v.removeprefix('Atmospheric Concentrations|')}"
    for v in CMIP7_CONCENTRATION_VARIABLES - CO2_CONCENTRATION_VARIABLES
)
"""
GHG emissions variables required for CMIP esm-allGHG-style runs

Emissions of every species in [CMIP7_CONCENTRATION_VARIABLES][(m).]
(with CO2 split into fossil and biosphere, as in [CO2_ESM_EMISSION_VARIABLES][(m).]).

The emissions of halogenated species are totals,
i.e. they include natural emissions (e.g. of CH3Cl and CH3Br).
"""

CMIP_ESM_ALL_GHG_VARIABLES: frozenset[str] = (
    CMIP_GHG_EMISSION_VARIABLES
    | CMIP_NATURAL_FORCING_VARIABLES
    | CMIP_AEROSOL_EMISSIONS_VARIABLES
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
        required_variables=CO2_CONCENTRATION_VARIABLES,
        first_year=1850,
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
        required_variables=CO2_CONCENTRATION_VARIABLES,
        # TODO: bring pre-industrial branch year back as
        # CMIP7_PRE_INDUSTRIAL_BRANCH_YEAR
        first_year=1850,
        last_year_at_most=None,
    )


# TODO: rename to CMIP7PreIndustrialBranchConcentrationDrivenInputs
CMIP7PreIndustrialBranchConcentrations: TypeAlias = pd.DataFrame
"""
Concentrations for a run branching off the CMIP7 pre-industrial state

[verify_cmip7_pre_industrial_branch_concentrations][(m).] defines the shape.
"""


def verify_cmip7_pre_industrial_branch_concentrations(
    concentrations: tuple[CMIP7PreIndustrialBranchConcentrations, ...],
) -> None:
    """
    Verify inputs for CMIP-style concentration-driven runs from CMIP7 pre-industrial

    Parameters
    ----------
    concentrations
        Inputs to verify (each one is exactly one experiment)

    Raises
    ------
    InvalidInputError
        An input doesn't match the definition
    """
    # TODO: add note throughout that there is deliberately no harmonisation check
    # so people can perform abrupt change experiments
    verify_wide_timeseries_inputs(
        concentrations,
        input_name="CMIP7PreIndustrialBranchConcentrations",
        required_variables=CMIP_CONCENTRATION_DRIVEN_VARIABLES,
        first_year=1850,
        last_year_at_most=None,
    )


CMIP6PreIndustrialBranchConcentrations: TypeAlias = pd.DataFrame
"""
CMIP-style concentrations for a run branching off the CMIP6 pre-industrial state

[verify_cmip6_pre_industrial_branch_concentrations][(m).] defines the shape.
"""


def verify_cmip6_pre_industrial_branch_concentrations(
    concentrations: tuple[CMIP6PreIndustrialBranchConcentrations, ...],
) -> None:
    """
    Verify inputs for CMIP-style concentration-driven runs from CMIP6 pre-industrial

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
        input_name="CMIP6PreIndustrialBranchConcentrations",
        # CMIP6 and CMIP7 have the same input set
        required_variables=CMIP_CONCENTRATION_DRIVEN_VARIABLES,
        first_year=1850,
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
        required_variables=CO2_EMISSION_VARIABLES,
        first_year=1850,
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
        required_variables=CO2_EMISSION_VARIABLES,
        first_year=1850,
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
        required_variables=CMIP_ESM_VARIABLES,
        first_year=1850,
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
        required_variables=CMIP_ESM_ALL_GHG_VARIABLES,
        first_year=1850,
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
        required_variables=CMIP_ESM_VARIABLES,
        first_year=1850,
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
        required_variables=CMIP_ESM_ALL_GHG_VARIABLES,
        first_year=1850,
        last_year_at_most=None,
    )
