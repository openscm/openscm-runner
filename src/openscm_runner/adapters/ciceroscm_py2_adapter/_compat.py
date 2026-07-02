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


def _ciceroscm_version_tuple() -> tuple[int, ...]:
    """Return the installed ciceroscm version as a tuple of ints, or ``(0,)``."""
    if not HAS_CICEROSCM_PY2:
        raise ImportError("ciceroscm is not installed")
    from importlib.metadata import PackageNotFoundError, version

    try:
        return tuple(
            int(p) for p in version("ciceroscm").split(".")[:3] if p.isdigit()
        )
    except (PackageNotFoundError, ValueError):
        return (0,)


def require_modern_ciceroscm() -> None:
    """Raise :class:`ImportError` unless the installed ciceroscm is >= 2.1.1.

    The CICEROSCMPY2 adapter targets ciceroscm v2.1.1+, which is where
    the carbon-cycle gating bug (``"carbon_cycle_outputs" in cfg`` ->
    ``cfg.get("carbon_cycle_outputs")``) was fixed upstream. Earlier
    2.0.1 / 2.1.0 releases run the ~30x carbon-cycle back-calculation
    on every conc-driven cfg regardless of whether its output was
    requested; the previous adapter shipped monkey-patches in
    ``_upstream_patches.py`` to work around that, but the patches now
    target code that no longer exists upstream and are a maintenance
    liability. Pinning the floor at 2.1.1 lets the adapter delete the
    patches and trust the upstream fix.
    """
    if not HAS_CICEROSCM_PY2:
        raise ImportError(
            "ciceroscm is not installed. Run "
            "'pip install \"ciceroscm>=2.1.1,<3\"' "
            "or 'pip install openscm-runner[ciceroscmpy2]'."
        )
    ver = _ciceroscm_version_tuple()
    if ver < (2, 1, 1):
        raise ImportError(
            f"CICEROSCMPY2 adapter requires ciceroscm >= 2.1.1; found "
            f"{'.'.join(str(p) for p in ver)}. Upgrade with "
            "'pip install --upgrade \"ciceroscm>=2.1.1,<3\"'. The 2.1.1 "
            "floor exists because earlier 2.0.1 / 2.1.0 releases ship a "
            "carbon-cycle gating bug that makes conc-driven runs "
            "~30x slower than necessary."
        )
