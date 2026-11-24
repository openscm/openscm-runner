"""
Adapter protocols and run functions for AR7 and AR6 scenarios
"""
# Developer notes
#
# As well as the full scenarios, there are AR6 variants
# which turn off part of the forcing (anthropogenic-only, CO2-forcing-only).
# The anthropogenic-only variant takes exactly the same input as the full scenarios,
# the CO2-forcing-only variant only takes the scenario's CO2 emissions
# (nothing else would be used).
# They are separate entry points so users have to be explicit about what they run.

from __future__ import annotations

from typing import Protocol

from openscm_runner.output import OpenSCMRunnerOutput, RunResults
from openscm_runner.output_specs import OutputCapabilities, OutputSpecs
from openscm_runner.running import run_adapters

from .inputs import (
    AR6Scenario,
    AR6ScenarioCO2Emissions,
    AR7Scenario,
    verify_ar6_scenario_co2_emissions,
    verify_ar6_scenarios,
    verify_ar7_scenarios,
)


class AdapterAR7Scenario(OutputCapabilities, Protocol):
    """
    Adapter that can run emissions scenarios defined in AR7 terms

    The adapter has to add on AR7's history and use other forcings (e.g. volcanic)
    in line with the standard AR7 choices not supplied by the input.

    Note that the AR7 history and other forcings are not defined yet,
    so you should consider this unstable.
    Whether to keep this experiment until they are defined
    is still to be decided (decision [B23][b23]).
    """

    def __call__(
        self,
        ar7_scenarios: tuple[AR7Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the scenarios

        Parameters
        ----------
        ar7_scenarios
            Scenarios to run (each one is exactly one scenario)

        output_specs
            Outputs to return

            Unsupported requests are recorded as `UnsupportedOutputError` for
            that adapter without calling it. Compatible adapters still run.

        Returns
        -------
        :
            One output per scenario, in the same order as `ar7_scenarios`
        """


class AdapterAR6Scenario(OutputCapabilities, Protocol):
    """
    Adapter that can run emissions scenarios defined in AR6 terms

    The adapter has to add on AR6's history and use other forcings (e.g. volcanic)
    in line with the standard AR6 choices not supplied by the input.
    """

    def __call__(
        self,
        ar6_scenarios: tuple[AR6Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the scenarios

        Parameters
        ----------
        ar6_scenarios
            Scenarios to run (each one is exactly one scenario)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per scenario, in the same order as `ar6_scenarios`
        """


class AdapterAR6ScenarioAnthropogenicOnly(OutputCapabilities, Protocol):
    """
    Adapter that can run AR6 scenarios with anthropogenic forcing only

    As for [AdapterAR6Scenario][(m).]
    (including AR6's history and land-use treatment),
    except that there is no natural (solar and volcanic) forcing
    for the whole run.
    This must be done by turning the natural forcing off,
    not by subtracting a natural-only run from a full run
    (the response isn't linear).
    """

    def __call__(
        self,
        ar6_scenarios: tuple[AR6Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the scenarios, returning one output per scenario, in input order"""


class AdapterAR6ScenarioCO2ForcingOnly(OutputCapabilities, Protocol):
    """
    Adapter that can run AR6 scenarios with CO2 forcing only

    As for [AdapterAR6Scenario][(m).] (including AR6's history),
    except that the only forcing is CO2's for the whole run.
    Non-CO2 forcing and land-use (albedo) forcing are absent.
    The carbon cycle sees all the CO2 emissions
    (fossil and biosphere).

    The input is only the scenario's CO2 emissions.
    So any CO2 from the oxidation of (fossil) CH4 in the scenario isn't included
    (see decision [B16][b16]).
    """

    def __call__(
        self,
        ar6_co2_emissions: tuple[AR6ScenarioCO2Emissions, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the scenarios, returning one output per scenario, in input order"""


def run_ar7_scenarios(
    ar7_scenarios: tuple[AR7Scenario, ...],
    *,
    adapters: tuple[AdapterAR7Scenario, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterAR7Scenario]:
    """
    Run AR7 scenarios with each adapter

    This is the interface we recommend for users:
    it guarantees that the inputs are verified.
    Calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    ar7_scenarios
        Scenarios to run (each one is exactly one scenario)

    adapters
        Adapters to run the scenarios with

    output_specs
        Outputs to return

    run_checks
        Whether to verify inputs and check each adapter's output capabilities.
        Only turn this off if you know what you are doing.

        Returned-output count/type checks are still performed.
        Adapters may retain their own native/resource safety checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar7_scenarios(ar7_scenarios)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            ar7_scenarios=ar7_scenarios, output_specs=output_specs
        ),
        n_inputs=len(ar7_scenarios),
        output_specs=output_specs,
        run_checks=run_checks,
    )


def run_ar6_scenarios(
    ar6_scenarios: tuple[AR6Scenario, ...],
    *,
    adapters: tuple[AdapterAR6Scenario, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterAR6Scenario]:
    """
    Run AR6 scenarios with each adapter

    See [run_ar7_scenarios][(m).] for details,
    this is the same except for the input definition.

    Parameters
    ----------
    ar6_scenarios
        Scenarios to run (each one is exactly one scenario)

    adapters
        Adapters to run the scenarios with

    output_specs
        Outputs to return

    run_checks
        Whether to verify inputs and check each adapter's output capabilities

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar6_scenarios(ar6_scenarios)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            ar6_scenarios=ar6_scenarios, output_specs=output_specs
        ),
        n_inputs=len(ar6_scenarios),
        output_specs=output_specs,
        run_checks=run_checks,
    )


def run_ar6_scenarios_anthropogenic_only(
    ar6_scenarios: tuple[AR6Scenario, ...],
    *,
    adapters: tuple[AdapterAR6ScenarioAnthropogenicOnly, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterAR6ScenarioAnthropogenicOnly]:
    """
    Run AR6 scenarios with anthropogenic forcing only with each adapter

    See [run_ar6_scenarios][(m).] for details,
    this is the same except for the forcing the adapters include
    (see [AdapterAR6ScenarioAnthropogenicOnly][(m).]).

    Parameters
    ----------
    ar6_scenarios
        Scenarios to run (each one is exactly one scenario)

    adapters
        Adapters to run the scenarios with

    output_specs
        Outputs to return

    run_checks
        Whether to verify the inputs before running

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar6_scenarios(ar6_scenarios)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            ar6_scenarios=ar6_scenarios, output_specs=output_specs
        ),
        n_inputs=len(ar6_scenarios),
        output_specs=output_specs,
        run_checks=run_checks,
    )


def run_ar6_scenarios_co2_forcing_only(
    ar6_co2_emissions: tuple[AR6ScenarioCO2Emissions, ...],
    *,
    adapters: tuple[AdapterAR6ScenarioCO2ForcingOnly, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterAR6ScenarioCO2ForcingOnly]:
    """
    Run AR6 scenarios with CO2 forcing only with each adapter

    See [run_ar6_scenarios][(m).] for details,
    this is the same except that the input is only the scenarios' CO2 emissions
    and the adapters only include CO2 forcing
    (see [AdapterAR6ScenarioCO2ForcingOnly][(m).]).

    Parameters
    ----------
    ar6_co2_emissions
        CO2 emissions of the scenarios to run (each one is exactly one scenario)

    adapters
        Adapters to run the scenarios with

    output_specs
        Outputs to return

    run_checks
        Whether to verify the inputs before running

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar6_scenario_co2_emissions(ar6_co2_emissions)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            ar6_co2_emissions=ar6_co2_emissions, output_specs=output_specs
        ),
        n_inputs=len(ar6_co2_emissions),
        output_specs=output_specs,
        run_checks=run_checks,
    )
