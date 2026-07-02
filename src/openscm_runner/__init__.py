"""
Thin wrapper to run emissions scenarios with simple climate models.
"""
import importlib.metadata

from ._run_mode import RunMode
from ._variables import (
    KNOWN_EMISSIONS_VARIABLES,
    check_variables_are_as_expected,
)

__version__ = importlib.metadata.version(__package__)

__all__ = [
    "KNOWN_EMISSIONS_VARIABLES",
    "RunMode",
    "__version__",
    "check_variables_are_as_expected",
]
