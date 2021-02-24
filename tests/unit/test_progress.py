from tqdm.autonotebook import tqdm

from openscm_runner.progress import _default_tqdm_params, progress


def test_progress(monkeypatch):
    items = range(10)

    iterable = progress(items)

    assert isinstance(iterable, tqdm)
    assert iterable.mininterval == 5
    assert iterable.unit == "it"

    monkeypatch.setitem(_default_tqdm_params, "mininterval", 2)

    iterable = progress(items)
    assert iterable.mininterval == 2


def test_progress_disable(monkeypatch):
    items = range(10)

    monkeypatch.setitem(_default_tqdm_params, "disable", True)

    iterable = progress(items)
    assert iterable.disable
