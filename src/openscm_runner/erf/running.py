"""
Adapter protocol and run function for ERF-driven experiments starting from equilibrium
"""

from __future__ import annotations

from typing import Protocol

from openscm_runner.output import OpenSCMRunnerOutput, RunResults
from openscm_runner.output_specs import OutputCapabilities, OutputSpecs
from openscm_runner.running import run_adapters

from .inputs import ERF, verify_erf

# The run functions in all the experiment subpackages follow the same pattern
# (verify the inputs if `run_checks`, then run each adapter with `run_adapters`),
# so their docstrings are the same apart from the experiment and the input's name.


class AdapterERFDrivenFromEquilibrium(OutputCapabilities, Protocol):
    """
    Adapter that can run ERF-driven experiments starting from equilibrium

    Runs the model driven by a single total effective radiative forcing (ERF)
    timeseries.

    The adapter is responsible for starting the model in (climate) equilibrium
    and applying the ERF as given,
    with no additional forcing and no efficacy adjustments.

    Forcing: the ERF only.
    """

    def __call__(
        self,
        erf: tuple[ERF, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        erf
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `erf`
        """


def run_erf_driven_from_equilibrium(
    erf: tuple[ERF, ...],
    *,
    adapters: tuple[AdapterERFDrivenFromEquilibrium, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterERFDrivenFromEquilibrium]:
    """
    Run ERF-driven experiments starting from equilibrium with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    erf
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
        verify_erf(erf)

    return run_adapters(
        adapters,
        inputs=erf,
        call=lambda adapter, inputs, output_specs: adapter(
            erf=inputs, output_specs=output_specs
        ),
        output_specs=output_specs,
        run_checks=run_checks,
    )
