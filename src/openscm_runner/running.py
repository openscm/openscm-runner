"""
Shared adapter execution, used by every `run_*` function
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .output import (
    AdapterOutputError,
    AdapterRunResult,
    OpenSCMRunnerOutput,
    RunResults,
)
from .output_specs import OutputCapabilities, OutputSpecs, validate_output_request

AdapterT = TypeVar("AdapterT", bound=OutputCapabilities)


def run_adapters(
    adapters: tuple[AdapterT, ...],
    *,
    # TODO: why not make this ?
    # inputs: tuple[InputT, ...],
    # call: Callable[[AdapterT, InputT], tuple[OpenSCMRunnerOutput, ...]],
    # I assume so that you can run multiple adapters for different experiments
    # (the above would only allow this to run a single kind of experiment
    # at a time).
    # However, the fact that we have n_inputs means we are effectively locked
    # to a single kind of input here too.
    # There is something I'm missing about why this is a useful interface...
    call: Callable[[AdapterT], tuple[OpenSCMRunnerOutput, ...]],
    n_inputs: int,
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterT]:
    """
    Run each adapter and collect the results

    The adapters are run one after the other.
    We haven't worked out what kind of parallelism across adapters
    makes sense (or is useful) to offer users with confidence yet.
    Until we do, parallelism is left to the adapters
    (and experts can write their own loop around the adapters).

    If an adapter raises or returns malformed outputs, the error is stored
    in its result and the remaining adapters are still run.

    Parameters
    ----------
    adapters
        Adapters to run

    call
        Function that calls one adapter with the inputs.
        Each `run_*` function passes in a function that calls the adapter
        with keyword arguments, so mypy can check the argument names.

    n_inputs
        Number of inputs.
        Each adapter must return exactly this many outputs.

    output_specs
        Request forwarded to every adapter.

    run_checks
        Whether to check each adapter's capabilities before calling it.
        Returned-output count/type checks are unaffected.
        TODO: cross reference roadmap item about this

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if not adapters:
        msg = "No adapters were given, so there is nothing to run"
        raise ValueError(msg)

    results: list[AdapterRunResult[AdapterT]] = []
    for adapter in adapters:
        try:
            if run_checks:
                validate_output_request(adapter, output_specs)

            outputs = call(adapter)

            verify_adapter_outputs(adapter, outputs, n_inputs=n_inputs)

        except Exception as exc:
            results.append(AdapterRunResult.from_failure(adapter, exc))
            continue

        results.append(AdapterRunResult.from_success(adapter, outputs))

    return RunResults(tuple(results))


def verify_adapter_outputs(
    adapter: object,
    outputs: object,
    *,
    n_inputs: int,
) -> None:
    """
    Verify that an adapter's outputs follow the shared output rules

    Parameters
    ----------
    adapter
        Adapter that produced `outputs` (used in error messages)

    outputs
        Outputs returned by the adapter

    n_inputs
        Number of inputs the adapter was given.
        The adapter must return exactly this many outputs.

    Raises
    ------
    AdapterOutputError
        `outputs` is not a tuple of `OpenSCMRunnerOutput`s
        with exactly one element per input
    """
    if not isinstance(outputs, tuple):
        msg = (
            f"{adapter!r} must return a tuple of `OpenSCMRunnerOutput`s, "
            f"received {type(outputs).__name__!r}"
        )
        raise AdapterOutputError(msg)

    if len(outputs) != n_inputs:
        msg = (
            f"{adapter!r} returned {len(outputs)} outputs "
            f"for {n_inputs} inputs (it must return exactly one per input)"
        )
        raise AdapterOutputError(msg)

    wrong_types = sorted(
        {type(o).__name__ for o in outputs if not isinstance(o, OpenSCMRunnerOutput)}
    )
    if wrong_types:
        msg = (
            f"{adapter!r} must return `OpenSCMRunnerOutput`s, received {wrong_types!r}"
        )
        raise AdapterOutputError(msg)

    # TODO: check the requested variables are all in the output.
    # TODO: check ensemble member IDs follow the agreed naming scheme.
    # TODO: decide which additional output checks `run_checks=False` skips.
