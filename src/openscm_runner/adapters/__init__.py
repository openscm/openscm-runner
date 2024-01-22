"""
Adapters for different climate models
"""

from .base import _Adapter
from .ciceroscm_adapter import CICEROSCM
from .ciceroscm_py_adapter import CICEROSCMPY
from .fair_adapter import FAIR
from .magicc7 import MAGICC7

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
