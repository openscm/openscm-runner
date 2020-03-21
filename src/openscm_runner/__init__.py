"""
OpenSCM-Runner, a thin wrapper to run simple climate models with a unified interface.

See README and docs for more info.
"""
from ._version import get_versions
from .run import run  # noqa: F401

__version__ = get_versions()["version"]
del get_versions
