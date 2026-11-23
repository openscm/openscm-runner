"""
Adapter protocol and run function for ERF-driven experiments starting from equilibrium
"""

from __future__ import annotations

from typing import Protocol

from openscm_runner.output import OpenSCMRunnerOutput, RunResults
from openscm_runner.output_specs import OutputCapabilities, OutputSpecs
from openscm_runner.running import run_adapters

from .inputs import ERF, verify_erf


class AdapterERFDrivenFromEquilibrium(OutputCapabilities, Protocol):
    """
    Adapter that can run ERF-driven experiments starting from equilibrium

    The input provides a single, already-combined total ERF timeseries.
    The adapter applies it as given,
    with no additional forcing and no efficacy adjustments.

    The input can start in any year.
    The adapter is responsible for setting up the equilibrium start
    (i.e. the model is in equilibrium with zero ERF at the start of the run).
    """

    # TODO: have the same kind of information in all of our different docstrings
    # (probably different docstrings are saying different things right now).
    # High priority as getting this right
    # will make docs for other adapter implementers easier.

    def __call__(
        self,
        erf: tuple[ERF, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments, returning one output per input, in input order"""


def run_erf_driven_from_equilibrium(
    erf: tuple[ERF, ...],
    *,
    adapters: tuple[AdapterERFDrivenFromEquilibrium, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterERFDrivenFromEquilibrium]:
    """
    Run ERF-driven experiments starting from equilibrium

    Same pattern as `run_ar7_scenarios` (TODO make this a cross-ref if we keep it),
    see its docstring for the details of `run_checks` and the open TODOs.
    TODO: decide whether this cross-ref goes in docstrings or comments throughout.

    Parameters
    ----------
    erf
        Inputs (each one is exactly one experiment)

    adapters
        Adapters to run the experiments with

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
        verify_erf(erf)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(erf=erf, output_specs=output_specs),
        n_inputs=len(erf),
        output_specs=output_specs,
        run_checks=run_checks,
    )
