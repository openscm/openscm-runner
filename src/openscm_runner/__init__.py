"""
OpenSCM-Runner, a thin wrapper to run simple climate models with a unified interface.

See README and docs for more info.
"""
from .run import run  # noqa: F401

try:
    from importlib.metadata import version as _version
except ImportError:
    # no recourse if the fallback isn't there either...
    from importlib_metadata import version as _version

try:
    __version__ = _version("openscm_runner")
except Exception:  # pylint: disable=broad-except
    # Local copy, not installed with setuptools
    __version__ = "unknown"
