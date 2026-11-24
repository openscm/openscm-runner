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
#
# The run functions in all the experiment subpackages follow the same pattern
# (verify the inputs if `run_checks`, then run each adapter with `run_adapters`),
# so their docstrings are the same apart from the experiment and the input's name.

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
    Adapter that can run AR7 scenarios

    Runs an emissions scenario defined in AR7 terms.

    The adapter is responsible for adding AR7's history
    and the forcing the scenario doesn't supply (e.g. volcanic),
    in line with the standard AR7 choices.

    Forcing: all (anthropogenic and natural).

    Open decisions: AR7's history and other forcing aren't defined yet,
    so this experiment is unstable
    (whether to keep it until they are is decision [B23][b23]).
    """

    def __call__(
        self,
        ar7_scenarios: tuple[AR7Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        ar7_scenarios
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `ar7_scenarios`
        """


class AdapterAR6Scenario(OutputCapabilities, Protocol):
    """
    Adapter that can run AR6 scenarios

    Runs an emissions scenario defined in AR6 terms.

    The adapter is responsible for adding AR6's history
    and the forcing the scenario doesn't supply (e.g. volcanic),
    in line with the standard AR6 choices.

    Forcing: all (anthropogenic and natural).
    """

    def __call__(
        self,
        ar6_scenarios: tuple[AR6Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        ar6_scenarios
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `ar6_scenarios`
        """


class AdapterAR6ScenarioAnthropogenicOnly(OutputCapabilities, Protocol):
    """
    Adapter that can run AR6 scenarios with anthropogenic forcing only

    As for [AdapterAR6Scenario][(m).]
    (including AR6's history and land-use treatment),
    except that there is no natural (solar and volcanic) forcing
    for the whole run.

    The adapter is responsible for turning the natural forcing off,
    not for subtracting a natural-only run from a full run
    (the response isn't linear).

    Forcing: anthropogenic only
    (land-use forcing is anthropogenic, so it is included).

    /// note | Details still being worked out
    This experiment is for the remaining carbon budget workflow,
    whose exact needs we are still clarifying (decision [B12][b12]),
    so its definition may change.
    ///
    """

    def __call__(
        self,
        ar6_scenarios: tuple[AR6Scenario, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        ar6_scenarios
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `ar6_scenarios`
        """


class AdapterAR6ScenarioCO2ForcingOnly(OutputCapabilities, Protocol):
    """
    Adapter that can run AR6 scenarios with CO2 forcing only

    As for [AdapterAR6Scenario][(m).] (including AR6's history),
    except that the only forcing is CO2's, for the whole run.

    Forcing: CO2 only.
    Non-CO2 forcing and land-use (albedo) forcing are absent.
    The carbon cycle sees all the CO2 emissions (fossil and biosphere).
    Any CO2 from the oxidation of (fossil) CH4 in the scenario isn't included.

    Open decisions: which feedbacks to include (decision [B16][b16])
    and whether to use fossil CO2 emissions only (decision [B17][b17]).
    """

    def __call__(
        self,
        ar6_co2_emissions: tuple[AR6ScenarioCO2Emissions, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        ar6_co2_emissions
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `ar6_co2_emissions`
        """


def run_ar7_scenarios(
    ar7_scenarios: tuple[AR7Scenario, ...],
    *,
    adapters: tuple[AdapterAR7Scenario, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterAR7Scenario]:
    """
    Run AR7 scenarios with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    ar7_scenarios
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar7_scenarios(ar7_scenarios)

    return run_adapters(
        adapters,
        inputs=ar7_scenarios,
        call=lambda adapter, inputs, output_specs: adapter(
            ar7_scenarios=inputs, output_specs=output_specs
        ),
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

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    ar6_scenarios
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar6_scenarios(ar6_scenarios)

    return run_adapters(
        adapters,
        inputs=ar6_scenarios,
        call=lambda adapter, inputs, output_specs: adapter(
            ar6_scenarios=inputs, output_specs=output_specs
        ),
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

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    ar6_scenarios
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar6_scenarios(ar6_scenarios)

    return run_adapters(
        adapters,
        inputs=ar6_scenarios,
        call=lambda adapter, inputs, output_specs: adapter(
            ar6_scenarios=inputs, output_specs=output_specs
        ),
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

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    ar6_co2_emissions
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_ar6_scenario_co2_emissions(ar6_co2_emissions)

    return run_adapters(
        adapters,
        inputs=ar6_co2_emissions,
        call=lambda adapter, inputs, output_specs: adapter(
            ar6_co2_emissions=inputs, output_specs=output_specs
        ),
        output_specs=output_specs,
        run_checks=run_checks,
    )
