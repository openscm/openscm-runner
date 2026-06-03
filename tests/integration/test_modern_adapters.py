"""
Integration smoke tests for the FaIRv2 and CICEROSCMPY2 adapters.

Four parameterised cases (FaIRv2 emissions/concentration-driven,
CICEROSCMPY2 emissions/concentration-driven). Each test constructs
the adapter via ``from_native_distribution``, runs the full 3-member
mini-bundle ensemble across ssp126/ssp245/ssp370, and checks GSAT
and total ERF at 1850/1900/2000/2025/2050/2100 against a
pytest-regressions snapshot.

Fixtures live under ``tests/test-data/fair2-mini-bundle/`` and
``tests/test-data/ciceroscm-mini-bundle/`` so the tests run on every
CI build with no external fetch. The CICERO mini-bundle ships
ssp245-specific input filenames; the CICERO test builders wire those
in via the cfg-override mechanism.

Tests are individually skipped when the underlying model package
(``fair>=2`` for FaIRv2, ``ciceroscm>=2`` for CICEROSCMPY2) is not
installed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import openscm_runner.run
from openscm_runner import RunMode
from openscm_runner.adapters import CICEROSCMPY2, FAIR2
from openscm_runner.adapters.ciceroscm_py2_adapter._compat import (
    HAS_CICEROSCM_PY2,
    _ciceroscm_major_version,
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
_MEMBER_INDICES = [0, 1, 2]
_TEST_SCENARIOS = ("ssp126", "ssp245", "ssp370")
_REGRESSION_YEARS = (1850, 1900, 2000, 2025, 2050, 2100)
_REGRESSION_VARIABLES = (
    "Surface Air Temperature Change",
    "Effective Radiative Forcing",
)

fair2_skip = pytest.mark.skipif(
    not HAS_FAIR2, reason="fair>=2 not installed"
)
cicero_skip = pytest.mark.skipif(
    not HAS_CICEROSCM_PY2 or _ciceroscm_major_version() < 2,
    reason="ciceroscm>=2 not installed",
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
def smoke_scenarios(test_scenarios):
    """SSP126/SSP245/SSP370 subset used in the smoke tests."""
    return test_scenarios.filter(scenario=list(_TEST_SCENARIOS))


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


def _result_to_regression_dict(result):
    """
    Flatten the run output into a flat dict for ``num_regression.check``.

    One key per (scenario, variable, run_id, year), value is the
    scalar timeseries entry. ``num_regression`` is happiest with a
    flat numeric mapping; we keep the key structure stable so a diff
    is easy to read.
    """
    snapshot = {}
    for variable in _REGRESSION_VARIABLES:
        sub = result.filter(variable=variable, year=list(_REGRESSION_YEARS))
        ts = sub.timeseries(time_axis="year")
        for index_tuple, row in ts.iterrows():
            meta = dict(zip(ts.index.names, index_tuple))
            scenario = meta["scenario"]
            run_id = meta.get("run_id", 0)
            for year, val in row.items():
                key = f"{scenario}|{variable}|run{run_id}|{int(year)}"
                snapshot[key] = float(val)
    return snapshot


@pytest.mark.parametrize(
    "adapter_factory",
    [
        pytest.param(
            _build_fair2_ed, marks=fair2_skip, id="fair2-emissions-driven"
        ),
        pytest.param(
            _build_fair2_cd, marks=fair2_skip, id="fair2-concentration-driven"
        ),
        pytest.param(
            _build_cicero_ed, marks=cicero_skip, id="cicero-emissions-driven"
        ),
        pytest.param(
            _build_cicero_cd,
            marks=cicero_skip,
            id="cicero-concentration-driven",
        ),
    ],
)
def test_adapter_smoke(adapter_factory, smoke_scenarios, num_regression):
    """
    Construct the adapter via its native-distribution classmethod,
    run a 3-member ensemble across ssp126/ssp245/ssp370, and check
    GSAT and total ERF against a pytest-regressions snapshot at
    1850, 1900, 2000, 2025, 2050 and 2100.
    """
    adapter = adapter_factory()
    result = openscm_runner.run.run([adapter], scenarios=smoke_scenarios)

    variables_seen = set(result.get_unique_meta("variable"))
    for var in _REGRESSION_VARIABLES:
        assert var in variables_seen, var

    num_regression.check(_result_to_regression_dict(result))
