"""
Integration smoke tests for the FaIRv2 and CICEROSCMPY2 adapters
under the AdapterLike reshape.

Four parameterised cases (FaIRv2 ED / CD, CICEROSCMPY2 ED / CD) per
upstream guidance in benmsanderson/openscm-runner#13. Each test
constructs an adapter via ``from_native_distribution`` over an
in-repo 2-3 member fixture (trimmed from a real distribution, not
synthetic), runs it through the new ``openscm_runner.run.run`` list
form, and asserts the requested output variables are present with
2100 GSAT in a plausible band.

Fixtures live under ``tests/test-data/fair2-mini-bundle/`` and
``tests/test-data/ciceroscm-mini-bundle/`` so the tests run on every
CI build with no external fetch. The scenario CSV is the same
``rcmip_scen_ssp_world_emissions.csv`` the existing adapter tests
use.

The CICERO mini-bundle was generated for the Phase E bundle-mode
adapter and ships ssp245-specific filenames (``ssp245_em_*``,
``ssp245_conc_*``, ``*_RCMIP_ssp245_RCMIP3.txt``). Phase F's
``from_native_distribution`` resolves canonical historical filenames
by default, so the CICERO test builders pass explicit cfg overrides
pointing at the bundle's ssp245-specific files. This is the same
"power-user reproduction" override pattern the AR7 application repo
uses to recover Marit's reference (see UPSTREAM_MERGE_PROGRESS.md
"Phase F fork-side check").

Tests are individually skipped when the underlying model package
(``fair>=2`` for FaIRv2, ``ciceroscm>=2`` for CICEROSCMPY2) is not
installed. CI is expected to install both extras.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import openscm_runner.run
from openscm_runner import RunMode
from openscm_runner.adapters import CICEROSCMPY2, FAIR2
from openscm_runner.adapters.ciceroscm_py2_adapter._compat import (
    HAS_CICEROSCM_PY2,
)
from openscm_runner.adapters.fair2_adapter._compat import HAS_FAIR2

FAIR2_MINI_BUNDLE = (
    Path(__file__).parent.parent / "test-data" / "fair2-mini-bundle"
)
CICERO_MINI_BUNDLE = (
    Path(__file__).parent.parent / "test-data" / "ciceroscm-mini-bundle"
)

_OUTPUT_VARIABLES = (
    "Surface Air Temperature Change",
    "Effective Radiative Forcing",
)
# 2 members per test per upstream guidance ("2-5 members per test, not
# full thousand-member configs"). Both mini-bundles ship 3 members in
# their parameter posterior; we use the first 2.
_MEMBER_INDICES = [0, 1]

fair2_skip = pytest.mark.skipif(
    not HAS_FAIR2, reason="fair>=2 not installed"
)
cicero_skip = pytest.mark.skipif(
    not HAS_CICEROSCM_PY2, reason="ciceroscm>=2 not installed"
)


# Explicit ssp245-specific overrides for the CICERO calibration
# directory. Phase F's canonical-filename resolver looks for
# ``historical_em_*`` etc. by default; the mini-bundle was generated
# pre-Phase F with ssp245-specific names, so we wire them in via the
# cfg-override mechanism. This is also the "power-user reproduction"
# pattern the AR7 application repo follows.
_CICERO_SSP245_OVERRIDES = {
    "historical_em_file": str(
        CICERO_MINI_BUNDLE / "ssp245_em_gases_vupdate_2024_WMO_added_new.txt"
    ),
    "historical_conc_file": str(
        CICERO_MINI_BUNDLE
        / "ssp245_conc_gases_vupdate_2024_WMO_added_new.txt"
    ),
    "rf_solar_file": str(
        CICERO_MINI_BUNDLE / "solar_RCMIP_ssp245_RCMIP3.txt"
    ),
    "rf_volc_file": str(
        CICERO_MINI_BUNDLE / "VOLC_RCMIP_ssp245_RCMIP3.txt"
    ),
    "rf_luc_file": str(
        CICERO_MINI_BUNDLE / "LUCalbedo_RCMIP_ssp245_RCMIP3.txt"
    ),
}


@pytest.fixture
def ssp245(test_scenarios):
    """Single scenario for the smoke tests."""
    return test_scenarios.filter(scenario="ssp245")


def _build_fair2_ed():
    return FAIR2.from_native_distribution(
        FAIR2_MINI_BUNDLE,
        mode=RunMode.EMISSIONS_DRIVEN,
        member_indices=_MEMBER_INDICES,
        output_variables=_OUTPUT_VARIABLES,
    )


def _build_fair2_cd():
    return FAIR2.from_native_distribution(
        FAIR2_MINI_BUNDLE,
        mode=RunMode.CONCENTRATION_DRIVEN,
        member_indices=_MEMBER_INDICES,
        output_variables=_OUTPUT_VARIABLES,
        fair2_conc_bundle_dir=str(CICERO_MINI_BUNDLE),
    )


def _build_cicero_ed():
    return CICEROSCMPY2.from_native_distribution(
        CICERO_MINI_BUNDLE,
        mode=RunMode.EMISSIONS_DRIVEN,
        member_indices=_MEMBER_INDICES,
        output_variables=_OUTPUT_VARIABLES,
        max_workers=1,
        **_CICERO_SSP245_OVERRIDES,
    )


def _build_cicero_cd():
    return CICEROSCMPY2.from_native_distribution(
        CICERO_MINI_BUNDLE,
        mode=RunMode.CONCENTRATION_DRIVEN,
        member_indices=_MEMBER_INDICES,
        output_variables=_OUTPUT_VARIABLES,
        max_workers=1,
        **_CICERO_SSP245_OVERRIDES,
    )


@pytest.mark.parametrize(
    "adapter_factory",
    [
        pytest.param(_build_fair2_ed, marks=fair2_skip, id="fair2-ed"),
        pytest.param(_build_fair2_cd, marks=fair2_skip, id="fair2-cd"),
        pytest.param(_build_cicero_ed, marks=cicero_skip, id="cicero-ed"),
        pytest.param(_build_cicero_cd, marks=cicero_skip, id="cicero-cd"),
    ],
)
def test_adapter_smoke_ssp245(adapter_factory, ssp245):
    """
    Construct the adapter via its native-distribution classmethod,
    run a 2-3 member ensemble on ssp245, and check the output is the
    right shape with a plausible 2100 GSAT.
    """
    adapter = adapter_factory()
    result = openscm_runner.run.run([adapter], scenarios=ssp245)

    variables_seen = set(result.get_unique_meta("variable"))
    assert "Surface Air Temperature Change" in variables_seen

    gsat_2100 = result.filter(
        variable="Surface Air Temperature Change", year=2100
    ).values
    # 2-3 ensemble members; coarse plausibility band.
    assert gsat_2100.size > 0
    assert (gsat_2100 > 0).all()
    assert (gsat_2100 < 7).all()
