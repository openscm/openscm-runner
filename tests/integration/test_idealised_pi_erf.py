"""Idealised conc-driven runs hold non-CO2 forcing at pre-industrial.

For an idealised experiment (abrupt-4xCO2) driven by CO2 concentration
only, every non-CO2 species should sit at its PI baseline, so the
non-CO2 ERF (total minus CO2) should be ~0 at the branch point. This
guards the FaIR2 idealised baseline fix: non-CO2 emissions-mode species
are pinned to ``baseline_emissions`` (not zero emissions), so their PI
forcing is ~0 rather than a constant ~1 W/m^2 aerosol offset.

Scope: FaIR2 only. The other adapters auto-handle idealised scenarios
differently and do not expose a directly comparable total / CO2 ERF
pair:
  * MAGICC7 does not auto-detect idealised scenarios and uses non-PI
    built-in defaults for non-conc species unless an esm-piControl
    emissions overlay is supplied (see the "Idealised experiments"
    docs page), so a conc-only assertion would not hold for it.
  * CICEROSCMPY2 exposes only component-wise ERF (no plain total /
    CO2 ERF), so a non-CO2 assertion needs adapter-specific
    aggregation -- a follow-up.

Env-gated: needs the full RCMIP3 bundle (the mini fixture lacks
abrupt-4xCO2 concentrations). Point ``RCMIP3_BUNDLE`` at it.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from scmdata import ScmRun

import openscm_runner.run
from openscm_runner import RunMode
from openscm_runner.adapters import FAIR2
from openscm_runner.adapters.fair2_adapter._compat import HAS_FAIR2
from openscm_runner.io import load_rcmip3_concentrations

pytestmark = pytest.mark.faircicero2_only

FAIR2_BUNDLE = Path(__file__).parent.parent / "test-data" / "fair2-mini-bundle"
RCMIP3_BUNDLE = os.environ.get(
    "RCMIP3_BUNDLE", "/storage/no-backup-nac/users/bensan/rcmip3_protocol",
)
SCENARIO = "abrupt-4xCO2"
PI_YEAR = 1850  # branch point: CO2 still ~PI, so total ERF ~ CO2 ERF
ERF = "Effective Radiative Forcing"
ERF_CO2 = "Effective Radiative Forcing|CO2"


def _has_full_bundle() -> bool:
    try:
        return not load_rcmip3_concentrations(
            RCMIP3_BUNDLE, scenarios=[SCENARIO],
        ).empty
    except Exception:
        return False


def _idealised_conc_scenario() -> ScmRun:
    """abrupt-4xCO2 CO2 concentration trajectory as a conc-driven ScmRun."""
    conc = load_rcmip3_concentrations(RCMIP3_BUNDLE, scenarios=[SCENARIO])
    co2 = conc[
        conc["Variable"].str.fullmatch("Atmospheric Concentrations.CO2")
    ].iloc[0]
    year_cols = [c for c in conc.columns if isinstance(c, str) and c.isdigit()]
    return ScmRun(pd.DataFrame({
        "model": ["protocol"], "scenario": [SCENARIO], "region": ["World"],
        "variable": ["Atmospheric Concentrations|CO2"], "unit": ["ppm"],
        **{int(c): [float(co2[c])] for c in year_cols},
    }))


@pytest.mark.skipif(not HAS_FAIR2, reason="fair>=2 not installed")
@pytest.mark.skipif(
    not _has_full_bundle(),
    reason=f"full RCMIP3 bundle with {SCENARIO} concentrations not found "
    f"(set RCMIP3_BUNDLE)",
)
def test_fair2_idealised_nonco2_erf_is_pi_zero():
    adapter = FAIR2.from_native_distribution(
        calibration_dir=FAIR2_BUNDLE, rcmip3_bundle_path=RCMIP3_BUNDLE,
        mode=RunMode.CONCENTRATION_DRIVEN, member_indices=[0],
        output_variables=(ERF, ERF_CO2),
    )
    res = openscm_runner.run.run([adapter], scenarios=_idealised_conc_scenario())
    ts = res.timeseries(time_axis="year")

    def _value(variable):
        sub = ts[ts.index.get_level_values("variable") == variable]
        assert not sub.empty, f"adapter did not output {variable!r}"
        return float(sub.iloc[0].get(PI_YEAR))

    total, co2 = _value(ERF), _value(ERF_CO2)
    non_co2 = total - co2
    # Everything but CO2 is held at PI -> non-CO2 ERF ~ 0 at the branch.
    # (Before the fix this carried a constant ~+0.6 W/m^2 aerosol offset.)
    assert abs(non_co2) < 0.1, (
        f"non-CO2 ERF at {PI_YEAR} = {non_co2:+.3f} W/m^2 "
        f"(total={total:+.3f}, CO2={co2:+.3f}); expected ~0"
    )
