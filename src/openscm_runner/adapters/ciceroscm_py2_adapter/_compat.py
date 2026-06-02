"""
Compatibility shims for the CICEROSCMPY2 adapter.

The v2.x adapter requires ciceroscm >= 2.0; the v1.1.x adapter
(:mod:`openscm_runner.adapters.ciceroscm_py_adapter`) requires
ciceroscm < 2. Only one major version can be installed in any given
environment; the pyproject extras ``ciceroscmpy`` and ``ciceroscmpy2``
both pull ``ciceroscm`` but are intended to be mutually exclusive at
install time.
"""
def _ciceroscm_major_version() -> int:
    """
    Return the major version of the installed ciceroscm.

    Uses ``importlib.metadata`` rather than ``ciceroscm.__version__``
    because ciceroscm's runtime ``__version__`` is a setuptools_scm dev
    string (e.g. ``"0+untagged.798.gabc1234.dirty"``) that does not
    reflect the package's PyPI release version.

    Returns 0 if the metadata can't be read for any reason; callers
    should treat 0 as "not the v2.x major we want".
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return int(version("ciceroscm").split(".")[0])
    except (PackageNotFoundError, ValueError):
        return 0


# pylint:disable=unused-import
try:
    import ciceroscm as cscmpy2

    if _ciceroscm_major_version() < 2:  # noqa: PLR2004
        # ciceroscm 1.x is installed; the v2.x adapter cannot use it.
        # Mirror the FaIR2 `_compat` shim's behaviour so
        # `HAS_CICEROSCM_PY2` is a single source of truth for "is the
        # modern adapter actually usable?" — same semantic as
        # `HAS_FAIR2`. Callers can rely on `if not HAS_CICEROSCM_PY2`
        # alone without a follow-up version check.
        cscmpy2 = None  # type: ignore[assignment]
        HAS_CICEROSCM_PY2 = False
    else:
        HAS_CICEROSCM_PY2 = True
except ImportError:
    cscmpy2 = None  # type: ignore[assignment]
    HAS_CICEROSCM_PY2 = False
