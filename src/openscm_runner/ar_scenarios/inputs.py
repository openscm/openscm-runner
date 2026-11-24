"""
Input definitions
"""

from __future__ import annotations

from typing import TypeAlias

import pandas as pd

from openscm_runner.verification import verify_wide_timeseries_inputs

AR6_SCENARIO_EMISSIONS_VARIABLES: frozenset[str] = frozenset(
    {
        "Emissions|CO2|Biosphere",
        "Emissions|CO2|Fossil",
        "Emissions|BC",
        "Emissions|CH4",
        "Emissions|CO",
        "Emissions|N2O",
        "Emissions|NH3",
        "Emissions|NMVOC",
        "Emissions|NOx",
        "Emissions|OC",
        "Emissions|SOx",
        "Emissions|C2F6",
        "Emissions|C6F14",
        "Emissions|CF4",
        "Emissions|SF6",
        "Emissions|HFC125",
        "Emissions|HFC134a",
        "Emissions|HFC143a",
        "Emissions|HFC227ea",
        "Emissions|HFC23",
        "Emissions|HFC245fa",
        "Emissions|HFC32",
        "Emissions|HFC4310mee",
        "Emissions|CCl4",
        "Emissions|CFC11",
        "Emissions|CFC113",
        "Emissions|CFC114",
        "Emissions|CFC115",
        "Emissions|CFC12",
        "Emissions|CH3CCl3",
        "Emissions|HCFC141b",
        "Emissions|HCFC142b",
        "Emissions|HCFC22",
        "Emissions|Halon1202",
        "Emissions|Halon1211",
        "Emissions|Halon1301",
        "Emissions|Halon2402",
        "Emissions|C3F8",
        "Emissions|C4F10",
        "Emissions|C5F12",
        "Emissions|C7F16",
        "Emissions|C8F18",
        "Emissions|cC4F8",
        "Emissions|SO2F2",
        "Emissions|HFC236fa",
        "Emissions|HFC152a",
        "Emissions|HFC365mfc",
        "Emissions|CH2Cl2",
        "Emissions|CHCl3",
        "Emissions|CH3Br",
        "Emissions|CH3Cl",
        "Emissions|NF3",
    }
)
"""
The 52 emissions species required for AR6 scenarios

This includes Halon1202 because AR6 scenario data includes it
(even though values were all zero),
so AR6 scenarios can be used as they are.

Note on HFC245: everything we use calls this species HFC245fa:
gcages, CMIP7 ScenarioMIP reporting, CMIP GHG concentrations,
and Velders et al.'s HFC scenarios (e.g. Velders et al., ACP, 2022,
https://doi.org/10.5194/acp-22-6087-2022), which project HFC-245fa, never HFC-245ca.
The AR6 WG3 IAM reporting template used `Emissions|HFC|HFC245ca`.
This looks like a labelling error: IAMs aren't modelling HFC-245ca.
gcages renames it to HFC245fa
(see `gcages/databases/emissions_variables.csv`, `ar6_wg3` column).
As far as we can tell, only the AR6 WG3 workflow had this naming error
(and it was fixed in pre-processing anyway).
"""

AR7_SCENARIO_EMISSIONS_VARIABLES = AR6_SCENARIO_EMISSIONS_VARIABLES - {
    "Emissions|Halon1202"
}
"""
The 51 emissions species required for AR7 scenarios

/// note | Halon1202
Halon1202 is excluded because it is absent from CMIP GHG concentration datasets,
was all zero in all AR6 scenarios and has negligible ERF (about 1e-6 W/m^2).
///
"""

AR6_SCENARIO_CO2_EMISSIONS_VARIABLES: frozenset[str] = frozenset(
    {"Emissions|CO2|Fossil", "Emissions|CO2|Biosphere"}
)
"""
CO2 emissions variables of an AR6 scenario

The input for runs with CO2 forcing only.
Whether these runs should take fossil CO2 emissions only,
or both fossil and biosphere CO2 emissions, is still to be decided
(decision [B17][b17]).
"""

AR7Scenario: TypeAlias = pd.DataFrame
"""
An emissions scenario defined in AR7 terms

[verify_ar7_scenarios][(m).] defines the shape.
"""


def verify_ar7_scenarios(ar7_scenarios: tuple[AR7Scenario, ...]) -> None:
    """
    Verify that inputs are valid AR7 scenarios

    Parameters
    ----------
    ar7_scenarios
        Inputs to verify (each one is exactly one scenario)

    Raises
    ------
    InvalidInputError
        An input is not a valid AR7 scenario
    """
    verify_wide_timeseries_inputs(
        ar7_scenarios,
        input_name="AR7Scenario",
        required_variables=AR7_SCENARIO_EMISSIONS_VARIABLES,
        first_year=2023,
        # A cap for now, it could be lifted later
        last_year_at_most=2500,
    )
    # Harmonisation to AR7 history isn't checked yet (roadmap W05)


AR6Scenario: TypeAlias = pd.DataFrame
"""
An emissions scenario defined in AR6 terms

[verify_ar6_scenarios][(m).] defines the shape.
"""


def verify_ar6_scenarios(ar6_scenarios: tuple[AR6Scenario, ...]) -> None:
    """
    Verify that inputs are valid AR6 scenarios

    Parameters
    ----------
    ar6_scenarios
        Inputs to verify (each one is exactly one scenario)

    Raises
    ------
    InvalidInputError
        An input is not a valid AR6 scenario
    """
    verify_wide_timeseries_inputs(
        ar6_scenarios,
        input_name="AR6Scenario",
        required_variables=AR6_SCENARIO_EMISSIONS_VARIABLES,
        first_year=2015,
        # No cap on the last year
        last_year_at_most=None,
    )
    # Harmonisation to AR6 history isn't checked yet (roadmap W05)


AR6ScenarioCO2Emissions: TypeAlias = pd.DataFrame
"""
The CO2 emissions of an emissions scenario defined in AR6 terms

[verify_ar6_scenario_co2_emissions][(m).] defines the shape.

/// note | Details still being worked out
Which CO2 emissions these runs take (decision [B17][b17])
and which feedbacks they include (decision [B16][b16]) are still to be decided,
so this definition may change.
///
"""


def verify_ar6_scenario_co2_emissions(
    ar6_co2_emissions: tuple[AR6ScenarioCO2Emissions, ...],
) -> None:
    """
    Verify that inputs are valid AR6 scenario CO2 emissions

    /// note | Details still being worked out
    Which CO2 emissions these runs take (decision [B17][b17])
    and which feedbacks they include (decision [B16][b16]) are still to be decided,
    so this definition may change.
    ///

    Parameters
    ----------
    ar6_co2_emissions
        Inputs to verify (each one is exactly one scenario)

    Raises
    ------
    InvalidInputError
        An input is not valid AR6 scenario CO2 emissions
    """
    verify_wide_timeseries_inputs(
        ar6_co2_emissions,
        input_name="AR6ScenarioCO2Emissions",
        required_variables=AR6_SCENARIO_CO2_EMISSIONS_VARIABLES,
        first_year=2015,
        # No cap on the last year
        last_year_at_most=None,
    )
    # Harmonisation to AR6 history isn't checked yet (roadmap W05)
