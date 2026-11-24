"""
Handling of optional dependencies
"""

from __future__ import annotations

import importlib
from typing import Any


class MissingOptionalDependencyError(ImportError):
    """Raised when an optional dependency isn't installed"""

    def __init__(
        self, callable_name: str, requirement: str, *, extra: str | None = None
    ) -> None:
        msg = f"`{callable_name}` requires {requirement} to be installed"
        if extra is not None:
            msg = f"{msg} (e.g. `pip install 'openscm-runner[{extra}]'`)"

        super().__init__(msg)


def import_optional_dependency(
    module: str, *, requirement: str, callable_name: str, extra: str | None = None
) -> Any:
    """
    Import an optional dependency

    Parameters
    ----------
    module
        Module to import (e.g. `"openscm_units"`)

    requirement
        Name of the package that provides the module (e.g. `"openscm-units"`)

    callable_name
        Name of the callable that needs the module (used in the error message)

    extra
        Optional extra of `openscm-runner` which installs the module
        (e.g. `"magicc-ar6"`, used in the error message)

    Returns
    -------
    :
        The imported module

    Raises
    ------
    MissingOptionalDependencyError
        The module isn't installed
    """
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            callable_name, requirement=requirement, extra=extra
        ) from exc
