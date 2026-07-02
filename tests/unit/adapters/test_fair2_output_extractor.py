"""Equivalence tests for the FaIR2 forcing-aggregation fast path.

The extractor materialises FaIR's forcing DataArray to numpy once and
aggregates per (scenario, member) with integer indexing, instead of
repeated xarray ``.sel().isel()`` orthogonal indexing (the dominant cost
for large ensembles). These tests pin that the numpy path is numerically
identical to a direct xarray reduction over the same species.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

xr = pytest.importorskip("xarray")

from openscm_runner.adapters.fair2_adapter._output_extractor import (  # noqa: E402
    _build_forcing_aggregations,
    _forcing_to_numpy,
    _sum_forcing_over,
)

SPECIES = [
    "CO2", "CH4", "N2O", "HFC-134a", "CF4", "CFC-11",
    "Aerosol-radiation interactions", "Aerosol-cloud interactions",
    "Ozone", "Solar", "Volcanic",
]


def _synthetic_forcing(n_t=10, n_scen=2, n_cfg=5, seed=0):
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((n_t, n_scen, n_cfg, len(SPECIES)))
    return xr.DataArray(
        data,
        dims=("timebounds", "scenario", "config", "specie"),
        coords={
            "timebounds": np.arange(1750, 1750 + n_t),
            "scenario": [f"s{i}" for i in range(n_scen)],
            "config": np.arange(n_cfg),
            "specie": SPECIES,
        },
    )


def _properties_df():
    ghg = {"CO2", "CH4", "N2O", "HFC-134a", "CF4", "CFC-11"}
    types = {
        "HFC-134a": "f-gas", "CF4": "f-gas", "CFC-11": "cfc-11",
    }
    return pd.DataFrame(
        {
            "greenhouse_gas": [s in ghg for s in SPECIES],
            "type": [types.get(s, "other") for s in SPECIES],
        },
        index=SPECIES,
    )


def _xarray_sum(da, sc_idx, member, species_list):
    present = [s for s in species_list if s in da["specie"].values]
    if not present:
        return None
    return (
        da.sel(specie=present)
        .isel(scenario=sc_idx, config=member)
        .sum(dim="specie")
        .values
    )


def test_sum_forcing_over_matches_xarray():
    da = _synthetic_forcing()
    forcing_np, species_index = _forcing_to_numpy(da)
    for sc_idx in range(da.sizes["scenario"]):
        for member in range(da.sizes["config"]):
            for species_list in (
                ["CO2", "CH4", "N2O"],
                ["HFC-134a", "CF4"],
                ["Solar", "Volcanic"],
                ["not-a-species"],  # empty intersection -> None
            ):
                got = _sum_forcing_over(
                    forcing_np, species_index, sc_idx, member, species_list
                )
                ref = _xarray_sum(da, sc_idx, member, species_list)
                if ref is None:
                    assert got is None
                else:
                    np.testing.assert_array_equal(got, ref)


def test_build_forcing_aggregations_matches_xarray():
    da = _synthetic_forcing(seed=1)
    props = _properties_df()
    forcing_np, species_index = _forcing_to_numpy(da)
    species_in_run = list(da["specie"].values)

    for sc_idx in range(da.sizes["scenario"]):
        for member in range(da.sizes["config"]):
            out = _build_forcing_aggregations(
                forcing_np, species_index, species_in_run, sc_idx, member, props
            )
            erf = "Effective Radiative Forcing"

            # Total anthropogenic = all species minus Solar/Volcanic.
            total = _xarray_sum(da, sc_idx, member, species_in_run)
            natural = _xarray_sum(da, sc_idx, member, ["Solar", "Volcanic"])
            np.testing.assert_allclose(
                out[f"{erf}|Anthropogenic"][0], total - natural, rtol=0, atol=1e-12
            )
            # Greenhouse gases.
            np.testing.assert_array_equal(
                out[f"{erf}|Greenhouse Gases"][0],
                _xarray_sum(da, sc_idx, member,
                            ["CO2", "CH4", "N2O", "HFC-134a", "CF4", "CFC-11"]),
            )
            # F-gases.
            np.testing.assert_array_equal(
                out[f"{erf}|F-Gases"][0],
                _xarray_sum(da, sc_idx, member, ["HFC-134a", "CF4"]),
            )
            # Single-species pass-through (Ozone).
            np.testing.assert_array_equal(
                out[f"{erf}|Ozone"][0],
                da.sel(specie="Ozone").isel(scenario=sc_idx, config=member).values,
            )
