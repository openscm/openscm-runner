"""
Module supporting the CICERO-SCM v2.x Python adapter.

Sibling to :mod:`openscm_runner.adapters.ciceroscm_py_adapter` (which
wraps CICERO-SCM v1.1.x via a per-config loop). This package targets
v2.1.0's native parameter-distribution API (``DistributionRun``) and
exposes the v2.x ensemble as a single adapter call.
"""
from ._upstream_patches import apply_upstream_patches as _apply
from .ciceroscmpy2_adapter import CICEROSCMPY2  # noqa: F401

# Apply upstream carbon-cycle perf workarounds at import time. With
# fork-mode multiprocessing on macOS, subprocesses inherit these
# patches; with spawn-mode the workers re-import this package and
# re-apply automatically. See _upstream_patches.py for the full bug
# description (concentrations_emissions_handler.py uses a key-presence
# check on `carbon_cycle_outputs`, so passing the key with any value
# - including False - triggers ~30x slowdown on conc-driven runs).
_apply()
