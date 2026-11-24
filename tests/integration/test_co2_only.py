"""
Integration tests: CO2-only runs only have CO2 forcing
"""
# When running in a CO2-only mode, there should only be CO2 forcing:
# everything else should be turned off.
#
# This isn't the only way to do CO2-only runs.
# You could also include feedbacks from CO2-driven changes
# (e.g. on CH4 lifetimes, or ozone's response to warming),
# in which case you get some non-CO2 forcing too.
# This test assumes not (see decision B16).
#
# Adapters are made inside the test (not at collection time),
# so an adapter which can't be set up (e.g. MAGICC isn't available)
# only fails its own test.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import pytest

from openscm_runner import (
    OutputSpecs,
    run_co2_concentration_driven_from_cmip6_pre_industrial,
    run_co2_concentration_driven_from_cmip7_pre_industrial,
    run_co2_emission_driven_from_cmip6_pre_industrial,
    run_co2_emission_driven_from_cmip7_pre_industrial,
)

YEARS = list(range(1850, 1850 + 140))

TOTAL_ERF_VARIABLES = (
    "Effective Radiative Forcing",
    "Effective Radiative Forcing|Anthropogenic",
)
"""Outputs which are totals (so include CO2 forcing)"""


def make_1pct_co2_concentrations() -> pd.DataFrame:
    """1pctCO2-style input: CO2 concentrations increasing by 1% per year"""
    values = 284.3 * 1.01 ** np.arange(len(YEARS))
    return pd.DataFrame(
        [values],
        index=pd.MultiIndex.from_tuples(
            [("1pctCO2", "Atmospheric Concentrations|CO2", "World", "ppm")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=YEARS,
    )


def make_flat10_co2_emissions() -> pd.DataFrame:
    """esm-flat10-style input: constant CO2 emissions of 10 GtC/yr"""
    return pd.DataFrame(
        [np.full(len(YEARS), 10.0)],
        index=pd.MultiIndex.from_tuples(
            [("esm-flat10", "Emissions|CO2|Fossil", "World", "GtC/yr")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=YEARS,
    )


def make_magicc_ar6_adapter(adapter_name: str) -> Callable[[], Any]:
    """Get a function which makes a MAGICC AR6 adapter (two ensemble members)"""

    def make() -> Any:
        from openscm_runner.adapters import magicc_ar6  # noqa: PLC0415

        return getattr(magicc_ar6, adapter_name)(
            configuration=magicc_ar6.MAGICCAR6AdapterConfiguration.from_environment(
                testing_only_n_members=2, n_workers=2
            )
        )

    return make


@pytest.mark.parametrize(
    "run, input_kwarg, make_input, make_adapter",
    (
        pytest.param(
            run_co2_concentration_driven_from_cmip7_pre_industrial,
            "co2_concentrations",
            make_1pct_co2_concentrations,
            make_magicc_ar6_adapter(
                "MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial"
            ),
            marks=pytest.mark.magicc_ar6,
            id="magicc-ar6-co2-conc-cmip7",
        ),
        pytest.param(
            run_co2_concentration_driven_from_cmip6_pre_industrial,
            "co2_concentrations",
            make_1pct_co2_concentrations,
            make_magicc_ar6_adapter(
                "MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial"
            ),
            marks=pytest.mark.magicc_ar6,
            id="magicc-ar6-co2-conc-cmip6",
        ),
        pytest.param(
            run_co2_emission_driven_from_cmip7_pre_industrial,
            "co2_emissions",
            make_flat10_co2_emissions,
            make_magicc_ar6_adapter(
                "MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial"
            ),
            marks=pytest.mark.magicc_ar6,
            id="magicc-ar6-co2-emms-cmip7",
        ),
        pytest.param(
            run_co2_emission_driven_from_cmip6_pre_industrial,
            "co2_emissions",
            make_flat10_co2_emissions,
            make_magicc_ar6_adapter(
                "MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial"
            ),
            marks=pytest.mark.magicc_ar6,
            id="magicc-ar6-co2-emms-cmip6",
        ),
    ),
)
def test_co2_only_runs_only_have_co2_forcing(
    run: Callable[..., Any],
    input_kwarg: str,
    make_input: Callable[[], pd.DataFrame],
    make_adapter: Callable[[], Any],
) -> None:
    adapter = make_adapter()
    # Every forcing output the adapter supports
    erf_variables = sorted(
        v
        for v in adapter.supported_output_variables
        if v.startswith("Effective Radiative Forcing")
    )
    results = run(
        **{input_kwarg: (make_input(),)},
        adapters=(adapter,),
        output_specs=OutputSpecs(output_variables=tuple(erf_variables)),
    )

    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output_df = output.as_df()

    co2 = output_df.xs("Effective Radiative Forcing|CO2", level="variable")
    # So the test can't pass trivially
    assert (co2.iloc[:, -1] > 1.0).all()

    # If CO2 is the only forcing, the totals equal CO2 forcing.
    # This catches any other forcing,
    # including forcing the adapter doesn't offer as an output.
    for variable in TOTAL_ERF_VARIABLES:
        np.testing.assert_allclose(
            output_df.xs(variable, level="variable").to_numpy(),
            co2.to_numpy(),
            rtol=1e-10,
            atol=1e-12,
            err_msg=variable,
        )

    # Every other forcing component the adapter offers is zero
    for variable in erf_variables:
        if (
            variable in TOTAL_ERF_VARIABLES
            or variable == "Effective Radiative Forcing|CO2"
        ):
            continue

        np.testing.assert_allclose(
            output_df.xs(variable, level="variable").to_numpy(),
            0.0,
            atol=1e-12,
            err_msg=variable,
        )
