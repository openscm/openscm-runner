"""Success, partial failure and dataframe access for the promoted containers."""

import sys

import pandas as pd
import pytest

from openscm_runner import (
    AdapterRunResult,
    EnsembleMemberResult,
    OpenSCMRunnerOutput,
    RunResults,
)

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup


def make_data() -> pd.DataFrame:
    return pd.DataFrame(
        [[1.0, 2.0]],
        index=pd.MultiIndex.from_tuples(
            [("test", "Surface Air Temperature Change", "World", "K")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=[2000, 2001],
    )


def test_successful_members_combine_in_member_order():
    first = make_data()
    second = first * 2
    before = first.copy(deep=True)
    output = OpenSCMRunnerOutput(
        (
            EnsembleMemberResult.from_success("b", first),
            EnsembleMemberResult.from_success("a", second),
        )
    )
    assert output.all_succeeded
    assert output.failures == ()
    output.raise_if_any_failed()
    combined = output.as_df()
    assert combined.index.names == ["ensemble_member", *first.index.names]
    assert combined.index.get_level_values("ensemble_member").tolist() == ["b", "a"]
    pd.testing.assert_frame_equal(combined.xs("b", level="ensemble_member"), first)
    pd.testing.assert_frame_equal(combined.xs("a", level="ensemble_member"), second)
    assert output.as_df(ensemble_member_level="member").index.names[0] == "member"
    pd.testing.assert_frame_equal(first, before)


def test_partial_member_failure_is_not_adapter_failure():
    error = RuntimeError("member failed")
    failed = EnsembleMemberResult.from_failure("failed", error)
    succeeded = EnsembleMemberResult.from_success("ok", make_data())
    output = OpenSCMRunnerOutput((failed, succeeded))
    assert not failed.succeeded
    assert not output.all_succeeded
    assert output.failures == (failed,)
    with pytest.raises(RuntimeError, match="member failed") as exc:
        _ = failed.data
    assert exc.value is error
    with pytest.raises(ExceptionGroup, match="'failed'") as group:
        output.as_df()
    assert group.value.exceptions == (error,)
    pd.testing.assert_frame_equal(
        output.as_df(skip_failed=True).xs("ok", level="ensemble_member"),
        succeeded.data,
    )
    result = AdapterRunResult.from_success("adapter", (output,))
    results = RunResults((result,))
    assert result.succeeded
    assert results.all_succeeded
    assert results.failures == ()
    assert list(results) == [result]
    assert results[0] is result
    results.raise_if_any_failed()


def test_no_successful_members():
    output = OpenSCMRunnerOutput(
        (EnsembleMemberResult.from_failure("a", RuntimeError("failed")),)
    )
    with pytest.raises(ValueError, match="No ensemble members succeeded"):
        output.as_df(skip_failed=True)


def test_member_identity_and_dataframe_level_collisions():
    member = EnsembleMemberResult.from_success("a", make_data())
    with pytest.raises(ValueError, match="at least one"):
        OpenSCMRunnerOutput(())
    with pytest.raises(ValueError, match="must be unique"):
        OpenSCMRunnerOutput((member, member))
    with pytest.raises(ValueError, match="already an index level"):
        OpenSCMRunnerOutput((member,)).as_df(ensemble_member_level="scenario")


@pytest.mark.parametrize("both_set", [False, True])
def test_result_requires_exactly_one_of_data_and_error(both_set):
    data = make_data() if both_set else None
    error = RuntimeError("failed") if both_set else None
    with pytest.raises(ValueError, match="Exactly one"):
        EnsembleMemberResult("a", data, error)
    outputs = () if both_set else None
    with pytest.raises(ValueError, match="Exactly one"):
        AdapterRunResult("adapter", outputs, error)
