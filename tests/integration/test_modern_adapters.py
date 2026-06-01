"""
Integration smoke tests for the FaIRv2 and CICEROSCMPY2 adapters
under the AdapterLike reshape.

Each test constructs an adapter via ``from_native_distribution`` over
an in-repo 2-3 member fixture (trimmed from a real distribution, not
synthetic), runs it through the new ``openscm_runner.run.run`` list
form, and asserts the requested output variables are present with
2100 GSAT in a plausible band.

Fixtures live under
``tests/test-data/fair2-mini-bundle/`` and
``tests/test-data/ciceroscm-mini-bundle/`` so the tests run on every
CI build with no external fetch. The scenario CSV is the same
``rcmip_scen_ssp_world_emissions.csv`` the existing adapter tests
use.

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

fair2_skip = pytest.mark.skipif(
    not HAS_FAIR2, reason="fair>=2 not installed"
)
cicero_skip = pytest.mark.skipif(
    not HAS_CICEROSCM_PY2, reason="ciceroscm>=2 not installed"
)


@pytest.fixture
def ssp245(test_scenarios):
    """Single scenario for the smoke tests."""
    return test_scenarios.filter(scenario="ssp245")


def _build_fair2_ed():
    return FAIR2.from_native_distribution(
        FAIR2_MINI_BUNDLE,
        mode=RunMode.EMISSIONS_DRIVEN,
        output_variables=_OUTPUT_VARIABLES,
    )


def _build_fair2_cd():
    return FAIR2.from_native_distribution(
        FAIR2_MINI_BUNDLE,
        mode=RunMode.CONCENTRATION_DRIVEN,
        output_variables=_OUTPUT_VARIABLES,
        fair2_conc_bundle_dir=str(CICERO_MINI_BUNDLE),
    )


def _build_cicero_ed():
    return CICEROSCMPY2.from_native_distribution(
        CICERO_MINI_BUNDLE,
        mode=RunMode.EMISSIONS_DRIVEN,
        output_variables=_OUTPUT_VARIABLES,
    )


def _build_cicero_cd():
    return CICEROSCMPY2.from_native_distribution(
        CICERO_MINI_BUNDLE,
        mode=RunMode.CONCENTRATION_DRIVEN,
        output_variables=_OUTPUT_VARIABLES,
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
