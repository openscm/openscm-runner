"""
Workarounds for upstream CICERO-SCM v2.x performance bugs.

The patches in this module are applied once when the CICEROSCMPY2
adapter package is imported. They modify upstream's
:mod:`ciceroscm.parallel.cscmparwrapper` in place; subprocesses
spawned via ``fork`` inherit the patched module functions, so the
runner's fork-mode multiprocessing on macOS works correctly. On
``spawn``-mode systems the workers re-import their modules and the
patches are re-applied at worker import time (because they live in
this module which is imported as part of the adapter package).

**Bug being worked around**

In ``ciceroscm.concentrations_emissions_handler.py`` (v2.1.0), the
carbon-cycle output computation is gated by a key-presence check
rather than a value check::

    if "carbon_cycle_outputs" in cfg:   # WRONG - True or False both trigger
        results["carbon cycle"] = self.get_carbon_cycle_data(...)

The ``CSCMParWrapper.run_over_cfgs`` method unconditionally passes
``{"carbon_cycle_outputs": carbon_cycle_outputs}`` (default ``True``)
into the run config, so every CICERO-SCM run pays the carbon-cycle
back-calculation cost (~30-50x speedup observed on conc-driven SSPs
when the key is absent).

**Patch**

1. ``CSCMParWrapper.run_over_cfgs`` is wrapped to:
   - default ``carbon_cycle_outputs=False`` (was ``True``)
   - auto-enable it when any output variable in ``output_variables``
     requires carbon-cycle diagnostics (the six entries in
     ``ciceroscm.formattingtools.reformat_cscm_results.carbon_cycle_outputs``)
2. ``CICEROSCM._run`` is wrapped to strip the
   ``carbon_cycle_outputs`` key from the run config when its value
   is ``False``, dodging the upstream presence-based check.

Carbon-cycle outputs are still computed when actually requested
(any of the 6 unlocked variables, or via explicit
``cicero_carbon_cycle_outputs=True`` sidecar override on the
CICEROSCMPY2 adapter), so RCMIP back-calculated emissions
diagnostics remain available.

Upstream fix should change the gating to ``cfg.get(...)`` and could
also make ``CSCMParWrapper.run_over_cfgs`` thread ``carbon_cycle_outputs``
through more carefully. To be filed at
https://github.com/ciceroOslo/ciceroscm/issues
"""
from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)

# Variables whose computation requires the carbon-cycle back-calculation
# (mirrors ciceroscm.formattingtools.reformat_cscm_results.carbon_cycle_outputs).
_CARBON_CYCLE_VARIABLES = frozenset(
    {
        "Carbon Flux|Land",
        "Carbon Flux|Ocean",
        "Airborne fraction CO2",
        "Carbon Pool|Land",
        "Carbon Pool|Ocean",
        "Net Flux to Atmosphere|CO2",
    }
)


def output_vars_need_carbon_cycle(output_variables) -> bool:
    """Return True if any of ``output_variables`` requires the carbon cycle."""
    return bool(set(output_variables) & _CARBON_CYCLE_VARIABLES)


def apply_upstream_patches() -> None:
    """
    Apply the carbon-cycle-presence-bug workaround patches.

    Idempotent: re-applying is a no-op. Safe to call from module
    import (which is how this happens for spawn-mode subprocesses
    that re-import the adapter package).
    """
    try:
        from ciceroscm.parallel import cscmparwrapper
    except ImportError:
        # ciceroscm not installed; nothing to patch. The adapter's
        # _compat.py will raise a clear ImportError when something
        # actually tries to use CICEROSCMPY2.
        return

    if getattr(cscmparwrapper, "_openscm_runner_patches_applied", False):
        return

    # --- Patch 1: auto-detect carbon_cycle_outputs from output_variables ---
    _orig_run_over_cfgs = cscmparwrapper.CSCMParWrapper.run_over_cfgs

    def _patched_run_over_cfgs(
        self, cfgs, output_variables, carbon_cycle_outputs=False
    ):
        # Auto-enable cc if any output variable needs it (caller may
        # still force it on via explicit carbon_cycle_outputs=True).
        if not carbon_cycle_outputs and output_vars_need_carbon_cycle(
            output_variables
        ):
            carbon_cycle_outputs = True
        return _orig_run_over_cfgs(
            self, cfgs, output_variables, carbon_cycle_outputs
        )

    cscmparwrapper.CSCMParWrapper.run_over_cfgs = _patched_run_over_cfgs

    # --- Patch 2: strip carbon_cycle_outputs=False from cscm._run cfg ---
    _orig_cscm_run = cscmparwrapper.CICEROSCM._run

    def _patched_cscm_run(self, cfg, **kwargs):
        # Upstream's `if "carbon_cycle_outputs" in cfg:` check fires
        # for any value including False. Drop the key when False so
        # we don't pay the carbon-cycle cost we explicitly declined.
        if cfg.get("carbon_cycle_outputs") is False:
            cfg = {k: v for k, v in cfg.items() if k != "carbon_cycle_outputs"}
        return _orig_cscm_run(self, cfg, **kwargs)

    cscmparwrapper.CICEROSCM._run = _patched_cscm_run

    cscmparwrapper._openscm_runner_patches_applied = True
    LOGGER.debug(
        "CICEROSCMPY2: applied upstream carbon-cycle workarounds to "
        "ciceroscm.parallel.cscmparwrapper"
    )
