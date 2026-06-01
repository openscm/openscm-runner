"""
Run-mode enum exposed at the top of :mod:`openscm_runner`.

Modes are an explicit, narrow public surface: each adapter declares
which modes it supports, and :func:`openscm_runner.run.run` rejects
any mode that no requested adapter can handle. Adapters that are
constructed directly may also accept ``mode`` as a constructor
argument so the user can pre-configure a run from a notebook or a
script without going through the dict API.

The enum deliberately stays small. Further values get added only
when a concrete adapter-side wiring need surfaces.
"""
from __future__ import annotations

from enum import Enum


class RunMode(str, Enum):
    """
    Driving mode for a climate-model run.

    ``EMISSIONS_DRIVEN`` consumes ``Emissions|*`` variables from the
    scenarios DataFrame and produces atmospheric concentrations,
    radiative forcing and surface temperature as model output.

    ``CONCENTRATION_DRIVEN`` consumes ``Atmospheric Concentrations|*``
    variables from the scenarios DataFrame (plus any non-WMGHG ERFs
    the model needs to read in this mode) and produces radiative
    forcing and surface temperature.
    """

    EMISSIONS_DRIVEN = "emissions_driven"
    CONCENTRATION_DRIVEN = "concentration_driven"
