"""
Adapters for different climate models
"""

from ._protocol import AdapterLike
from .base import _Adapter
from .ciceroscm_adapter import CICEROSCM
from .ciceroscm_py2_adapter import CICEROSCMPY2
from .ciceroscm_py_adapter import CICEROSCMPY
from .fair2_adapter import FAIR2
from .fair_adapter import FAIR
from .magicc7 import MAGICC7

_registered_adapters: list[type[_Adapter]] = [
    CICEROSCM,
    CICEROSCMPY,
    CICEROSCMPY2,
    FAIR,
    FAIR2,
    MAGICC7,
]


def get_adapter(climate_model, **kwargs):
    """
    Get an adapter for a given ``climate_model``.

    Parameters
    ----------
    climate_model: str
        The name of the model to fetch. Case-insensitive.

    **kwargs
        Forwarded to the adapter's constructor. The base
        :class:`~openscm_runner.adapters.base._Adapter` accepts
        ``cfgs``, ``mode``, ``output_variables`` and ``output_config``
        as keyword arguments; concrete adapters may take additional
        kwargs through their constructor. Callers that just want an
        adapter instance for inspection can pass no kwargs.

    Raises
    ------
    NotImplementedError
        A matching adapter could not be found.

    Returns
    -------
    openscm_runner.adapters.base._Adapter
        Configured adapter instance.
    """
    adapters_classes = get_adapters_classes()

    for Adapter in adapters_classes:
        if Adapter.model_name.upper() == climate_model.upper():
            return Adapter(**kwargs)

    raise NotImplementedError(f"No adapter available for {climate_model}")


def get_adapters_classes():
    """
    Get a list of registered adapter classes

    Returns
    -------
    list of Type[:class:`openscm_runner.adapters.base._Adapter`]
    """
    return _registered_adapters


def register_adapter_class(adapter_cls: type[_Adapter]):
    """
    Register a new adapter class

    Parameters
    ----------
    adapter_cls: Type[:class:`openscm_runner.adapters.base._Adapter`]
        Adapter class to register

        Must inherit from openscm_runner :class:`openscm_runner.adapters.base._Adapter` and have a unique `model_name`

    Raises
    ------
    ValueError
        `adapter_cls` does not inherit from :class:`openscm_runner.adapters.base._Adapter`

        Invalid or non unique `model_name`
    """
    existing_names = [a.model_name.upper() for a in _registered_adapters]

    if not issubclass(adapter_cls, _Adapter):
        raise ValueError(
            "Adapter does not inherit from openscm_runner.adapters.base._Adapter"
        )

    if adapter_cls.model_name is None or not isinstance(adapter_cls.model_name, str):
        raise ValueError("Cannot determine model_name")

    if any(adapter_cls.model_name.upper() == name for name in existing_names):
        raise ValueError(
            "An adapter with the same model_name has already been registered"
        )

    _registered_adapters.append(adapter_cls)
