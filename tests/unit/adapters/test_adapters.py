import pytest

from openscm_runner.adapters import (
    get_adapters_classes,
    register_adapter_class,
    _registered_adapters,
)
from openscm_runner.adapters.base import _Adapter


class CustomAdapter(_Adapter):
    model_name = "Custom"


@pytest.fixture()
def custom_adapters():
    # Ensure that the adapter list is cleaned up after each test
    existing_adapters = _registered_adapters.copy()

    yield

    _registered_adapters.clear()
    _registered_adapters.extend(existing_adapters)


def test_register_adapters(custom_adapters):
    assert CustomAdapter not in get_adapters_classes()

    register_adapter_class(CustomAdapter)

    assert CustomAdapter in get_adapters_classes()


# Doesn't inherit _Adapter
class FakeAdapter:
    model_name = "Custom"


# model_name isn't defined
class NoModelNameAdapter(_Adapter):
    pass


@pytest.mark.parametrize(
    "cls,msg",
    [
        (
            FakeAdapter,
            "Adapter does not inherit from openscm_runner.adapters.base._Adapter",
        ),
        (NoModelNameAdapter, "Cannot determine model_name"),
    ],
)
def test_register_adapters_invalid(custom_adapters, cls, msg):
    assert cls not in get_adapters_classes()

    with pytest.raises(ValueError, match=msg):
        register_adapter_class(cls)

    assert cls not in get_adapters_classes()
