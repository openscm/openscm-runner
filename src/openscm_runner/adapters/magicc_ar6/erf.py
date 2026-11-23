"""
MAGICC AR6 adapter for ERF-driven experiments starting from equilibrium
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from openscm_runner.erf import ERF, AdapterERFDrivenFromEquilibrium, verify_erf
from openscm_runner.output import EnsembleMemberResult, OpenSCMRunnerOutput
from openscm_runner.output_specs import OutputSpecs

from .base import (
    END_YEAR_BUFFER,
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6Experiment,
    format_forcing_in,
    get_experiment_levels,
    hold_last_value,
    run_experiments,
)
from .naming import convert_units, get_output_variables, get_unique_variable_timeseries

MAGICC_START_YEAR = 1849
"""
Year MAGICC starts in (with zero ERF, in equilibrium)

The input's first year is put on the year after this.
"""

SUPPORTED_OUTPUT_VARIABLES: tuple[str, ...] = (
    "Surface Air Temperature Change",
    "Effective Radiative Forcing",
    "Heat Uptake",
)
"""Outputs this adapter can provide"""
# MAGICC's other calculations (e.g. the gas cycles) still run,
# but don't affect the climate.
# So the only outputs we offer are the temperature, the ERF and the heat uptake.


def get_erf_values(erf: pd.DataFrame) -> pd.Series[float]:
    """
    Get the ERF values from an input (in W/m^2)

    Parameters
    ----------
    erf
        Input (see [ERF][openscm_runner.erf.])

    Returns
    -------
    :
        ERF (W/m^2), years as the index

    Raises
    ------
    ValueError
        The input doesn't have exactly one timeseries
    """
    timeseries = get_unique_variable_timeseries(erf, description="ERF")
    if timeseries.shape[0] != 1:
        msg = f"Expected exactly one ERF timeseries, received {timeseries.shape[0]}"
        raise ValueError(msg)

    converted = convert_units(timeseries, ["W/m^2"], callable_name="get_erf_values")

    return converted.iloc[0].astype(float)


def run_erf_experiments(
    erf: tuple[ERF, ...],
    output_specs: OutputSpecs,
    *,
    configuration: MAGICCAR6AdapterConfiguration,
) -> tuple[OpenSCMRunnerOutput, ...]:
    """
    Run ERF-driven experiments starting from equilibrium

    The inputs aren't verified here,
    verification is a decision to be made by callers of this function
    using e.g. [verify_erf][openscm_runner.erf.].

    Parameters
    ----------
    erf
        Inputs (each one is exactly one experiment)

    output_specs
        Outputs to return

    configuration
        Configuration to run with

    Returns
    -------
    :
        One output per input, in input order
    """
    output_variables = get_output_variables(
        output_specs.output_variables, SUPPORTED_OUTPUT_VARIABLES
    )

    experiments = []
    input_years = []
    for inp in erf:
        values = get_erf_values(inp)
        years = [int(y) for y in values.index]
        input_years.append(years)

        # MAGICC is run on a fixed calendar
        # to avoid settings that are tied to calendar years.
        # We shift the output to match the desired output years.
        # We only provided output from one year after we start MAGICC,
        # so we can handle abrupt step experiments.
        output_first_year = MAGICC_START_YEAR + 1
        output_last_year = output_first_year + len(years) - 1
        # Zero ERF in the start year, then the input on MAGICC's calendar.
        # The zero year is what makes abrupt steps work
        # (the step is applied in full in the input's first year).
        on_magicc_calendar = pd.concat(
            [
                pd.Series([0.0], index=[MAGICC_START_YEAR]),
                pd.Series(
                    values.to_numpy(),
                    index=range(output_first_year, output_last_year + 1),
                ),
            ]
        )
        # ERF runs need the extension too:
        # without it, heat uptake differs in the last year (temperature doesn't)
        extended = hold_last_value(
            on_magicc_calendar.to_frame().T, END_YEAR_BUFFER
        ).iloc[0]

        # Name of the ERF file we write
        ERF_FILE = "OPENSCM_RUNNER_EXTRA_RF.IN"

        experiments.append(
            MAGICCAR6Experiment(
                files={ERF_FILE: format_forcing_in("EXTRA_RF", extended)},
                settings={
                    # Pass in forcing as 'extra'
                    "rf_total_runmodus": "QEXTRA",
                    "rf_extra_read": 1,
                    "file_extra_rf": ERF_FILE,
                    # Set things so the forcing is provided as given
                    "rf_extra_offset": 0.0,
                    "rf_extra_factor": 1.0,
                    "rf_efficacy_qxtra": 1.0,
                    # Start in equilibrium in the (zero ERF) start year.
                    # JUMPSTART makes no difference with zero ERF in the start year,
                    # but it makes sure nothing is shifted.
                    "rf_initialization_method": "JUMPSTART",
                    "rf_preind_referenceyr": MAGICC_START_YEAR,
                },
                start_year=MAGICC_START_YEAR,
                end_year=output_last_year + END_YEAR_BUFFER,
                output_first_year=output_first_year,
                output_last_year=output_last_year,
                output_variables=output_variables,
                experiment_levels=get_experiment_levels(inp),
            )
        )

    outputs = run_experiments(experiments, configuration=configuration)

    return tuple(
        OpenSCMRunnerOutput(
            members=tuple(_to_input_years(member, years) for member in output.members)
        )
        for output, years in zip(outputs, input_years, strict=True)
    )


def _to_input_years(
    member: EnsembleMemberResult, years: list[int]
) -> EnsembleMemberResult:
    if not member.succeeded:
        return member

    data = member.data.copy()
    data.columns = years

    return EnsembleMemberResult.from_success(member.ensemble_member, data)


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterERFDrivenFromEquilibrium:
    """
    MAGICC AR6 adapter for ERF-driven experiments starting from equilibrium
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        erf: tuple[ERF, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments, returning one output per input, in input order"""
        if self.configuration.run_checks:
            verify_erf(erf)

        return run_erf_experiments(erf, output_specs, configuration=self.configuration)


if TYPE_CHECKING:
    # mypy checks that the adapter satisfies its protocol
    # (see the note in `ar_scenarios`)
    def _check_erf(
        adapter: MAGICCAR6AdapterERFDrivenFromEquilibrium,
    ) -> AdapterERFDrivenFromEquilibrium:
        return adapter
