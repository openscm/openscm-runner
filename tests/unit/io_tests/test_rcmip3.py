"""Tests for the RCMIP3 wide-table reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from openscm_runner.io import (
    RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY,
    RCMIP3_METADATA_COLS,
    canonicalise_rcmip3_variable,
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


# ---------------------------------------------------------------------------
# CICEROSCMPY2 back-report helper
# ---------------------------------------------------------------------------


def _fake_series_df(values, nystart=1750):
    """Year-indexed single-column DataFrame matching the adapter shape."""
    return pd.DataFrame(
        {0: values},
        index=pd.RangeIndex(nystart, nystart + len(values), name="year"),
    )


def test_backreport_builds_scmrun_with_expected_shape():
    from openscm_runner.adapters.ciceroscm_py2_adapter.ciceroscmpy2_adapter import (
        _build_rcmip3_backreport_scmrun,
    )

    scendata_list = [
        {
            "scenname": "ssp245",
            "rf_sun_data": _fake_series_df([0.0, 0.1, 0.15]),
            "rf_volc_data": _fake_series_df([0.0, -0.05, -0.20]),
            "rf_luc_data": _fake_series_df([0.0, -0.01, -0.02]),
        },
        {
            "scenname": "ssp126",
            "rf_sun_data": _fake_series_df([0.0, 0.05, 0.08]),
            "rf_volc_data": _fake_series_df([0.0, 0.0, 0.0]),
            # No rf_luc_data — idealised-style scenario, lu_zero path.
        },
    ]
    dist_cfgs = [{"Index": "cfg_0"}, {"Index": "cfg_1"}]
    backreport_variables = [
        "Effective Radiative Forcing|Natural|Solar",
        "Effective Radiative Forcing|Natural|Volcanic",
        "Effective Radiative Forcing|Anthropogenic|Albedo Change|Land use",
    ]

    out = _build_rcmip3_backreport_scmrun(
        scendata_list=scendata_list,
        backreport_variables=backreport_variables,
        dist_cfgs=dist_cfgs,
    )
    assert out is not None
    # ssp245: 3 vars x 2 cfgs = 6 rows; ssp126: 2 vars x 2 cfgs = 4 rows
    assert len(out.meta) == 10
    assert set(out.get_unique_meta("variable")) == set(backreport_variables)
    assert set(out.get_unique_meta("scenario")) == {"ssp245", "ssp126"}
    assert set(out.get_unique_meta("region")) == {"World"}
    assert set(out.get_unique_meta("unit")) == {"W/m^2"}


def test_backreport_returns_none_when_no_trajectories_match():
    # User asks only for Land use back-report but every scenario is
    # idealised (no rf_luc_data populated). Helper returns None so
    # the caller can log/omit.
    from openscm_runner.adapters.ciceroscm_py2_adapter.ciceroscmpy2_adapter import (
        _build_rcmip3_backreport_scmrun,
    )

    scendata_list = [
        {"scenname": "1pctCO2", "rf_sun_data": _fake_series_df([0.0, 0.0])},
    ]
    dist_cfgs = [{"Index": "cfg_0"}]
    out = _build_rcmip3_backreport_scmrun(
        scendata_list=scendata_list,
        backreport_variables=[
            "Effective Radiative Forcing|Anthropogenic|Albedo Change|Land use",
        ],
        dist_cfgs=dist_cfgs,
    )
    assert out is None


# ---------------------------------------------------------------------------
# canonicalise_rcmip3_variable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("canonical", "expected"),
    [
        # Flat name -- unchanged
        ("Emissions|CH4", "Emissions|CH4"),
        ("Atmospheric Concentrations|CO2", "Atmospheric Concentrations|CO2"),
        # Natural-forcing categories aren't stripped
        (
            "Effective Radiative Forcing|Natural|Solar",
            "Effective Radiative Forcing|Natural|Solar",
        ),
        # CO2 sub-sectors -> MAGICC-style
        ("Emissions|CO2|AFOLU", "Emissions|CO2|MAGICC AFOLU"),
        (
            "Emissions|CO2|Energy and Industrial Processes",
            "Emissions|CO2|MAGICC Fossil and Industrial",
        ),
        # PFCs / F-gases: strip intermediate categories
        ("Emissions|PFC|C2F6", "Emissions|C2F6"),
        ("Emissions|PFC|cC4F8", "Emissions|cC4F8"),
        (
            "Atmospheric Concentrations|F-Gases|HFC|HFC125",
            "Atmospheric Concentrations|HFC125",
        ),
        (
            "Atmospheric Concentrations|F-Gases|PFC|CF4",
            "Atmospheric Concentrations|CF4",
        ),
    ],
)
def test_canonicalise_rcmip3_variable_roundtrips(canonical, expected):
    assert canonicalise_rcmip3_variable(canonical) == expected


# ---------------------------------------------------------------------------
# FaIR2 canonical-RCMIP3 emissions + concentrations builders
# ---------------------------------------------------------------------------


def test_fair2_emissions_canonical_path_translates_variables():
    from openscm_runner.adapters.fair2_adapter._emissions_translator import (
        _rcmip3_to_fair_emissions_df,
    )

    df = _rcmip3_to_fair_emissions_df(MINI_BUNDLE, scenario_names=["ssp245"])
    assert not df.empty
    species_seen = set(df["variable"].unique())
    # Mini fixture covers every FaIR emissions-mode species so the
    # integration smoke can iterate them; assert the FaIR-translated
    # forms made it through for the sub-sector + intermediate-category
    # cases that the translator has to handle (CO2 sub-sectors and an
    # F-Gases / HFC / PFC / Halon / CFC representative).
    assert {
        "CO2 AFOLU", "CO2 FFI", "CH4",
        "HFC-125", "C2F6", "Halon-1211", "CFC-11",
    }.issubset(species_seen)
    # Year columns are integer keys (FaIR convention internally)
    year_cols = [c for c in df.columns if isinstance(c, int)]
    assert 1750 in year_cols and 2100 in year_cols


def test_fair2_splice_empty_bundle_returns_user_rows():
    """Idealised scenarios (abrupt-4xCO2, 1pctCO2, esm-flat10*) have no
    RCMIP3 emissions baseline, so the bundle frame is empty. The splice
    must return the user's rows instead of raising ``KeyError`` on the
    missing ``scenario`` column."""
    from openscm_runner.adapters.fair2_adapter._emissions_translator import (
        _splice_bundle_with_user,
    )

    user_df = pd.DataFrame([{
        "scenario": "abrupt-4xCO2",
        "variable": "CO2 FFI",
        "region": "World",
        "unit": "Gt CO2/yr",
        1750: 0.0,
        1850: 36.0,
    }])

    out = _splice_bundle_with_user(
        pd.DataFrame(), user_df, scenario_names=["abrupt-4xCO2"],
    )
    assert not out.empty
    assert set(out["variable"]) == {"CO2 FFI"}
    assert out.loc[out["variable"] == "CO2 FFI", 1850].iloc[0] == 36.0

    # Empty bundle + empty user -> empty frame (no crash).
    assert _splice_bundle_with_user(
        pd.DataFrame(), pd.DataFrame(), scenario_names=["abrupt-4xCO2"],
    ).empty


def test_fair2_build_emissions_df_idealised_scenario_with_user_emissions():
    """End-to-end: an idealised scenario (no RCMIP3 baseline) with a
    user emissions overlay must build without KeyError, keep CO2, and
    zero the non-CO2 species via the ``co2_only_scenarios`` path."""
    from scmdata import ScmRun

    from openscm_runner.adapters.fair2_adapter._emissions_translator import (
        build_emissions_df,
    )

    scmrun = ScmRun(pd.DataFrame({
        "model": ["test", "test"],
        "scenario": ["abrupt-4xCO2", "abrupt-4xCO2"],
        "region": ["World", "World"],
        "variable": [
            "Emissions|CO2|MAGICC Fossil and Industrial",
            "Emissions|CH4",
        ],
        "unit": ["Mt CO2/yr", "Mt CH4/yr"],
        1750: [0.0, 100.0],
        1850: [1000.0, 300.0],
    }))

    out = build_emissions_df(
        scmrun, MINI_BUNDLE, scenario_names=["abrupt-4xCO2"],
        co2_only_scenarios=("abrupt-4xCO2",),
    )
    assert not out.empty
    variables = set(out["variable"])
    assert "CO2 FFI" in variables and "CH4" in variables
    # build_emissions_df stringifies year columns at the boundary.
    year_cols = [c for c in out.columns if isinstance(c, str) and c.isdigit()]
    co2 = out[out["variable"] == "CO2 FFI"]
    ch4 = out[out["variable"] == "CH4"]
    # CO2 survives; non-CO2 is zeroed for the idealised scenario.
    assert (co2[year_cols].to_numpy() != 0).any()
    assert (ch4[year_cols].fillna(0).to_numpy() == 0).all()


def test_fair2_concentrations_canonical_path_translates_variables():
    from openscm_runner.adapters.fair2_adapter._concentrations_translator import (
        build_concentrations_df_from_rcmip3,
    )

    df = build_concentrations_df_from_rcmip3(
        rcmip3_bundle_path=MINI_BUNDLE,
        scenario_names=["ssp245"],
        fair_species={"CO2", "CH4", "N2O"},
        nystart=1750,
        nyend=2100,
    )
    assert not df.empty
    species_seen = set(df["variable"].unique())
    assert species_seen == {"CO2", "CH4", "N2O"}
    # Lowercased metadata columns + string-keyed year columns
    assert "scenario" in df.columns
    assert "1750" in df.columns
    assert "2100" in df.columns


def test_fair2_concentrations_canonical_path_filters_unknown_species():
    from openscm_runner.adapters.fair2_adapter._concentrations_translator import (
        build_concentrations_df_from_rcmip3,
    )

    df = build_concentrations_df_from_rcmip3(
        rcmip3_bundle_path=MINI_BUNDLE,
        scenario_names=["ssp245"],
        fair_species={"CH4"},  # restrict
        nystart=1750,
        nyend=2100,
    )
    assert set(df["variable"].unique()) == {"CH4"}
