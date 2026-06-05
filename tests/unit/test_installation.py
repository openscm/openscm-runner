from unittest.mock import patch

import pandas as pd
import pytest
import scmdata

import openscm_runner.run


def _dummy_scenarios():
    """Minimal ScmRun that passes the wrapper's input validation.

    A single ``Surface Temperature`` row -- doesn't start with
    ``Emissions|`` so ``check_variables_are_as_expected`` no-ops,
    and the object satisfies the ``.get_unique_meta('variable')``
    contract the wrapper enforces. The dummy is enough for the
    missing-package tests below; they fail later inside
    ``get_adapter`` rather than at scenarios validation.
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


@patch("openscm_runner.adapters.fair_adapter.fair_adapter.fair", None)
def test_no_fair():
    with pytest.raises(
        ImportError, match="fair is not installed. Run 'pip install fair'"
    ):
        openscm_runner.run.run(
            climate_models_cfgs={"fair": ["config list"]},
            scenarios=_dummy_scenarios(),
        )


@patch("openscm_runner.adapters.magicc7.magicc7.pymagicc", None)
def test_no_pymagicc():
    with pytest.raises(
        ImportError,
        match=(
            "pymagicc is not installed. "
            "Run 'conda install pymagicc' or 'pip install pymagicc'"
        ),
    ):
        openscm_runner.run.run(
            climate_models_cfgs={"MAGICC7": ["config list"]},
            scenarios=_dummy_scenarios(),
        )
