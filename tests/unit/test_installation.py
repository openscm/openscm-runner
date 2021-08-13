from unittest.mock import patch

import pytest

from openscm_runner import run


@patch("openscm_runner.adapters.fair_adapter.fair_adapter.fair", None)
def test_no_fair():
    with pytest.raises(
        ImportError, match="fair is not installed. Run 'pip install fair'"
    ):
        run(
            climate_models_cfgs={"fair": ["config list"]}, scenarios="not used",
        )


@patch("openscm_runner.adapters.magicc7.magicc7.pymagicc", None)
def test_no_pymagicc():
    with pytest.raises(
        ImportError,
        match="pymagicc is not installed. Run 'conda install pymagicc' or 'pip install pymagicc'",
    ):
        run(
            climate_models_cfgs={"MAGICC7": ["config list"]}, scenarios="not used",
        )
