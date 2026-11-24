"""
MAGICC AR6 adapters for assessment report (AR, e.g. AR6, AR7) scenarios
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import pandas as pd

from openscm_runner.ar_scenarios import (
    AdapterAR6Scenario,
    AdapterAR6ScenarioAnthropogenicOnly,
    AdapterAR6ScenarioCO2ForcingOnly,
    AdapterAR7Scenario,
    AR6Scenario,
    AR6ScenarioCO2Emissions,
    AR7Scenario,
    verify_ar6_scenario_co2_emissions,
    verify_ar6_scenarios,
)
from openscm_runner.output import OpenSCMRunnerOutput
from openscm_runner.output_specs import OutputSpecs

from .base import (
    END_YEAR_BUFFER,
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6Experiment,
    get_experiment_levels,
    hold_last_value,
    run_experiments,
)
from .io import (
    FILE_HEADER,
    format_conc_in,
    format_held_tabular_file,
    format_scen7,
    read_namelist,
    read_tabular_file,
)
from .naming import (
    EMISSIONS_VARIABLES,
    FGAS_NAMES,
    MHALO_NAMES,
    OUTPUT_VARIABLES,
    get_output_variables,
    to_magicc_emissions,
)
from .running import NO_EXTRA_SCENARIO_FILES, MAGICCInstallation

AR6_START_YEAR = 1750
"""
Year in which runs have to start to match the AR6 configuration
"""

AR6_SUPPORTED_OUTPUT_VARIABLES: tuple[str, ...] = tuple(OUTPUT_VARIABLES)
"""Outputs the AR6 scenario adapter can provide"""

AR6_ANTHROPOGENIC_ONLY_SUPPORTED_OUTPUT_VARIABLES: tuple[str, ...] = tuple(
    v
    for v in OUTPUT_VARIABLES
    if v
    not in ("Effective Radiative Forcing|Solar", "Effective Radiative Forcing|Volcanic")
)
"""
Outputs the AR6 anthropogenic-only adapter can provide

MAGICC still reports the solar and volcanic forcing it would have applied,
so we don't offer these (they aren't part of the run).
"""

AR6_CO2_FORCING_ONLY_SUPPORTED_OUTPUT_VARIABLES: tuple[str, ...] = tuple(
    v
    for v in OUTPUT_VARIABLES
    if not v.startswith("Effective Radiative Forcing|")
    or v == "Effective Radiative Forcing|CO2"
)
"""
Outputs the AR6 CO2-forcing-only adapter can provide

MAGICC still reports every forcing it would have applied,
so we only offer the total and CO2 forcing (the only ones which are part of the run).
"""

SCENARIO_FILE = "OPENSCM_RUNNER_EMMS.SCEN7"
"""
Name of the scenario file we write

