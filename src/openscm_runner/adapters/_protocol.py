"""
Structural protocol for the new stateful adapter API.

An :class:`AdapterLike` object is configured once at construction
(with cfgs, mode, output variables, output config, and anything else
the model needs), then exposed via a single
``run(scenarios) -> scmdata.ScmRun`` call. The wrapper does no
config carrying of its own; whatever the adapter needs to know to
produce a result has to be in the instance by the time ``.run`` is
called.

Adapters that support a native parameter distribution (e.g. a
calibration bundle on disk) expose a ``from_native_distribution``
classmethod that returns a fully-configured instance. The classmethod
is allowed to defer the actual loading of the distribution until
``.run`` is called -- it can just store the path.

Existing adapters (FaIR 1.6, MAGICC, CICERO-SCM 1.1.x) are
:class:`AdapterLike`-compatible via the
:class:`~openscm_runner.adapters.base._Adapter` base class, which
takes the same constructor arguments and binds them to instance
state before delegating to the adapter's ``_run`` implementation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import scmdata


class AdapterLike(Protocol):
    """
    Minimum surface a climate-model adapter exposes to
    :func:`openscm_runner.run.run`.

    Implementations are stateful objects: construction binds the
    cfgs, mode, output variable selection and any other
    model-specific configuration. ``run`` consumes a scenarios
    DataFrame and returns model output.
    """

    def run(self, scenarios) -> "scmdata.ScmRun":  # noqa: D401
        """Run the model over ``scenarios`` and return its output."""
        ...
