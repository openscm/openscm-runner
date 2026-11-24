"""
Experiment and ensemble output containers

There are four levels:

- [RunResults][(m).]: what the `run_*` functions return.
  One [AdapterRunResult][(m).] per adapter.
- [AdapterRunResult][(m).]: the outputs of one adapter
  (one [OpenSCMRunnerOutput][(m).] per input)
  or the error if the adapter failed as a whole.
- [OpenSCMRunnerOutput][(m).]: the output for one experiment (one input).
  One [EnsembleMemberResult][(m).] per ensemble member
- [EnsembleMemberResult][(m).]: the result for one ensemble member from an adapter.
  Holds the data if the member ran successfully or the error if it failed.

The containers keep what worked and record what failed,
so one failure doesn't throw away all the other results.
Accessing a failed result's data should re-raise its error,
so failures aren't silently missed.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, TypeVar

import pandas as pd

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

AdapterT = TypeVar("AdapterT")


class AdapterOutputError(ValueError):
    """Raised (and stored) when an adapter's output breaks the shared output rules"""


@dataclass(frozen=True, slots=True)
class EnsembleMemberResult:
    """
    Result for one ensemble member of one experiment

    Create with [from_success][(c).from_success] or [from_failure][(c).from_failure].
    """

    ensemble_member: str
    """
    ID of the ensemble member, provided by the adapter

    The naming scheme for ensemble members is still to be agreed
    (decision [A3][a3]).
    """

    data_if_succeeded: pd.DataFrame | None
    """Wide dataframe of outputs, `None` if the member failed (use `data` normally)"""

    error: Exception | None
    """Error raised for this member, `None` if it succeeded"""

    def __post_init__(self) -> None:  # noqa: D105
        if (self.data_if_succeeded is None) == (self.error is None):
            msg = "Exactly one of `data_if_succeeded` and `error` must be set"
            raise ValueError(msg)

    @classmethod
    def from_success(
        cls, ensemble_member: str, data: pd.DataFrame
    ) -> EnsembleMemberResult:
        """Create a result for an ensemble member that ran successfully"""
        return cls(ensemble_member=ensemble_member, data_if_succeeded=data, error=None)

    @classmethod
    def from_failure(
        cls, ensemble_member: str, error: Exception
    ) -> EnsembleMemberResult:
        """Create a result for an ensemble member that failed"""
        return cls(ensemble_member=ensemble_member, data_if_succeeded=None, error=error)

    @property
    def succeeded(self) -> bool:
        """Whether this ensemble member ran successfully"""
        # Post init hook means we don't have to check self.data
        return self.error is None

    @property
    def data(self) -> pd.DataFrame:
        """
        Wide dataframe of outputs

        This is the recommended way to get your data
        if you want an error to raise if there was one.

        Raises
        ------
        Exception
            The stored error, if this ensemble member failed
        """
        if self.error is not None:
            raise self.error

        if self.data_if_succeeded is None:  # pragma: no cover
            # Can't happen because of the check in `__post_init__`
            raise AssertionError

        return self.data_if_succeeded


@dataclass(frozen=True, slots=True)
class OpenSCMRunnerOutput:
    """
    Output for one experiment (i.e. one set of input)

    One result per ensemble member.
    Use [as_df][(c).as_df] to get a single dataframe
    containing results from all ensemble members.
    """

    members: tuple[EnsembleMemberResult, ...]
    """Result for each ensemble member"""

    def __post_init__(self) -> None:  # noqa: D105
        if not self.members:
            msg = "There must be at least one ensemble member"
            raise ValueError(msg)

        ids = [m.ensemble_member for m in self.members]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            msg = f"Ensemble member IDs must be unique, duplicates: {duplicates!r}"
            raise ValueError(msg)

    @property
    def failures(self) -> tuple[EnsembleMemberResult, ...]:
        """Results for the ensemble members that failed"""
        return tuple(m for m in self.members if not m.succeeded)

    @property
    def all_succeeded(self) -> bool:
        """Whether every ensemble member ran successfully"""
        return not self.failures

    def raise_if_any_failed(self) -> None:
        """
        Raise if any ensemble member failed

        Raises
        ------
        ExceptionGroup
            Group containing the error from each failed ensemble member
        """
        failures = self.failures
        if failures:
            names = ", ".join(repr(m.ensemble_member) for m in failures)
            msg = (
                f"{len(failures)} of {len(self.members)} ensemble members failed: "
                f"{names}"
            )
            raise ExceptionGroup(msg, [m.error for m in failures if m.error])

    def as_df(
        self,
        *,
        ensemble_member_level: str = "ensemble_member",
        raise_if_any_failed: bool = True,
    ) -> pd.DataFrame:
        """
        Combine the ensemble members' outputs into one dataframe

        Parameters
        ----------
        ensemble_member_level
            Name of the index level that identifies the ensemble member.
            It is the first level of the index
            (letting you choose where it goes is roadmap [W17][w17]).

        raise_if_any_failed
            If `True`, raise if any ensemble member failed.
            If `False`, leave out failed ensemble members.

        Returns
        -------
        :
            Wide dataframe with an extra `ensemble_member_level` index level

        Raises
        ------
        ExceptionGroup
            `raise_if_any_failed` is `True` and at least one ensemble member failed

        ValueError
            No ensemble member succeeded,
            or `ensemble_member_level` is already an index level of the data
        """
        if raise_if_any_failed:
            self.raise_if_any_failed()

        succeeded = [m for m in self.members if m.succeeded]
        if not succeeded:
            msg = "No ensemble members succeeded"
            raise ValueError(msg)

        for m in succeeded:
            if ensemble_member_level in m.data.index.names:
                msg = (
                    f"{ensemble_member_level!r} is already an index level "
                    f"of ensemble member {m.ensemble_member!r}'s data"
                )
                raise ValueError(msg)

        return pd.concat(
            [m.data for m in succeeded],
            keys=[m.ensemble_member for m in succeeded],
            names=[ensemble_member_level],
        )


