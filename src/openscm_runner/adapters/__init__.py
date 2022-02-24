"""
Adapters for different climate models
"""
from .ciceroscm_adapter import CICEROSCM  # noqa: F401
from .fair_adapter import FAIR  # noqa: F401
from .magicc7 import MAGICC7  # noqa: F401

_registered_adapters = [CICEROSCM, FAIR, MAGICC7]


def get_adapters_classes():
    return _registered_adapters


def register_adapter_class(adapter_cls):
    existing_names = [a.model_name.upper() for a in _registered_adapters]

    if any([adapter_cls.model_name.upper() == name for name in existing_names]):
        raise ValueError(
            "An adapter with the same model_name has already been registered"
        )

    _registered_adapters.append(adapter_cls)
