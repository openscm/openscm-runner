"""
Integration tests: zero ERF in gives zero out
"""
# Adapters are made inside the test (not at collection time),
# so an adapter which can't be set up (e.g. MAGICC isn't available)
# only fails its own test.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import pytest

from openscm_runner import OutputSpecs, run_erf_driven_from_equilibrium


def make_zero_erf() -> pd.DataFrame:
    """Zero ERF input (start year is arbitrary)"""
    years = list(range(1750, 2101))
    return pd.DataFrame(
        [np.zeros(len(years))],
        index=pd.MultiIndex.from_tuples(
            [("zero-erf", "Effective Radiative Forcing", "World", "W/m^2")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=years,
    )


def make_magicc_ar6_adapter() -> Any:
    """Make the MAGICC AR6 adapter (with two ensemble members, for speed)"""
    from openscm_runner.adapters.magicc_ar6 import (  # noqa: PLC0415
        MAGICCAR6AdapterConfiguration,
        MAGICCAR6AdapterERFDrivenFromEquilibrium,
    )

    return MAGICCAR6AdapterERFDrivenFromEquilibrium(
        configuration=MAGICCAR6AdapterConfiguration.from_environment(
            testing_only_n_members=2,
            # Faster than two workers for two members (~0.8s vs ~1.0s)
            n_workers=1,
        )
    )


@pytest.mark.parametrize(
    "make_adapter",
    (
        pytest.param(
            make_magicc_ar6_adapter,
            marks=pytest.mark.magicc_ar6,
            id="magicc-ar6-erf-from-equilibrium",
        ),
    ),
)
def test_zero_erf_gives_zero_outputs(make_adapter: Callable[[], Any]) -> None:
    adapter = make_adapter()
    results = run_erf_driven_from_equilibrium(
        (make_zero_erf(),),
        adapters=(adapter,),
        # Every output the adapter supports
        output_specs=OutputSpecs(
            output_variables=tuple(sorted(adapter.supported_output_variables))
        ),
    )

    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    output_df = output.as_df()

    assert not output_df.empty
    np.testing.assert_allclose(output_df.to_numpy(), 0.0, atol=1e-12)