@dataclass(frozen=True, slots=True)
class AdapterRunResult(Generic[AdapterT]):
    """
    Result of running one adapter

    Create with [from_success][(c).from_success] or [from_failure][(c).from_failure].

    TODO: think through if this is actually the logic we want.
    Probably we just need to change the names.
    `outputs_if_succeeded` --> `outputs`
    (the information about success is held by the OpenSCMRunnerOutput instance).
    `error` --> `error_if_no_output`
    (only use this if an OpenSCMRunnerOutput instance wasn't created).
    `succeeded` --> `has_outputs` and introduce new `succeeded` method
    that checks if any output has failures.
    `from_success` --> `from_outputs`
    `from_failure` --> `from_error`

    If the adapter ran, but some ensemble members failed,
    the adapter still succeeded:
    the failures are recorded in each [OpenSCMRunnerOutput][(m).].

    Notes
    -----
    This (or [OpenSCMRunnerOutput][(m).]) is likely the natural place
    for other information the adapter provides, e.g. provenance.
    """

    adapter: AdapterT
    """Adapter that was run"""

    outputs_if_succeeded: tuple[OpenSCMRunnerOutput, ...] | None
    """
    Outputs, `None` if the adapter failed

    To read the data, you normally should use `outputs`
    """

    error: Exception | None
    """Error raised by (or about) the adapter, `None` if it succeeded"""

    def __post_init__(self) -> None:  # noqa: D105
        if (self.outputs_if_succeeded is None) == (self.error is None):
            msg = "Exactly one of `outputs_if_succeeded` and `error` must be set"
            raise ValueError(msg)

    @classmethod
    def from_success(
        cls, adapter: AdapterT, outputs: tuple[OpenSCMRunnerOutput, ...]
    ) -> AdapterRunResult[AdapterT]:
        """Create a result for an adapter that ran successfully"""
        return cls(adapter=adapter, outputs_if_succeeded=outputs, error=None)

    @classmethod
    def from_failure(
        cls, adapter: AdapterT, error: Exception
    ) -> AdapterRunResult[AdapterT]:
        """Create a result for an adapter that failed"""
        return cls(adapter=adapter, outputs_if_succeeded=None, error=error)

    @property
    def succeeded(self) -> bool:
        """Whether the adapter ran successfully"""
        return self.error is None

    @property
    def outputs(self) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Outputs, one per input, in the same order as the inputs

        Raises
        ------
        Exception
            The stored error, if the adapter failed.
            This means failures can't be silently ignored.
        """
        if self.error is not None:
            raise self.error

        if self.outputs_if_succeeded is None:  # pragma: no cover
            # Can't happen because of the check in `__post_init__`
            raise AssertionError

        return self.outputs_if_succeeded


@dataclass(frozen=True, slots=True)
class RunResults(Generic[AdapterT]):
    """
    Results of running several adapters on the same inputs

    The results are in the same order as the adapters that were passed in.

    TODO: combine everything into a single dataframe.
    This needs an index level that identifies the adapter/model,
    which we haven't designed yet.

    TODO: similar tweaks to AdapterRunResult in terms of differentiating between
    no output at all, some output or all ensemble members ran successfully.
    """

    results: tuple[AdapterRunResult[AdapterT], ...]
    """Result for each adapter, in the same order as the adapters"""

    def __iter__(self) -> Iterator[AdapterRunResult[AdapterT]]:  # noqa: D105
        return iter(self.results)

    def __len__(self) -> int:  # noqa: D105
        return len(self.results)

    def __getitem__(self, index: int) -> AdapterRunResult[AdapterT]:  # noqa: D105
        return self.results[index]

    @property
    def failures(self) -> tuple[AdapterRunResult[AdapterT], ...]:
        """Results for the adapters that failed as a whole"""
        return tuple(r for r in self.results if not r.succeeded)

    @property
    def all_succeeded(self) -> bool:
        """
        Whether every adapter ran successfully

        This doesn't check individual ensemble members,
        see [OpenSCMRunnerOutput][(m).] for that.
        TODO: consider a method
        that does consider whether any individual ensemble failed.
        """
        return not self.failures

    def raise_if_any_failed(self) -> None:
        """
        Raise if any adapter failed as a whole

        Raises
        ------
        ExceptionGroup
            Group containing the error from each failed adapter.
            The message names the failed adapters (position and type).
        """
        failed = [(i, r) for i, r in enumerate(self.results) if not r.succeeded]
        if failed:
            names = ", ".join(f"{i} ({type(r.adapter).__name__})" for i, r in failed)
            msg = f"{len(failed)} of {len(self.results)} adapters failed: {names}"
            raise ExceptionGroup(msg, [r.error for _, r in failed if r.error])
