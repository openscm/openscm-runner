"""
Adapters for different climate models

Packages outside OpenSCM-Runner can provide adapters
by declaring an entry point in the ``openscm_runner.adapters`` group,
for example in their ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."openscm_runner.adapters"]
    my-model = "my_package.adapter:MyModelAdapter"

The entry point must load a subclass of
:class:`openscm_runner.adapters.base._Adapter`.
Entry points are loaded the first time the registered adapters are requested.
"""

import functools
import sys
import warnings
from collections.abc import Iterable
from importlib.metadata import EntryPoint, entry_points

from .base import _Adapter
from .ciceroscm_adapter import CICEROSCM
from .ciceroscm_py_adapter import CICEROSCMPY
from .fair_adapter import FAIR
from .magicc7 import MAGICC7

_ENTRY_POINT_GROUP = "openscm_runner.adapters"

_registered_adapters: list[type[_Adapter]] = [
    CICEROSCM,
    CICEROSCMPY,
    FAIR,
    MAGICC7,
]


def get_adapter(climate_model):
    """
    Get an adapter for a given climate_model

    Parameters
    ----------
    climate_model: str
        The name of the model to fetch

        This parameter is case-insensitive

    Raises
    ------
    NotImplementedError
        A matching adapter could not be found

    Returns
    -------
    openscm_runner.adapters.base._Adapter
        The adapter for a given climate model
    """
    adapters_classes = get_adapters_classes()

    for Adapter in adapters_classes:
        if Adapter.model_name.upper() == climate_model.upper():
            return Adapter()

    raise NotImplementedError(f"No adapter available for {climate_model}")


def get_adapters_classes():
    """
    Get a list of registered adapter classes

    This includes adapters provided through the ``openscm_runner.adapters``
    entry point group.

    Returns
    -------
    list of Type[:class:`openscm_runner.adapters.base._Adapter`]
    """
    _load_entry_point_adapters()

    return _registered_adapters


def register_adapter_class(adapter_cls: type[_Adapter]):
    """
    Register a new adapter class

    Parameters
    ----------
    adapter_cls: Type[:class:`openscm_runner.adapters.base._Adapter`]
        Adapter class to register

        Must inherit from :class:`openscm_runner.adapters.base._Adapter`
        and have a unique `model_name`

    Raises
    ------
    ValueError
        `adapter_cls` does not inherit from
        :class:`openscm_runner.adapters.base._Adapter`

        Invalid or non unique `model_name`
    """
    _load_entry_point_adapters()
    _register(adapter_cls)


def _register(adapter_cls: type[_Adapter]) -> None:
    existing_names = [a.model_name.upper() for a in _registered_adapters]

    if not (isinstance(adapter_cls, type) and issubclass(adapter_cls, _Adapter)):
        raise ValueError(  # noqa: TRY003, TRY004
            "Adapter does not inherit from openscm_runner.adapters.base._Adapter"
        )

    if adapter_cls.model_name is None or not isinstance(adapter_cls.model_name, str):
        raise ValueError("Cannot determine model_name")  # noqa: TRY003

    if any(adapter_cls.model_name.upper() == name for name in existing_names):
        raise ValueError(  # noqa: TRY003
            "An adapter with the same model_name has already been registered"
        )

    _registered_adapters.append(adapter_cls)


def _entry_points() -> Iterable[EntryPoint]:
    if sys.version_info >= (3, 10):
        return entry_points(group=_ENTRY_POINT_GROUP)

    return entry_points().get(_ENTRY_POINT_GROUP, ())


@functools.cache
def _load_entry_point_adapters() -> None:
    """
    Register the adapters declared in the ``openscm_runner.adapters`` group

    Only runs once per process.
    An entry point that fails to load or register is skipped with a warning,
    so that one broken package does not stop the other models from running.
    """
    for ep in _entry_points():
        try:
            _register(ep.load())
        except Exception as exc:
            warnings.warn(
                f"Could not register the adapter from entry point "
                f"{ep.name!r} ({ep.value}): {exc}",
                stacklevel=2,
            )
