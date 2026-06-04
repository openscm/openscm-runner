"""I/O helpers for openscm-runner inputs.

Currently exposes :mod:`.rcmip3`, a reader for the canonical RCMIP
Phase 3 wide-table CSV bundle (Zenodo record 20430630).
"""
from .rcmip3 import (
    RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY,
    RCMIP3_METADATA_COLS,
    load_rcmip3,
    load_rcmip3_albedo_categories,
    load_rcmip3_concentrations,
    load_rcmip3_emissions,
    load_rcmip3_forcings,
    resolve_scenario_category,
)

__all__ = [
    "RCMIP3_DEFAULT_SCENARIO_TO_CATEGORY",
    "RCMIP3_METADATA_COLS",
    "load_rcmip3",
    "load_rcmip3_albedo_categories",
    "load_rcmip3_concentrations",
    "load_rcmip3_emissions",
    "load_rcmip3_forcings",
    "resolve_scenario_category",
]
