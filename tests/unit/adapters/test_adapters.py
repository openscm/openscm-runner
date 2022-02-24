import pytest

from openscm_runner.adapters import (
    MAGICC7,
    _registered_adapters,
    get_adapter,
    get_adapters_classes,
    register_adapter_class,
)
from openscm_runner.adapters.base import _Adapter


class CustomAdapter(_Adapter):
    model_name = "Custom"

    def _init_model(self, *args, **kwargs):
        pass

    def _run(self, scenarios, cfgs, output_variables, output_config):
        pass


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


def test_registering_existing_adapter(custom_adapters):
    msg = "An adapter with the same model_name has already been registered"
    with pytest.raises(ValueError, match=msg):
        register_adapter_class(MAGICC7)


def test_get_adapter(custom_adapters):
    msg = "No adapter available for custom"
    with pytest.raises(NotImplementedError, match=msg):
        get_adapter("custom")

    register_adapter_class(CustomAdapter)

    adapter = get_adapter("custom")

    assert isinstance(adapter, CustomAdapter)
