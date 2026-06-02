"""
Compatibility shims for the CICEROSCMPY2 adapter.

The v2.x adapter requires ciceroscm >= 2.0; the v1.1.x adapter
(:mod:`openscm_runner.adapters.ciceroscm_py_adapter`) requires
ciceroscm < 2. Only one major version can be installed in any given
environment; the pyproject extras ``ciceroscmpy`` and ``ciceroscmpy2``
both pull ``ciceroscm`` but are intended to be mutually exclusive at
install time.
"""
# pylint:disable=unused-import
try:
    import ciceroscm as cscmpy2

    HAS_CICEROSCM_PY2 = True
except ImportError:
    cscmpy2 = None  # type: ignore[assignment]
    HAS_CICEROSCM_PY2 = False


def _ciceroscm_major_version() -> int:
    """
    Return the major version of the installed ciceroscm.

    Uses ``importlib.metadata`` rather than ``ciceroscm.__version__``
    because ciceroscm's runtime ``__version__`` is a setuptools_scm dev
    string (e.g. ``"0+untagged.798.gabc1234.dirty"``) that does not
    reflect the package's PyPI release version.
    """
    if not HAS_CICEROSCM_PY2:
        raise ImportError("ciceroscm is not installed")
    from importlib.metadata import PackageNotFoundError, version

    try:
        return int(version("ciceroscm").split(".")[0])
    except (PackageNotFoundError, ValueError):
        return 0