Name doesn't matter, it's just so the runner has a common value.
"""


class MAGICCAR6AdapterAR7Scenario:
    """
    MAGICC adapter for AR7 scenarios

    For experiment details, see
    [AdapterAR7Scenario][openscm_runner.ar_scenarios.running.].

    Not implemented, and we don't plan to implement it:
    this setup relies on AR6's history,
    so running AR7 scenarios would mean joining AR6 history and AR7 scenarios,
    which won't match what anyone else does.
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset()
    """Output variables this adapter can provide"""

    def __call__(
        self,
        ar7_scenarios: tuple[AR7Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments (not implemented)"""
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterAR6Scenario:
    """
    MAGICC AR6 adapter for AR6 scenarios

    For experiment details, see
    [AdapterAR6Scenario][openscm_runner.ar_scenarios.running.].

    Differences from AR6 WG3 that we know of:

    - how we work around MAGICC v7.5.3's last year bug
      (which halves emissions in the last year):
      we hold the last year of the input constant for
      [END_YEAR_BUFFER][openscm_runner.adapters.magicc_ar6.base.] years,
      AR6 WG3 ran to MAGICC's default end year (2105)
      without holding the input (its scenarios ended in 2100).
      This makes no difference up to 2100
      (the full-ensemble acceptance test reproduces
      AR6's published temperatures, 2100 included).

    /// note | Where MAGICC averages emissions over each year and the next
    MAGICC v7.5.3's convention is that the emissions in year `t`
    are the total for year `t`,
    and the state at the start of year `t + 1` is calculated
    from the state at the start of year `t` and the emissions in year `t`
    (`src/MAGICC7.f90`, v7.5.3, around line 127).
    The gas cycles, tropospheric ozone and nitrate
    use each year's emissions as given.

    The exception is the aerosol forcing and optical thickness MAGICC derives
    from emissions (direct aerosol, BC on snow
    and, via the optical thicknesses, aerosol-cloud forcing).
    These are start-of-year values calculated from the average of the emissions
    in year `t` and year `t + 1`
    (`extend_rf_box_from_switchyear_with_emissions` in MAGICC v7.5.3),
    so for these a step change in emissions in year `y`
    is half applied in year `y - 1`.

    These adapters don't do anything about this:
    we pass the emissions on as given,
    because that is the behaviour MAGICC v7.5.3 has always had.
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        AR6_SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        ar6_scenarios: tuple[AR6Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_ar6_scenarios(ar6_scenarios)

        experiments = make_ar6_scenario_experiments(
            ar6_scenarios,
            output_variables=get_output_variables(
                output_specs.output_variables, AR6_SUPPORTED_OUTPUT_VARIABLES
            ),
        )

        return run_experiments(experiments, configuration=self.configuration)


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly:
    """
    MAGICC AR6 adapter for AR6 scenarios with anthropogenic forcing only

    For experiment details, see
    [AdapterAR6ScenarioAnthropogenicOnly][openscm_runner.ar_scenarios.running.].

    As for [MAGICCAR6AdapterAR6Scenario][(m).],
    with `RF_TOTAL_RUNMODUS = "ANTHROPOGENIC"`.
    The outputs don't include solar and volcanic forcing
    ([AR6_ANTHROPOGENIC_ONLY_SUPPORTED_OUTPUT_VARIABLES][(m).]).
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        AR6_ANTHROPOGENIC_ONLY_SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        ar6_scenarios: tuple[AR6Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_ar6_scenarios(ar6_scenarios)

        experiments = make_ar6_scenario_experiments(
            ar6_scenarios,
            output_variables=get_output_variables(
                output_specs.output_variables,
                AR6_ANTHROPOGENIC_ONLY_SUPPORTED_OUTPUT_VARIABLES,
            ),
            rf_total_runmodus="ANTHROPOGENIC",
        )

        return run_experiments(experiments, configuration=self.configuration)


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly:
    """
    MAGICC AR6 adapter for AR6 scenarios with CO2 forcing only

    For experiment details, see
    [AdapterAR6ScenarioCO2ForcingOnly][openscm_runner.ar_scenarios.running.].

    As for [MAGICCAR6AdapterAR6Scenario][(m).],
    with `RF_TOTAL_RUNMODUS = "CO2"`.
    The only forcing outputs are the total and CO2 forcing
    ([AR6_CO2_FORCING_ONLY_SUPPORTED_OUTPUT_VARIABLES][(m).]).

    /// warning | Everything except CO2 is held at pre-industrial (1750)
    Everything else is held at its pre-industrial (1750) state
    for the whole run, history included:
    every gas except CO2 is concentration-driven for the whole run,
    with its concentrations held at their 1750 values
    (see [make_pi_control_non_co2_history][(m).]).
    The CO2 history (concentrations to 2014, fossil and biosphere emissions)
    is MAGICC's usual history.

    MAGICC adds the CO2 from the oxidation of fossil CH4
    to the fossil CO2 emissions
    (even if CH4 is concentration-driven).
    Fossil CH4 emissions are zero for the whole run (history included),
    so there is no CO2 from the oxidation of the scenario's
    (or history's) CH4 at any point in the run.
    The exception is CH4 from thawing permafrost
    (MAGICC's permafrost feedback, which is on in the AR6 distribution):
    MAGICC counts its oxidation as CO2 too.
    This is a response to warming, not part of the input,
    and it's small: for the test scenario
    (fossil CO2 emissions of 6-12 GtC/yr this century),
    it is zero until the permafrost starts thawing (1950-2000,
    depending on the ensemble member) and 0.002-0.024 GtC/yr in 2100,
    compared to 0.10-0.13 GtC/yr from all CH4 oxidation in the full run.
    We keep it: it's part of the permafrost feedback, not the input.

    If we change our minds, add `"pf_co2fromch4oxinatm_fraction": 0.0`
    to the settings in [make_pi_control_non_co2_history][(m).].
    That setting is the fraction of the permafrost CH4
    which MAGICC counts as oxidising to CO2
    (default 1, it isn't part of the AR6 calibration).
    With it at zero, the fossil fraction of the CH4 in the atmosphere is zero
    (so there is no CO2 from CH4 oxidation at all),
    while the rest of the permafrost feedback (its CO2 emissions) stays on.
    Don't use `PF_APPLY = 0` (that turns off the whole permafrost feedback)
    or `CH4_INCL_CH4OX = 0` (that would work too,
    but we'd rather not rely on a switch).
    Whether CO2-forcing-only runs should include this CO2
    is something we need to clarify (see decision [B16][b16]).

    MAGICC's other history files (e.g. aerosol and land-use forcing)
    are left as they are: they only affect forcing which isn't part of the run.
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        AR6_CO2_FORCING_ONLY_SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        ar6_co2_emissions: tuple[AR6ScenarioCO2Emissions, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_ar6_scenario_co2_emissions(ar6_co2_emissions)

        experiments = make_ar6_co2_forcing_only_experiments(
            ar6_co2_emissions,
            output_variables=get_output_variables(
                output_specs.output_variables,
                AR6_CO2_FORCING_ONLY_SUPPORTED_OUTPUT_VARIABLES,
            ),
            installation=self.configuration.installation,
        )

        return run_experiments(experiments, configuration=self.configuration)


def with_missing_emissions(
    emissions: pd.DataFrame, fill_values: Mapping[str, float]
) -> pd.DataFrame:
    """
    Add constant emissions for every species MAGICC can be given which is missing

    Parameters
    ----------
    emissions
        Emissions in MAGICC's names and units (`variable` and `unit` index levels)

    fill_values
        Value to use for each missing species (MAGICC's names and units)

    Returns
    -------
    :
        `emissions`, with constant emissions (from `fill_values`)
        for every species in
        [EMISSIONS_VARIABLES][openscm_runner.adapters.magicc_ar6.naming.]
        which isn't in `emissions`

    Raises
    ------
    KeyError
        A missing species isn't in `fill_values`
    """
    given = set(emissions.index.get_level_values("variable"))
    missing = [spec for spec in EMISSIONS_VARIABLES.values() if spec.gas not in given]
    if not missing:
        return emissions

    filled = pd.DataFrame(
        [[fill_values[spec.gas]] * emissions.shape[1] for spec in missing],
        index=pd.MultiIndex.from_tuples(
            [(spec.gas, spec.magicc_unit) for spec in missing],
            names=["variable", "unit"],
        ),
        columns=emissions.columns,
    )

    return pd.concat([emissions, filled])


NON_CO2_GAS_GROUPS: tuple[str, ...] = ("ch4", "n2o", "fgas", "mhalo")
"""MAGICC's gas groups other than CO2"""


def make_pi_control_non_co2_history(
    installation: MAGICCInstallation, *, end_year: int
) -> tuple[dict[str, str], dict[str, Any]]:
    """
    Make files and settings which hold everything except CO2 at pre-industrial (1750)

    For the CO2-forcing-only runs (see the adapter's docstring).
    Every gas except CO2 is concentration-driven for the whole run,
    with its concentrations held at their value in [AR6_START_YEAR][(m).] (1750).
    So their emissions don't matter,
    except fossil CH4's: MAGICC adds the CO2 from its oxidation
    to the fossil CO2 emissions
    (even if CH4 is concentration-driven:
    it is the fossil fraction of the CH4 in the atmosphere times the CH4 sink).
    So fossil CH4 emissions are zero for the whole run (history included).

    Parameters
    ----------
    installation
        MAGICC installation (the source of the history files)

    end_year
        Last year of the run

    Returns
    -------
    files :
        File name to contents

    settings :
        Settings which point MAGICC at the files
        (and keep every gas except CO2 concentration-driven)
    """
    defaults = read_namelist(installation.run_dir / "MAGCFG_DEFAULTALL.CFG")[
        "nml_allcfgs"
    ]

    files: dict[str, str] = {}

    def held(filename: str, *, value: float | None = None, to_end: bool) -> str:
        data, specifications = read_tabular_file(installation.run_dir / filename)
        values = (
            data[AR6_START_YEAR]
            if value is None
            else pd.Series(value, index=data.index)
        )
        last_year = max(int(data.columns.max()), end_year) if to_end else None
        name = f"OPENSCM_RUNNER_PI_{filename}"
        files[name] = format_held_tabular_file(
            values,
            years=(
                data.columns
                if last_year is None
                else range(int(data.columns.min()), last_year + 1)
            ),
            specifications=specifications,
            header=f"{FILE_HEADER} ({filename} held at {AR6_START_YEAR} values)",
        )

        return name

    def held_conc(gas: str, filename: str) -> str:
        if filename:
            return held(filename, to_end=True)

        # MAGICC has no concentration file for some gases (e.g. Halon1202).
        # It would use zero for these, which is also their 1750 value,
        # but we write the zeros explicitly rather than rely on MAGICC's internals.
        name = f"OPENSCM_RUNNER_PI_{gas}_CONC.IN"
        files[name] = format_conc_in(
            gas, pd.Series(0.0, index=range(AR6_START_YEAR, end_year + 1))
        )

        return name

    settings: dict[str, Any] = {
        # Concentration-driven for the whole run
        **{
            f"{group}_switchfromconc2emis_year": end_year + 1
            for group in NON_CO2_GAS_GROUPS
        },
        "file_ch4_conc": held(defaults["file_ch4_conc"], to_end=True),
        "file_n2o_conc": held(defaults["file_n2o_conc"], to_end=True),
        # MAGICC matches these to gases by position,
        # in the order of its own `FGAS_NAMES` and `MHALO_NAMES`
        "fgas_files_conc": [
            held_conc(gas, f)
            for gas, f in zip(FGAS_NAMES, defaults["fgas_files_conc"], strict=True)
        ],
        "mhalo_files_conc": [
            held_conc(gas, f)
            for gas, f in zip(MHALO_NAMES, defaults["mhalo_files_conc"], strict=True)
        ],
        # No fossil CH4, so no CO2 from its oxidation
        "file_ch4i_emis": held(defaults["file_ch4i_emis"], value=0.0, to_end=False),
    }

    return files, settings


def make_ar6_scenario_experiments(
    ar6_scenarios: tuple[AR6Scenario, ...] | tuple[AR6ScenarioCO2Emissions, ...],
    *,
    output_variables: Mapping[str, str],
    rf_total_runmodus: str = "ALL",
    make_extra_files_and_settings: (
        Callable[[int], tuple[Mapping[str, str], Mapping[str, Any]]] | None
    ) = None,
    missing_emissions: Mapping[str, float] | None = None,
) -> list[MAGICCAR6Experiment]:
    """
    Make the experiments to run AR6 scenarios

    This is the back-end the AR6 scenario adapters share.
    The inputs aren't verified here (that's up to the adapter).

    Parameters
    ----------
    ar6_scenarios
        Scenarios to run (each one is exactly one scenario)

    output_variables
        Output variables to return: our name to MAGICC's name

    rf_total_runmodus
        Which forcing drives the climate (MAGICC's `RF_TOTAL_RUNMODUS`)

    make_extra_files_and_settings
        Function which makes extra files to write into the run directory
        (name to contents) and extra settings
        (applied on top of the ones every AR6 scenario run gets),
        given the last year of the run

    missing_emissions
        Emissions to use for species MAGICC wants which aren't in a scenario
        (MAGICC's names and units, held constant).
        If `None`, every species has to be in the scenarios.

    Returns
    -------
    :
        One experiment per scenario, in the same order as `ar6_scenarios`
    """
    experiments = []
    for scenario in ar6_scenarios:
        emissions = with_missing_emissions(
            to_magicc_emissions(scenario), missing_emissions or {}
        )
        last_year = int(emissions.columns.max())
        end_year = last_year + END_YEAR_BUFFER
        extra_files, extra_settings = (
            ({}, {})
            if make_extra_files_and_settings is None
            else make_extra_files_and_settings(end_year)
        )
        experiments.append(
            MAGICCAR6Experiment(
                files={
                    **extra_files,
                    SCENARIO_FILE: format_scen7(
                        hold_last_value(emissions, END_YEAR_BUFFER)
                    ),
                },
                settings={
                    "file_emisscen": SCENARIO_FILE,
                    **NO_EXTRA_SCENARIO_FILES,
                    "rf_total_runmodus": rf_total_runmodus,
                    **extra_settings,
                },
                start_year=AR6_START_YEAR,
                end_year=end_year,
                output_first_year=AR6_START_YEAR,
                output_last_year=last_year,
                output_variables=output_variables,
                experiment_levels=get_experiment_levels(scenario),
            )
        )

    return experiments


def make_ar6_co2_forcing_only_experiments(
    ar6_co2_emissions: tuple[AR6ScenarioCO2Emissions, ...],
    *,
    output_variables: Mapping[str, str],
    installation: MAGICCInstallation,
) -> list[MAGICCAR6Experiment]:
    """
    Make the experiments to run AR6 scenarios with CO2 forcing only

    See [MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly][(m).] for how they are set up.

    Parameters
    ----------
    ar6_co2_emissions
        CO2 emissions of the scenarios to run (each one is exactly one scenario)

    output_variables
        Output variables to return: our name to MAGICC's name

    installation
        MAGICC installation (the source of the history files)

    Returns
    -------
    :
        One experiment per scenario, in the same order as `ar6_co2_emissions`
    """
    return make_ar6_scenario_experiments(
        ar6_co2_emissions,
        output_variables=output_variables,
        rf_total_runmodus="CO2",
        make_extra_files_and_settings=lambda end_year: make_pi_control_non_co2_history(
            installation, end_year=end_year
        ),
        # Every gas except CO2 is concentration-driven,
        # so these emissions don't matter
        # (and fossil CH4 oxidation is off, see `make_pi_control_non_co2_history`)
        missing_emissions=dict.fromkeys(
            (spec.gas for spec in EMISSIONS_VARIABLES.values()), 0.0
        ),
    )


if TYPE_CHECKING:
    # mypy checks that the adapters satisfy their protocols.
    # Nothing in here runs, so nothing is initialised.
    # The functions are just so mypy checks the assignment from one type to the other.
    def _check_ar7(adapter: MAGICCAR6AdapterAR7Scenario) -> AdapterAR7Scenario:
        return adapter

    def _check_ar6(adapter: MAGICCAR6AdapterAR6Scenario) -> AdapterAR6Scenario:
        return adapter

    def _check_ar6_anthropogenic_only(
        adapter: MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
    ) -> AdapterAR6ScenarioAnthropogenicOnly:
        return adapter

    def _check_ar6_co2_forcing_only(
        adapter: MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
    ) -> AdapterAR6ScenarioCO2ForcingOnly:
        return adapter
