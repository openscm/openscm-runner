"""Tests for the RCMIP3 wide-table reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from openscm_runner.io import (
    RCMIP3_METADATA_COLS,
    load_rcmip3,
    load_rcmip3_albedo_categories,
    load_rcmip3_concentrations,
    load_rcmip3_emissions,
    load_rcmip3_forcings,
)
from openscm_runner.io.rcmip3 import _RCMIP3_CMIP7_CATEGORY_TO_SSP

MINI_BUNDLE = Path(__file__).parent.parent.parent / "test-data" / "rcmip3-mini"


def test_load_concentrations_returns_wide_format():
    df = load_rcmip3_concentrations(MINI_BUNDLE)
    for col in RCMIP3_METADATA_COLS:
        assert col in df.columns
    assert "1750" in df.columns
    assert "2100" in df.columns
    assert len(df) > 0


def test_load_filters_by_scenario():
    df = load_rcmip3_concentrations(MINI_BUNDLE, scenarios=["ssp245"])
    assert set(df["Scenario"].unique()) == {"ssp245"}
    assert len(df) > 0


def test_load_filters_by_variable():
    df = load_rcmip3_emissions(
        MINI_BUNDLE,
        variables=["Emissions|CH4"],
    )
    assert set(df["Variable"].unique()) == {"Emissions|CH4"}


def test_load_filters_by_region_default():
    df = load_rcmip3_forcings(MINI_BUNDLE)
    assert set(df["Region"].unique()) == {"World"}


def test_load_filters_by_region_explicit_none():
    df = load_rcmip3_forcings(MINI_BUNDLE, region=None)
    # Mini bundle only has World rows; this just exercises the
    # filter-off path without asserting on other regions.
    assert "Region" in df.columns


def test_load_empty_filter_returns_empty_frame():
    df = load_rcmip3_concentrations(
        MINI_BUNDLE, scenarios=["does-not-exist"]
    )
    assert df.empty
    # Columns are still present.
    for col in RCMIP3_METADATA_COLS:
        assert col in df.columns


def test_load_unknown_kind_raises():
    with pytest.raises(KeyError):
        load_rcmip3(MINI_BUNDLE, kind="bogus")  # type: ignore[arg-type]


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_rcmip3(Path("/does/not/exist"), kind="concentrations")


def test_load_direct_csv_path_accepted(tmp_path):
    src = MINI_BUNDLE / "rcmip_phase3_concentrations_v2.0.0.csv"
    dest = tmp_path / "renamed.csv"
    dest.write_text(src.read_text())
    # Direct file path works regardless of the canonical name.
    df = load_rcmip3(dest, kind="concentrations")
    assert len(df) > 0


def test_load_missing_metadata_raises(tmp_path):
    # Construct a CSV that doesn't have the metadata columns.
    bad = tmp_path / "rcmip_phase3_concentrations_v2.0.0.csv"
    pd.DataFrame({"WrongCol": [1, 2, 3]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="missing expected metadata"):
        load_rcmip3(tmp_path, kind="concentrations")


def test_forcings_has_albedo_change_for_ssp_scenarios():
    df = load_rcmip3_forcings(
        MINI_BUNDLE,
        scenarios=["ssp245"],
        variables=["Effective Radiative Forcing|Anthropogenic|Albedo Change"],
    )
    assert len(df) >= 1
    # Per the canonical bundle, ssp* scenarios carry the lumped
    # Albedo Change row. Confirm it's negative by 2100 (land use
    # cooling).
    assert df["2100"].iloc[0] < 0


def test_albedo_categories_returns_land_use_and_irrigation():
    df = load_rcmip3_albedo_categories(MINI_BUNDLE, category="M")
    assert list(df.columns) == ["Land Use", "Irrigation"]
    assert df.index.is_monotonic_increasing
    assert df.loc[1750, "Land Use"] == 0.0
    assert df.loc[1750, "Irrigation"] == 0.0


def test_albedo_categories_unknown_category_raises():
    with pytest.raises(ValueError, match="Unknown RCMIP3 CMIP7 scenario"):
        load_rcmip3_albedo_categories(MINI_BUNDLE, category="ZZ")


def test_category_to_ssp_map_covers_published_categories():
    expected = {"VL", "LN", "L", "ML", "M", "H", "HL"}
    assert set(_RCMIP3_CMIP7_CATEGORY_TO_SSP) == expected
