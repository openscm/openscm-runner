"""
Integration tests: the MAGICC AR6 adapter for ERF-driven runs from equilibrium
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from openscm_runner import (
    run_erf_driven_from_equilibrium,
)
from openscm_runner.adapters.magicc_ar6 import (
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6AdapterERFDrivenFromEquilibrium,
)
from openscm_runner.adapters.magicc_ar6.base import MAGICC_VERSION
from openscm_runner.adapters.magicc_ar6.running import MAGICCRunError
from openscm_runner.output_specs import OutputSpecs

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

# These are the MAGICC AR6 adapters' tests (see docs/development/testing.md)
pytestmark = pytest.mark.magicc_ar6

N_MEMBERS = 2
# Faster than two workers for two members (~0.8s vs ~1.0s)
N_WORKERS = 1


def make_erf(values: np.ndarray[Any, Any], first_year: int, name: str) -> pd.DataFrame:
    return pd.DataFrame(
        [values],
        index=pd.MultiIndex.from_tuples(
            [(name, "Effective Radiative Forcing", "World", "W/m^2")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=range(first_year, first_year + len(values)),
    )


def test_erf_driven_from_equilibrium() -> None:
    """
    The ERF applied is exactly the input, from equilibrium, starting in any year
    """
    n_years = 150
    inputs = (
        make_erf(np.full(n_years, 3.7), 0, "abrupt"),
        make_erf(np.zeros(n_years), 1, "zero"),
        make_erf(np.linspace(0.0, 3.0, n_years), 2000, "ramp"),
    )
    results = run_erf_driven_from_equilibrium(
        inputs,
        adapters=(
            MAGICCAR6AdapterERFDrivenFromEquilibrium(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=OutputSpecs(
            output_variables=(
                "Surface Air Temperature Change",
                "Effective Radiative Forcing",
                "Heat Uptake",
            )
        ),
    )
    results.raise_if_any_failed()
    for output in results[0].outputs:
        output.raise_if_any_failed()

    abrupt, zero, ramp = (o.as_df() for o in results[0].outputs)

    for inp, res in zip(inputs, (abrupt, zero, ramp), strict=True):
        erf = res.xs("Effective Radiative Forcing", level="variable")
        # Back on the input's years
        assert erf.columns.tolist() == inp.columns.tolist()
        # Exactly the input (no efficacy, no natural forcing)
        np.testing.assert_allclose(
            erf.to_numpy(), np.broadcast_to(inp.to_numpy(), erf.shape), atol=1e-12
        )

    np.testing.assert_allclose(
        zero.xs("Surface Air Temperature Change", level="variable").to_numpy(),
        0.0,
        atol=1e-12,
    )
    abrupt_temperature = abrupt.xs("Surface Air Temperature Change", level="variable")
    # The step acts from the first year
    assert (abrupt_temperature[0] > 0.1).all()
    assert (abrupt_temperature[n_years - 1] > 1.5).all()


def test_more_than_one_timeseries_without_checks() -> None:
    """Without the input checks, the adapter still refuses more than one timeseries"""
    # (With the checks, `verify_erf` catches this first.)
    erf = pd.concat(
        [
            make_erf(np.zeros(10), 1850, "two-timeseries"),
            make_erf(np.ones(10), 1850, "two-timeseries").rename(
                {"Effective Radiative Forcing": "Effective Radiative Forcing|CO2"},
                level="variable",
            ),
        ]
    )
    adapter = MAGICCAR6AdapterERFDrivenFromEquilibrium(
        configuration=MAGICCAR6AdapterConfiguration.from_environment(
            testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS, run_checks=False
        )
    )

    with pytest.raises(ValueError, match="Expected exactly one ERF timeseries"):
        adapter(
            (erf,),
            output_specs=OutputSpecs(
                output_variables=("Surface Air Temperature Change",)
            ),
        )


def make_failing_binary(tmp_path: Path) -> Path:
    """Make a MAGICC binary which reports the right version but fails every run"""
    # Unix only (a shell script).
    # Windows would need a .cmd file, but the adapters don't support Windows yet anyway
    # (e.g. they symlink MAGICC's run directory) and CI doesn't run on Windows.
    binary = tmp_path / "failing-magicc"
    binary.write_text(
        "#!/bin/sh\n"
        # Pass the installation's version check,
        # so the failure happens when each ensemble member is run.
        # (We can't ask the real binary for its version:
        # on macOS it needs `DYLD_LIBRARY_PATH`, which `/bin/sh` strips.)
        'if [ "$1" = "--version" ]; then\n'
        f"  echo {MAGICC_VERSION}\n"
        "  exit 0\n"
        "fi\n"
        'echo "<FATAL> deliberately failing for a test"\n'
        "exit 1\n"
    )
    binary.chmod(0o755)

    return binary


def test_failed_members_are_reported_not_raised(tmp_path: Path) -> None:
    """If MAGICC fails, each member's result records the error (nothing is raised)"""
    adapter = MAGICCAR6AdapterERFDrivenFromEquilibrium(
        configuration=MAGICCAR6AdapterConfiguration.from_environment(
            testing_only_n_members=N_MEMBERS,
            n_workers=N_WORKERS,
            magicc_binary=make_failing_binary(tmp_path),
        )
    )

    (output,) = adapter(
        (make_erf(np.full(10, 1.0), 1, "step"),),
        output_specs=OutputSpecs(output_variables=("Surface Air Temperature Change",)),
    )

    assert len(output.members) == N_MEMBERS
    for member in output.members:
        assert not member.succeeded
        assert isinstance(member.error, MAGICCRunError)
        assert "deliberately failing" in str(member.error)

    # Every member failed, so all their errors are raised together
    with pytest.raises(ExceptionGroup) as excinfo:
        output.raise_if_any_failed()

    assert len(excinfo.value.exceptions) == N_MEMBERS
    assert excinfo.group_contains(MAGICCRunError, match="deliberately failing")
