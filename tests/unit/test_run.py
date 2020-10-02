import re

import pytest

from openscm_runner import run


def test_run_out_config_conflict_error():
    error_msg = re.escape(
        "Found model(s) in `out_config` which are not in "
        "`climate_models_cfgs`: {'another model'}"
    )
    with pytest.raises(KeyError, match=error_msg):
        run(
            climate_models_cfgs={"model_a": ["config list"]},
            scenarios="not used",
            out_config={"another model": ("hi")}
        )
