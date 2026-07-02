"""
Module supporting the CICERO-SCM v2.x Python adapter.

Sibling to :mod:`openscm_runner.adapters.ciceroscm_py_adapter` (which
wraps CICERO-SCM v1.1.x via a per-config loop). This package targets
v2.1.1's native parameter-distribution API (``DistributionRun``) and
exposes the v2.x ensemble as a single adapter call. The 2.1.1 floor
is enforced at runtime by :func:`._compat.require_modern_ciceroscm`
and is the version where upstream fixed the carbon-cycle gating
bug; earlier 2.0.1 / 2.1.0 releases ran the ~30x carbon-cycle
back-calculation on every conc-driven cfg regardless of whether
its output was requested.
"""
from .ciceroscmpy2_adapter import CICEROSCMPY2  # noqa: F401
