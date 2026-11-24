"""Exercise the promoted public runners without a native model."""

import sys

import pandas as pd
import pytest

import openscm_runner
from openscm_runner import (
    AdapterERFDrivenFromEquilibrium,
    AdapterOutputError,
    EnsembleMemberResult,
    InvalidInputError,
    OpenSCMRunnerOutput,
    OutputSpecs,
    UnsupportedOutputError,
    run_erf_driven_from_equilibrium,
)

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

SPECS = OutputSpecs(("Surface Air Temperature Change",))


def make_input(name: str) -> pd.DataFrame:
    return pd.DataFrame(
        [[0.0, 1.0]],
        index=pd.MultiIndex.from_tuples(
            [(name, "Effective Radiative Forcing", "World", "W/m^2")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=[2000, 2001],
    )


class RecordingAdapter:
    supported_output_variables = frozenset(SPECS.output_variables)

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[pd.DataFrame, ...], OutputSpecs]] = []

    def __call__(
        self, erf: tuple[pd.DataFrame, ...], *, output_specs: OutputSpecs
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        self.calls.append((erf, output_specs))
        outputs = []
        for frame in erf:
            data = frame.copy(deep=True)
            data.index = pd.MultiIndex.from_tuples(
                [
                    (
                        frame.index.get_level_values("scenario")[0],
                        "Surface Air Temperature Change",
                        "World",
                        "K",
                    )
                ],
                names=frame.index.names,
            )
            outputs.append(
                OpenSCMRunnerOutput((EnsembleMemberResult.from_success("a", data),))
            )
        return tuple(outputs)


class FailingAdapter:
    supported_output_variables = frozenset(SPECS.output_variables)

    def __init__(self, error: Exception) -> None:
        self.error = error

    def __call__(
        self, erf: tuple[pd.DataFrame, ...], *, output_specs: OutputSpecs
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        raise self.error


def test_public_exports_resolve():
    assert len(openscm_runner.__all__) == len(set(openscm_runner.__all__))
    for name in openscm_runner.__all__:
        assert getattr(openscm_runner, name) is not None
    assert openscm_runner.OpenSCMRunnerOutput is OpenSCMRunnerOutput
    for removed in ("CheckedAdapter", "ModelCore", "AdapterRegistry", "get_adapter"):
        assert not hasattr(openscm_runner, removed)


def test_adapter_and_experiment_order_and_no_mutation():
    inputs = tuple(make_input(f"experiment-{i}") for i in range(7))
    before = tuple(frame.copy(deep=True) for frame in inputs)
    adapters = (RecordingAdapter(), RecordingAdapter())
    results = run_erf_driven_from_equilibrium(
        inputs, adapters=adapters, output_specs=SPECS
    )
    assert len(results) == 2
    assert results.all_succeeded
    results.raise_if_any_failed()
    for result, adapter in zip(results, adapters, strict=True):
        assert result.adapter is adapter
        assert len(adapter.calls) == 1
        assert adapter.calls[0][0] is inputs
        assert adapter.calls[0][1] is SPECS
        assert len(result.outputs) == len(inputs)
        for output, frame, original in zip(result.outputs, inputs, before, strict=True):
            scenarios = output.as_df().index.get_level_values("scenario")
            expected = frame.index.get_level_values("scenario")
            assert scenarios.unique().tolist() == expected.unique().tolist()
            pd.testing.assert_frame_equal(frame, original)


def test_failure_does_not_discard_other_adapters():
    error = RuntimeError("native failure")
    failed = FailingAdapter(error)
    succeeded = RecordingAdapter()
    results = run_erf_driven_from_equilibrium(
        (make_input("test"),), adapters=(failed, succeeded), output_specs=SPECS
    )
    assert not results.all_have_outputs
    assert not results.all_succeeded
    assert results.without_outputs == (results[0],)
    assert results.failures == (results[0],)
    assert results[1].all_succeeded
    assert len(succeeded.calls) == 1
    with pytest.raises(RuntimeError, match="native failure") as exc:
        _ = results[0].outputs
    assert exc.value is error
    with pytest.raises(ExceptionGroup, match=r"0 \(FailingAdapter\)") as group:
        results.raise_if_any_failed()
    assert group.value.exceptions == (error,)


@pytest.mark.parametrize("run_checks", [True, False])
@pytest.mark.parametrize(
    "outputs, message",
    [
        pytest.param((), "returned 0 outputs", id="wrong-count"),
        pytest.param(
            (pd.DataFrame(),), "must return `OpenSCMRunnerOutput`s", id="wrong-element"
        ),
        pytest.param(None, "must return a tuple", id="none"),
        pytest.param(42, "must return a tuple", id="scalar"),
        pytest.param({}, "must return a tuple", id="mapping"),
        pytest.param(
            [
                OpenSCMRunnerOutput(
                    (EnsembleMemberResult.from_success("a", make_input("test")),)
                )
            ],
            "must return a tuple",
            id="list",
        ),
    ],
)
def test_malformed_adapter_outputs_are_recorded(outputs, message, run_checks):
    class MalformedAdapter:
        supported_output_variables = frozenset(SPECS.output_variables)

        def __call__(self, erf, *, output_specs):
            return outputs

    first, last = RecordingAdapter(), RecordingAdapter()
    malformed = MalformedAdapter()
    results = run_erf_driven_from_equilibrium(
        (make_input("test"),),
        adapters=(first, malformed, last),
        output_specs=SPECS,
        run_checks=run_checks,
    )
    assert [r.adapter for r in results] == [first, malformed, last]
    assert results[0].all_succeeded and results[2].all_succeeded
    assert len(first.calls) == len(last.calls) == 1
    assert isinstance(results[1].error_if_no_outputs, AdapterOutputError)
    assert results.failures == (results[1],)
    with pytest.raises(AdapterOutputError, match=message):
        _ = results[1].outputs


def test_checks_are_owned_by_runner():
    invalid = make_input("test").drop(columns=2000).rename(columns={2001: 2000.5})
    adapter = RecordingAdapter()
    adapters: tuple[AdapterERFDrivenFromEquilibrium, ...] = (adapter,)
    with pytest.raises(InvalidInputError):
        run_erf_driven_from_equilibrium(
            (invalid,), adapters=adapters, output_specs=SPECS
        )
    assert not adapter.calls
    results = run_erf_driven_from_equilibrium(
        (invalid,), adapters=adapters, output_specs=SPECS, run_checks=False
    )
    assert results.all_succeeded
    assert len(adapter.calls) == 1


def test_empty_adapter_selection():
    with pytest.raises(ValueError, match="No adapters"):
        run_erf_driven_from_equilibrium(
            (make_input("test"),), adapters=(), output_specs=SPECS
        )


def test_incompatible_adapter_is_not_called_and_others_continue():
    incompatible = RecordingAdapter()
    incompatible.supported_output_variables = frozenset({"Other Diagnostic"})
    first, last = RecordingAdapter(), RecordingAdapter()
    results = run_erf_driven_from_equilibrium(
        (make_input("test"),),
        adapters=(first, incompatible, last),
        output_specs=SPECS,
    )
    assert [r.adapter for r in results] == [first, incompatible, last]
    assert results[0].all_succeeded
    assert results[2].all_succeeded
    assert len(first.calls) == len(last.calls) == 1
    assert not incompatible.calls
    assert isinstance(results[1].error_if_no_outputs, UnsupportedOutputError)
    assert results.failures == (results[1],)
    with pytest.raises(ExceptionGroup) as exc:
        results.raise_if_any_failed()
    assert exc.value.exceptions == (results[1].error_if_no_outputs,)


def test_unchecked_execution_does_not_read_capabilities():
    class ExpertAdapter(RecordingAdapter):
        def __getattribute__(self, name):
            if name == "supported_output_variables":
                msg = "Capabilities should not be read"
                raise AssertionError(msg)
            return super().__getattribute__(name)

    adapter = ExpertAdapter()
    results = run_erf_driven_from_equilibrium(
        (make_input("test"),),
        adapters=(adapter,),
        output_specs=SPECS,
        run_checks=False,
    )
    assert results.all_succeeded
    assert len(adapter.calls) == 1


def test_request_can_change_between_calls_on_one_adapter():
    adapter = RecordingAdapter()
    unsupported = OutputSpecs(("Other Diagnostic",))
    inputs = (make_input("test"),)
    first = run_erf_driven_from_equilibrium(
        inputs, adapters=(adapter,), output_specs=SPECS
    )
    second = run_erf_driven_from_equilibrium(
        inputs, adapters=(adapter,), output_specs=unsupported
    )
    third = run_erf_driven_from_equilibrium(
        inputs, adapters=(adapter,), output_specs=SPECS
    )
    assert first.all_succeeded and third.all_succeeded
    assert isinstance(second[0].error_if_no_outputs, UnsupportedOutputError)
    assert len(adapter.calls) == 2
