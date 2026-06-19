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
    RCMIP_TO_MAGICC_SPECIES,
    build_concentrations_overlay,
    cfg_keys_for_species,
)

RCMIP3_MINI_BUNDLE = (
    Path(__file__).parent.parent.parent
    / "test-data"
    / "rcmip3-mini"
)


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


def test_cfg_keys_for_species_rejects_unsupported_species():
    """v1 supports only CO2/CH4/N2O; F-gases / halocarbons raise."""
    with pytest.raises(ValueError, match="MAGICC7 conc-driven v1"):
        cfg_keys_for_species("HFC134a")
    with pytest.raises(ValueError, match="MAGICC7 conc-driven v1"):
        cfg_keys_for_species("CFC11")


def test_rcmip_to_magicc_species_covers_halons_and_hfc4310mee():
    """Spot-check the species rename table for the cases that bite."""
    assert RCMIP_TO_MAGICC_SPECIES["H-1211"] == "HALON1211"
    assert RCMIP_TO_MAGICC_SPECIES["HFC4310mee"] == "HFC4310"


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


def test_overlay_drops_species_not_present_in_every_batch_scenario():
    """Mixed-mode filter: species must be supplied for every batch scenario."""
    # rcmip3-mini ships ssp245 baseline but no ssp126 conc data; a batch
    # of [ssp245, ssp126] therefore has zero species covered for every
    # scenario, and the overlay should be empty.
    empty_run = None
    overlay = build_concentrations_overlay(
        empty_run, RCMIP3_MINI_BUNDLE, ["ssp245", "ssp126"],
    )
    assert overlay.empty


def test_overlay_returns_empty_when_no_scenarios():
    """No scenario_names -> empty overlay (no work to do)."""
    empty_run = None
    overlay = build_concentrations_overlay(
        empty_run, RCMIP3_MINI_BUNDLE, [],
    )
    assert overlay.empty
