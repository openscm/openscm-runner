"""Unit tests for the MAGICC7 conc-driven translator.

These tests do NOT require pymagicc or the MAGICC binary; they
exercise the pure-Python overlay / filter / cfg-key logic only. The
end-to-end conc-file writer (which goes through pymagicc) is tested
under ``@pytest.mark.magicc`` in ``tests/integration/test_magicc7.py``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scmdata import ScmRun

from openscm_runner.adapters.magicc7._concentrations_translator import (
    FGAS_NAMES,
    MHALO_NAMES,
    RCMIP_TO_MAGICC_SPECIES,
    build_concentrations_overlay,
    cfg_keys_for_species,
    classify_conc_species,
    to_magicc_species,
)

_TEST_DATA = Path(__file__).parent.parent.parent / "test-data"
RCMIP3_MINI_BUNDLE = _TEST_DATA / "rcmip3-mini"
# Variant bundle that additionally ships a few F-gas / Montreal-halocarbon
# ssp245 concentration trajectories (HFC134a, SF6, CFC12) to exercise the
# bundled-array path. Kept separate from the main mini bundle so the
# binary end-to-end GSAT comparison stays on the WMGHGs only.
RCMIP3_MINI_HALO_BUNDLE = _TEST_DATA / "rcmip3-mini-halo"


def _user_conc_run(
    scenario: str, species_short: str, unit: str, values: dict[int, float],
) -> ScmRun:
    """Build a one-row ScmRun with an ``Atmospheric Concentrations|<species>`` trajectory."""
    frame = pd.DataFrame({
        "model": ["unspecified"],
        "scenario": [scenario],
        "region": ["World"],
        "variable": [f"Atmospheric Concentrations|{species_short}"],
        "unit": [unit],
        **{year: [val] for year, val in values.items()},
    })
    return ScmRun(frame)


def test_cfg_keys_for_species_naming_convention():
    """MAGICC7 namelist: ``FILE_<gas>_CONC`` + ``<gas>_SWITCHFROMCONC2EMIS_YEAR``."""
    assert cfg_keys_for_species("CO2") == (
        "file_co2_conc", "co2_switchfromconc2emis_year",
    )
    assert cfg_keys_for_species("CH4") == (
        "file_ch4_conc", "ch4_switchfromconc2emis_year",
    )
    assert cfg_keys_for_species("N2O") == (
        "file_n2o_conc", "n2o_switchfromconc2emis_year",
    )


def test_cfg_keys_for_species_rejects_non_per_gas_species():
    """Per-gas flags are CO2/CH4/N2O only; F-gases / halocarbons raise
    (they route through the bundled-array path instead)."""
    with pytest.raises(ValueError, match="per-gas species"):
        cfg_keys_for_species("HFC134A")
    with pytest.raises(ValueError, match="per-gas species"):
        cfg_keys_for_species("CFC11")


def test_classify_conc_species():
    """Species route to per-gas / fgas / mhalo / unsupported correctly."""
    assert classify_conc_species("CO2") == "per_gas"
    assert classify_conc_species("N2O") == "per_gas"
    assert classify_conc_species("SF6") == "fgas"
    assert classify_conc_species("HFC134A") == "fgas"
    assert classify_conc_species("CFC12") == "mhalo"
    assert classify_conc_species("HALON1211") == "mhalo"
    assert classify_conc_species("NOTAGAS") is None


def test_to_magicc_species_normalises_case_and_renames():
    """RCMIP3 leaf names map onto MAGICC's upper-case FGAS/MHALO names."""
    # Pure case differences (uppercase fallback):
    assert to_magicc_species("HFC134a") == "HFC134A"
    assert to_magicc_species("CCl4") == "CCL4"
    assert to_magicc_species("CH3Cl") == "CH3CL"
    # Explicit renames win over the fallback:
    assert to_magicc_species("H-1211") == "HALON1211"
    assert to_magicc_species("HFC4310mee") == "HFC4310"
    assert to_magicc_species("cC4F8") == "CC4F8"
    # Already-canonical names round-trip:
    assert to_magicc_species("CO2") == "CO2"
    assert to_magicc_species("SF6") == "SF6"


def test_rcmip_to_magicc_species_covers_halons_and_hfc4310mee():
    """Spot-check the species rename table for the cases that bite."""
    assert RCMIP_TO_MAGICC_SPECIES["H-1211"] == "HALON1211"
    assert RCMIP_TO_MAGICC_SPECIES["HFC4310mee"] == "HFC4310"


