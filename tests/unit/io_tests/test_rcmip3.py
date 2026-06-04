"""Tests for the RCMIP3 wide-table reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from openscm_runner.io import (
    RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY,
    RCMIP3_METADATA_COLS,
    load_rcmip3,
    load_rcmip3_albedo_categories,
    load_rcmip3_concentrations,
    load_rcmip3_emissions,
    load_rcmip3_forcings,
    resolve_scenario_category,
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
    df = load_rcmip3_concentrations(MINI_BUNDLE, scenarios=["does-not-exist"])
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


def test_default_scenario_to_category_covers_all_ssp_rcps():
    # SSP-RCP scenarios published in the canonical RCMIP3 forcing CSV.
    expected = {
        "ssp119", "ssp126", "ssp245", "ssp370",
        "ssp434", "ssp460", "ssp534-over", "ssp585",
    }
    assert set(RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY) == expected


def test_resolve_scenario_category_default():
    assert resolve_scenario_category("ssp245") == "M"
    assert resolve_scenario_category("ssp585") == "HL"
    assert resolve_scenario_category("ssp119") == "VL"


def test_resolve_scenario_category_override_takes_precedence():
    assert (
        resolve_scenario_category("ssp245", overrides={"ssp245": "L"})
        == "L"
    )


def test_resolve_scenario_category_native_scen7_name():
    assert resolve_scenario_category("scen7-M") == "M"
    assert resolve_scenario_category("scen7-VL") == "VL"


def test_resolve_scenario_category_historical_returns_none():
    # Historical has its own per-component breakdown in the canonical
    # CSV; the resolver signals that by returning None.
    assert resolve_scenario_category("historical") is None
    assert resolve_scenario_category("historical-cmip6") is None


def test_resolve_scenario_category_unknown_raises():
    with pytest.raises(KeyError, match="No CMIP7 ScenarioMIP category"):
        resolve_scenario_category("1pctCO2")


def test_forcings_has_historical_albedo_breakdown():
    # Historical scenario carries per-component Land Use and
    # Irrigation rows in the canonical CSV; ssp scenarios only have
    # the lumped Albedo Change. Confirm both sub-components exist for
    # historical.
    for component in ("Land Use", "Irrigation"):
        df = load_rcmip3_forcings(
            MINI_BUNDLE,
            scenarios=["historical"],
            variables=[
                f"Effective Radiative Forcing|Anthropogenic|"
                f"Albedo Change|{component}"
            ],
        )
        assert len(df) == 1, f"{component}: expected 1 row, got {len(df)}"


def test_forcings_has_natural_solar_volcanic_per_scenario():
    # Solar + Volcanic are published per-scenario in the canonical
    # forcing CSV (not a single trajectory broadcast across scenarios
    # like the legacy bundle CSVs). Confirm both are present for
    # ssp245 (one of the SSP-RCP scenarios) and historical.
    for scenario in ("historical", "ssp245"):
        for component in ("Solar", "Volcanic"):
            df = load_rcmip3_forcings(
                MINI_BUNDLE,
                scenarios=[scenario],
                variables=[
                    f"Effective Radiative Forcing|Natural|{component}"
                ],
            )
            assert len(df) == 1, (
                f"{scenario}/{component}: expected 1 row, got {len(df)}"
            )


def test_forcings_solar_differs_across_scenarios():
    # The canonical CSV uses per-scenario natural-forcing rows. If
    # historical 1850 == ssp245 1850 we've accidentally lost the
    # per-scenario distinction the adapter relies on.
    hist = load_rcmip3_forcings(
        MINI_BUNDLE,
        scenarios=["historical"],
        variables=["Effective Radiative Forcing|Natural|Solar"],
    )
    ssp = load_rcmip3_forcings(
        MINI_BUNDLE,
        scenarios=["ssp245"],
        variables=["Effective Radiative Forcing|Natural|Solar"],
    )
    assert float(hist["1850"].iloc[0]) != float(ssp["1850"].iloc[0])
