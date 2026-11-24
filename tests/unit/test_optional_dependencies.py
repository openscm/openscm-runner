"""
Tests of `openscm_runner.optional_dependencies`
"""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest

from openscm_runner.optional_dependencies import (
    MissingOptionalDependencyError,
    import_optional_dependency,
)


@pytest.fixture
def missing_module(monkeypatch: pytest.MonkeyPatch) -> str:
    """Make importing a module (which is installed) fail"""
    module = "json"
    real_import_module = importlib.import_module

    def import_module(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == module:
            raise ImportError(name)

        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", import_module)

    return module


def test_import_optional_dependency() -> None:
    res = import_optional_dependency("json", requirement="json", callable_name="caller")

    assert res is json


def test_missing_optional_dependency(missing_module: str) -> None:
    with pytest.raises(
        MissingOptionalDependencyError,
        match=r"^`caller` requires a-package to be installed$",
    ):
        import_optional_dependency(
            missing_module, requirement="a-package", callable_name="caller"
        )


def test_missing_optional_dependency_with_extra(missing_module: str) -> None:
    with pytest.raises(
        MissingOptionalDependencyError,
        match=(
            r"^`caller` requires a-package to be installed "
            r"\(e\.g\. `pip install 'openscm-runner\[an-extra\]'`\)$"
        ),
    ):
        import_optional_dependency(
            missing_module,
            requirement="a-package",
            callable_name="caller",
            extra="an-extra",
        )