def test_fgas_mhalo_name_lists_are_sane():
    """Positional name arrays match the MAGICC namelist cardinality."""
    assert len(FGAS_NAMES) == 23
    assert len(MHALO_NAMES) == 18
    assert len(set(FGAS_NAMES)) == len(FGAS_NAMES)
    assert len(set(MHALO_NAMES)) == len(MHALO_NAMES)
    assert "HALON1202" == MHALO_NAMES[-1]


def test_overlay_uses_rcmip3_baseline_when_user_run_empty():
    """With no user overlay, ssp245 in rcmip3-mini supplies CO2/CH4/N2O."""
    empty_run = None
    overlay = build_concentrations_overlay(
        empty_run, RCMIP3_MINI_BUNDLE, ["ssp245"],
    )
    assert set(overlay["magicc_species"]) == {"CO2", "CH4", "N2O"}
    co2 = overlay[overlay["magicc_species"] == "CO2"].iloc[0]
    assert co2["scenario"] == "ssp245"
    assert co2["unit"] == "ppm"
    assert co2["series"].loc[2100] == pytest.approx(602.78, rel=1e-3)


def test_overlay_includes_fgas_mhalo_from_bundle():
    """The halo bundle's F-gas / Montreal-halocarbon ssp245 rows survive,
    are mapped onto MAGICC's upper-case names, and carry ppt units."""
    empty_run = None
    overlay = build_concentrations_overlay(
        empty_run, RCMIP3_MINI_HALO_BUNDLE, ["ssp245"],
    )
    assert set(overlay["magicc_species"]) == {
        "CO2", "CH4", "N2O", "HFC134A", "SF6", "CFC12",
    }
    sf6 = overlay[overlay["magicc_species"] == "SF6"].iloc[0]
    assert sf6["unit"] == "ppt"
    assert sf6["series"].loc[2100] == pytest.approx(18.3, rel=1e-3)
    # RCMIP3 leaf 'HFC134a' resolved to MAGICC's 'HFC134A':
    assert "HFC134a" not in set(overlay["magicc_species"])


def test_overlay_user_row_merges_year_by_year_with_baseline():
    """User CO2 values win per-year; gaps are filled from the bundle."""
    user = _user_conc_run(
        "ssp245", "CO2", "ppm", {2050: 999.0, 2100: 999.0},
    )
    overlay = build_concentrations_overlay(
        user, RCMIP3_MINI_BUNDLE, ["ssp245"],
    )
    co2 = overlay[overlay["magicc_species"] == "CO2"].iloc[0]
    # User values win where supplied:
    assert co2["series"].loc[2100] == pytest.approx(999.0)
    assert co2["series"].loc[2050] == pytest.approx(999.0)
    # Baseline fills the gaps the user did NOT supply:
    assert co2["series"].loc[1850] == pytest.approx(284.32, rel=1e-3)
    # CH4 / N2O still served from the RCMIP3 baseline:
    ch4 = overlay[overlay["magicc_species"] == "CH4"].iloc[0]
    assert ch4["series"].loc[2100] == pytest.approx(1683.16, rel=1e-3)


def test_overlay_is_per_scenario_not_batch_intersection():
    """The conc-driven decision is per-scenario, with no batch-consistency
    requirement (unlike FaIR2). rcmip3-mini ships ssp245 conc data but no
    ssp126; a batch of both should still drive ssp245's species and simply
    leave ssp126 to the emissions path — not blank out ssp245."""
    empty_run = None
    overlay = build_concentrations_overlay(
        empty_run, RCMIP3_MINI_BUNDLE, ["ssp245", "ssp126"],
    )
    assert not overlay.empty
    # ssp245 species survive ...
    assert set(overlay.loc[overlay["scenario"] == "ssp245", "magicc_species"]) == {
        "CO2", "CH4", "N2O",
    }
    # ... and ssp126 (no baseline data) contributes nothing.
    assert (overlay["scenario"] == "ssp126").sum() == 0


def test_overlay_returns_empty_when_no_scenarios():
    """No scenario_names -> empty overlay (no work to do)."""
    empty_run = None
    overlay = build_concentrations_overlay(
        empty_run, RCMIP3_MINI_BUNDLE, [],
    )
    assert overlay.empty
