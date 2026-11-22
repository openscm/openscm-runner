import sys
import textwrap

import pytest

import openscm_runner.adapters
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
    openscm_runner.adapters._load_entry_point_adapters.cache_clear()

    yield

    _registered_adapters.clear()
    _registered_adapters.extend(existing_adapters)
    openscm_runner.adapters._load_entry_point_adapters.cache_clear()


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


class _FakeEntryPoint:
    def __init__(self, name, value, loaded):
        self.name = name
        self.value = value
        self._loaded = loaded

    def load(self):
        if isinstance(self._loaded, Exception):
            raise self._loaded

        return self._loaded


@pytest.fixture()
def installed_plugin(tmp_path, monkeypatch):
    (tmp_path / "fake_scm_plugin.py").write_text(
        textwrap.dedent(
            """
            from openscm_runner.adapters.base import _Adapter


            class PluginAdapter(_Adapter):
                model_name = "PluginModel"

                def _init_model(self, *args, **kwargs):
                    pass

                def _run(self, scenarios, cfgs, output_variables, output_config):
                    pass
            """
        )
    )
    dist_info = tmp_path / "fake_scm_plugin-0.1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: fake-scm-plugin\nVersion: 0.1.0\n"
    )
    (dist_info / "entry_points.txt").write_text(
        "[openscm_runner.adapters]\nplugin-model = fake_scm_plugin:PluginAdapter\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    yield

    sys.modules.pop("fake_scm_plugin", None)


def test_entry_point_adapter_from_installed_package(custom_adapters, installed_plugin):
    adapter = get_adapter("pluginmodel")

    assert type(adapter).__name__ == "PluginAdapter"
    assert type(adapter).__module__ == "fake_scm_plugin"
    assert MAGICC7 in get_adapters_classes()


def test_entry_point_adapters_load_once(custom_adapters, monkeypatch):
    calls = []

    def fake_entry_points():
        calls.append(1)
        return [_FakeEntryPoint("custom", "tests:CustomAdapter", CustomAdapter)]

    monkeypatch.setattr(openscm_runner.adapters, "_entry_points", fake_entry_points)

    get_adapters_classes()
    get_adapters_classes()
    get_adapter("custom")

    assert len(calls) == 1
    assert get_adapters_classes().count(CustomAdapter) == 1


@pytest.mark.parametrize(
    "loaded,msg",
    [
        (ImportError("No module named 'missing'"), "No module named 'missing'"),
        (FakeAdapter, "does not inherit from"),
        (len, "does not inherit from"),
        (MAGICC7, "same model_name has already been registered"),
    ],
)
def test_entry_point_adapter_invalid_warns(custom_adapters, monkeypatch, loaded, msg):
    monkeypatch.setattr(
        openscm_runner.adapters,
        "_entry_points",
        lambda: [
            _FakeEntryPoint("broken", "broken:Adapter", loaded),
            _FakeEntryPoint("custom", "tests:CustomAdapter", CustomAdapter),
        ],
    )
    existing = _registered_adapters.copy()

    with pytest.warns(UserWarning, match=f"'broken' \\(broken:Adapter\\).*{msg}"):
        classes = get_adapters_classes()

    assert classes == [*existing, CustomAdapter]


def test_entry_point_adapters_load_before_manual_registration(
    custom_adapters, monkeypatch
):
    class ClashingAdapter(CustomAdapter):
        pass

    monkeypatch.setattr(
        openscm_runner.adapters,
        "_entry_points",
        lambda: [_FakeEntryPoint("custom", "tests:CustomAdapter", CustomAdapter)],
    )

    with pytest.raises(ValueError, match="same model_name"):
        register_adapter_class(ClashingAdapter)

    assert isinstance(get_adapter("custom"), CustomAdapter)
    assert ClashingAdapter not in get_adapters_classes()
