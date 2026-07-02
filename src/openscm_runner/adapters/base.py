"""
Base class for adapters.

Adapters are stateful objects: construction binds cfgs, mode,
output variables and output config to the instance, and
:meth:`_Adapter.run` consumes a scenarios DataFrame and returns
:class:`scmdata.ScmRun` output.

The cfgs / mode / output_variables / output_config kwargs all
default to ``None`` (or the EMISSIONS_DRIVEN default for mode) so
that ``AdapterClass()`` still returns a usable instance for
``get_adapter``-style lookups. The high-level
:func:`openscm_runner.run.run` dispatcher constructs adapters with
the right kwargs on every call.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from .._run_mode import RunMode


class _Adapter(ABC):
    """
    Base class for adapters.
    """

    # Case-insensitive name of the simple climate model
    model_name: str | None = None

    # Driving modes this adapter supports. Concrete adapters override
    # with the modes they actually handle; :meth:`run` raises
    # :class:`NotImplementedError` if ``self.mode`` is not in this set.
    # Default is the conservative case (emissions-driven only) since
    # that's what the original upstream wrapper exposed.
    supported_modes: frozenset[RunMode] = frozenset({RunMode.EMISSIONS_DRIVEN})

    def __init__(
        self,
        cfgs: list[dict[str, Any]] | None = None,
        mode: RunMode = RunMode.EMISSIONS_DRIVEN,
        output_variables: Iterable[str] | None = None,
        output_config: Iterable[str] | None = None,
    ):
        """
        Initialise the adapter.

        Parameters
        ----------
        cfgs
            Configs with which to run the model. Each entry is a
            dict of model-specific parameter names mapped to values.
            Optional at construction; callers that use
            :func:`openscm_runner.run.run` pass the cfgs at the
            call site and the wrapper threads them in.
        mode
            Driving mode for the run. Adapters that don't support
            the requested mode raise :class:`NotImplementedError`
            on :meth:`run`. Defaults to
            :attr:`RunMode.EMISSIONS_DRIVEN`.
        output_variables
            Variables to include in the output.
        output_config
            Cfg keys to surface as meta columns on the output
            :class:`scmdata.ScmRun`.
        """
        self.cfgs = cfgs
        self.mode = mode
        self.output_variables = output_variables
        self.output_config = output_config
        self._init_model()

    @abstractmethod
    def _init_model(self) -> None:
        """
        Initialise the model.

        Override on concrete adapters to do model-specific
        availability checks (e.g. ``ImportError`` if the model
        package isn't installed).
        """

    def run(self, scenarios) -> "scmdata.ScmRun":  # type: ignore[name-defined]  # noqa: F821
        """
        Run the model over ``scenarios``.

        Parameters
        ----------
        scenarios
            Scenarios to run, as an :class:`scmdata.ScmRun` or
            :class:`pyam.IamDataFrame`.

        Raises
        ------
        NotImplementedError
            ``self.mode`` is not in :attr:`supported_modes`.

        Returns
        -------
        :obj:`scmdata.ScmRun`
            Model output.
        """
        if self.mode not in self.supported_modes:
            raise NotImplementedError(
                f"{type(self).__name__} does not support {self.mode}; "
                f"supported modes are "
                f"{sorted(m.value for m in self.supported_modes)}."
            )
        return self._run(
            scenarios,
            self.cfgs,
            self.output_variables,
            self.output_config,
        )

    @abstractmethod
    def _run(self, scenarios, cfgs, output_variables, output_config):
        """
        Run the model.

        Internal implementation of :meth:`run`. Concrete adapters
        keep the four-argument signature so the body of the method
        doesn't need to change as part of the AdapterLike reshape;
        the public :meth:`run` reads the three trailing args from
        instance state.
        """
