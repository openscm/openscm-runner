import logging
import re

import pandas as pd
import pytest
import scmdata

import openscm_runner.run
from openscm_runner.adapters import _registered_adapters, register_adapter_class
from openscm_runner.adapters.base import _Adapter


def test_run_out_config_conflict_error(caplog):
    expected_log = (
        "Found model(s) in `out_config` which are not in "
        "`climate_models_cfgs`: {'another model'}"
    )
    with caplog.at_level(logging.WARNING, logger="openscm_runner.run"):
        with pytest.raises(NotImplementedError):
            openscm_runner.run.run(
                climate_models_cfgs={"model_a": ["config list"]},
                scenarios=_dummy_scenarios(),
                out_config={"another model": ("hi",)},
            )

    assert expected_log in caplog.text


def test_run_out_config_type_error():
    error_msg = re.escape(
        "`out_config` values must be tuples, this isn't the case for "
        "climate_model: 'model_a'"
    )
    with pytest.raises(TypeError, match=error_msg):
        openscm_runner.run.run(
            climate_models_cfgs={"model_a": ["config list"]},
            scenarios="not used",
            out_config={"model_a": "hi"},
        )


def test_run_rejects_unknown_emissions_variables(test_scenarios):
    # Surface unknown emissions variable names at the wrapper boundary
    # rather than have each adapter silently drop them.
    bad = test_scenarios.filter(scenario="ssp245").copy()
    bad["variable"] = [
        "Emissions|CO2|AFOLU [NGHGI]" if v == "Emissions|CO2|MAGICC AFOLU" else v
        for v in bad["variable"]
    ]
    with pytest.raises(ValueError, match="Unknown emissions variable"):
        openscm_runner.run.run(
            climate_models_cfgs={"model_a": [{}]},
            scenarios=bad,
        )


def _dummy_scenarios():
    """A minimal ScmRun the wrapper's input validation accepts.

    Has a single ``Surface Temperature`` row -- the variable doesn't
    start with ``Emissions|`` so ``check_variables_are_as_expected``
    no-ops, and the object satisfies the
    "``scenarios is not None`` and exposes
    ``.get_unique_meta('variable')``" contract that the wrapper enforces
    since PR97. Dummy-adapter tests use this because the
    :class:`_DummyAdapterA` / ``B`` ``_run`` methods don't actually
    consume scenarios; they just need the input-validation pre-check
    to pass.
    """
    return scmdata.ScmRun(
        pd.DataFrame(
            {
                "scenario": ["dummy"],
                "model": ["dummy"],
                "region": ["World"],
                "variable": ["Surface Temperature"],
                "unit": ["K"],
                2020: [0.0],
            }
        )
    )


def _dummy_result(climate_model):
    return scmdata.ScmRun(
        pd.DataFrame(
            [[1.0, 2.0]],
            index=pd.MultiIndex.from_tuples(
                [
                    (
                        climate_model,
                        "test_scen",
                        "test_iam",
                        "World",
                        "Surface Temperature",
                        "K",
                        0,
                    )
                ],
                names=[
                    "climate_model",
                    "scenario",
                    "model",
                    "region",
                    "variable",
                    "unit",
                    "run_id",
                ],
            ),
            columns=[2020, 2021],
        )
    )


class _DummyAdapterA(_Adapter):
    model_name = "DummyA"

    def _init_model(self, *args, **kwargs):
        pass

    def _run(self, scenarios, cfgs, output_variables, output_config):
        return _dummy_result("DummyA")


class _DummyAdapterB(_Adapter):
    model_name = "DummyB"

    def _init_model(self, *args, **kwargs):
        pass

    def _run(self, scenarios, cfgs, output_variables, output_config):
        return _dummy_result("DummyB")


@pytest.fixture()
def dummy_adapters():
    existing = _registered_adapters.copy()
    register_adapter_class(_DummyAdapterA)
    register_adapter_class(_DummyAdapterB)
    yield
    _registered_adapters.clear()
    _registered_adapters.extend(existing)


def test_serial_dispatch_runs_each_model(dummy_adapters):
    res = openscm_runner.run.run(
        climate_models_cfgs={"DummyA": [{}], "DummyB": [{}]},
        scenarios=_dummy_scenarios(),
        parallel_models=False,
    )
    assert set(res["climate_model"]) == {"DummyA", "DummyB"}


def test_parallel_models_single_model_skips_pool(dummy_adapters, monkeypatch):
    pool_calls = []

    def _spy(*args, **kwargs):
        pool_calls.append((args, kwargs))
        raise AssertionError(
            "ProcessPoolExecutor should not be constructed for a single-model run"
        )

    monkeypatch.setattr("openscm_runner.run.ProcessPoolExecutor", _spy)

    res = openscm_runner.run.run(
        climate_models_cfgs={"DummyA": [{}]},
        scenarios=_dummy_scenarios(),
        parallel_models=True,
    )

    assert res["climate_model"].iloc[0] == "DummyA"
    assert pool_calls == []


def test_parallel_dispatch_uses_process_pool(dummy_adapters, monkeypatch):
    """
    Verify that parallel_models=True with >1 model routes through
    ProcessPoolExecutor. We do not actually fork: we substitute a fake pool
    that runs submitted tasks in-process. This keeps the test deterministic
    across platforms (macOS uses the spawn start method, which would not
    inherit our runtime-registered dummy adapters).
    """
    captured = {}

    class _FakeFuture:
        def __init__(self, func, args):
            self._func = func
            self._args = args

        def result(self):
            return self._func(*self._args)

    class _FakePool:
        def __init__(self, max_workers):
            captured["max_workers"] = max_workers
            captured["submitted"] = []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, func, *args):
            captured["submitted"].append((func.__name__, args[0]))
            return _FakeFuture(func, args)

    monkeypatch.setattr("openscm_runner.run.ProcessPoolExecutor", _FakePool)

    res = openscm_runner.run.run(
        climate_models_cfgs={"DummyA": [{}], "DummyB": [{}]},
        scenarios=_dummy_scenarios(),
        parallel_models=True,
    )

    assert captured["max_workers"] == 2
    assert [name for name, _ in captured["submitted"]] == [
        "_run_one_adapter",
        "_run_one_adapter",
    ]
    assert sorted(model for _, model in captured["submitted"]) == ["DummyA", "DummyB"]
    assert set(res["climate_model"]) == {"DummyA", "DummyB"}


def test_max_model_workers_caps_pool_size(dummy_adapters, monkeypatch):
    captured = {}

    class _FakePool:
        def __init__(self, max_workers):
            captured["max_workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, func, *args):
            class _Fut:
                def result(self_inner):  # noqa: N805
                    return func(*args)

            return _Fut()

    monkeypatch.setattr("openscm_runner.run.ProcessPoolExecutor", _FakePool)

    openscm_runner.run.run(
        climate_models_cfgs={"DummyA": [{}], "DummyB": [{}]},
        scenarios=_dummy_scenarios(),
        parallel_models=True,
        max_model_workers=1,
    )

    assert captured["max_workers"] == 1
