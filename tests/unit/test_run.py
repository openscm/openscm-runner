import re

import pytest

from openscm_runner import run


def test_run_out_config_conflict_error():
    error_msg = re.escape(
        "Found model(s) in `out_config` which are not in "
        "`climate_models_cfgs`: {'another model'}"
    )
    with pytest.raises(NotImplementedError):
        with pytest.warns(UserWarning, match=error_msg):
            run(
                climate_models_cfgs={"model_a": ["config list"]},
                scenarios="not used",
                out_config={"another model": ("hi",)},
            )


def test_run_out_config_type_error():
    error_msg = re.escape(
        "`out_config` values must be tuples, this isn't the case for "
        "climate_model: 'model_a'"
    )
    with pytest.raises(TypeError, match=error_msg):
        run(
            climate_models_cfgs={"model_a": ["config list"]},
            scenarios="not used",
            out_config={"model_a": "hi"},
        )
