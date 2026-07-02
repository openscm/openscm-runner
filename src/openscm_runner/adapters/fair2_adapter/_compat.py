"""
Handling of compatibility of fair imports with different states of installation.

The FaIR 2.x adapter requires the ``fair`` package at version 2.x. The
existing FaIR 1.6 adapter (``openscm_runner.adapters.fair_adapter``)
declares the same package at ``<2``. Both extras therefore should not
be installed together; the runtime check below selects whichever is
present and lets the other adapter raise its own ImportError if it
isn't.
"""
# pylint:disable=unused-import
try:
    import fair as fair2

    _major = int(fair2.__version__.split(".")[0])
    if _major < 2:  # noqa: PLR2004
        # FaIR 1.6 is installed; the FaIR2 adapter cannot use it.
        fair2 = None
        HAS_FAIR2 = False
    else:
        HAS_FAIR2 = True
except ImportError:
    fair2 = None
    HAS_FAIR2 = False
