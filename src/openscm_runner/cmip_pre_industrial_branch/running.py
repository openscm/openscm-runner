"""
Adapter protocols and run functions for CMIP experiments branching off pre-industrial
"""
# Developer notes
#
# The CO2-only experiments are deliberately separate from the CMIP-style ones,
# even though the adapter back-end can be the same:
#
# - CO2-concentration-driven vs. CMIP-style concentration-driven:
#   in CO2-only runs, everything except CO2 is held at pre-industrial levels.
#   So it can be the same call to the model,
#   the CO2-only adapter just has hard-coded infilling of the other species
#   (and a different input definition).
# - CO2-emission-driven vs. CMIP esm-style
#   (emission-driven CO2, other species prescribed):
#   the same relationship.
# - CMIP esm-allGHG-style: emission-driven GHGs
#   (natural forcing and aerosol emissions prescribed, as in esm-style).
#
# Having separate entry points means users have to be explicit
# about what they are running.

from __future__ import annotations

from typing import Protocol

from openscm_runner.output import OpenSCMRunnerOutput, RunResults
from openscm_runner.output_specs import OutputCapabilities, OutputSpecs
from openscm_runner.running import run_adapters

from .inputs import (
    CMIP6PreIndustrialBranchCO2Concentrations,
    CMIP6PreIndustrialBranchCO2Emissions,
    CMIP6PreIndustrialBranchConcentrations,
    CMIP6PreIndustrialBranchESMAllGHGInput,
    CMIP6PreIndustrialBranchESMInput,
    CMIP7PreIndustrialBranchCO2Concentrations,
    CMIP7PreIndustrialBranchCO2Emissions,
    CMIP7PreIndustrialBranchConcentrations,
    CMIP7PreIndustrialBranchESMAllGHGInput,
    CMIP7PreIndustrialBranchESMInput,
    verify_cmip6_pre_industrial_branch_co2_concentrations,
    verify_cmip6_pre_industrial_branch_co2_emissions,
    verify_cmip6_pre_industrial_branch_concentrations,
    verify_cmip6_pre_industrial_branch_esm_all_ghg_inputs,
    verify_cmip6_pre_industrial_branch_esm_inputs,
    verify_cmip7_pre_industrial_branch_co2_concentrations,
    verify_cmip7_pre_industrial_branch_co2_emissions,
    verify_cmip7_pre_industrial_branch_concentrations,
    verify_cmip7_pre_industrial_branch_esm_all_ghg_inputs,
    verify_cmip7_pre_industrial_branch_esm_inputs,
)

# Note: mypy can't tell the CMIP6 and CMIP7 protocols apart
# (same argument names, and the input aliases are all `pd.DataFrame`).
# We accept this, see `docs/further-background/architecture.md`.


class AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CO2-concentration-driven experiments from CMIP7 pre-industrial

    Idealised experiments in which only the CO2 concentrations change
    (e.g. abrupt-4xCO2 or 1pctCO2).

    The adapter is responsible for starting
    from its CMIP7 pre-industrial (piControl) state
    and holding everything other than CO2 at pre-industrial levels for the whole run.

    Forcing: CO2 only.

    Open decisions: which feedbacks CO2-only runs include (decision [B16][b16])
    and what values to use as pre-industrial (decision [B19][b19]).
    """

    def __call__(
        self,
        co2_concentrations: tuple[CMIP7PreIndustrialBranchCO2Concentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        co2_concentrations
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `co2_concentrations`
        """


# The run functions in all the experiment subpackages follow the same pattern
# (verify the inputs if `run_checks`, then run each adapter with `run_adapters`),
# so their docstrings are the same apart from the experiment and the input's name.


def run_co2_concentration_driven_from_cmip7_pre_industrial(
    co2_concentrations: tuple[CMIP7PreIndustrialBranchCO2Concentrations, ...],
    *,
    adapters: tuple[AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial]:
    """
    Run CO2-concentration-driven experiments from CMIP7 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    co2_concentrations
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip7_pre_industrial_branch_co2_concentrations(co2_concentrations)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            co2_concentrations=co2_concentrations, output_specs=output_specs
        ),
        n_inputs=len(co2_concentrations),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CO2-concentration-driven experiments from CMIP6 pre-industrial

    As for [AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial][(m).],
    except that the adapter starts from its CMIP6 pre-industrial state.
    """

    def __call__(
        self,
        co2_concentrations: tuple[CMIP6PreIndustrialBranchCO2Concentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        co2_concentrations
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `co2_concentrations`
        """


def run_co2_concentration_driven_from_cmip6_pre_industrial(
    co2_concentrations: tuple[CMIP6PreIndustrialBranchCO2Concentrations, ...],
    *,
    adapters: tuple[AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial]:
    """
    Run CO2-concentration-driven experiments from CMIP6 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    co2_concentrations
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip6_pre_industrial_branch_co2_concentrations(co2_concentrations)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            co2_concentrations=co2_concentrations, output_specs=output_specs
        ),
        n_inputs=len(co2_concentrations),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterConcentrationDrivenFromCMIP7PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CMIP-style concentration-driven experiments from CMIP7 pre-industrial

    Experiments in which the GHG concentrations are prescribed,
    as in CMIP's concentration-driven experiments (e.g. historical).

    The adapter is responsible for starting
    from its CMIP7 pre-industrial (piControl) state.

    Forcing: from the GHG concentrations, the natural forcing
    and the aerosol and ozone precursor emissions.

    Open decisions: how land-use forcing is handled (decision [B07][b07]),
    when chemistry and other feedbacks are on (decision [B18][b18]),
    what values to use as pre-industrial (decision [B19][b19])
    and the form of the natural forcing (decision [B22][b22]).
    """  # noqa: E501

    def __call__(
        self,
        concentrations: tuple[CMIP7PreIndustrialBranchConcentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        concentrations
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `concentrations`
        """


def run_concentration_driven_from_cmip7_pre_industrial(
    concentrations: tuple[CMIP7PreIndustrialBranchConcentrations, ...],
    *,
    adapters: tuple[AdapterConcentrationDrivenFromCMIP7PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterConcentrationDrivenFromCMIP7PreIndustrial]:
    """
    Run CMIP-style concentration-driven experiments from CMIP7 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    concentrations
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """  # noqa: E501
    if run_checks:
        verify_cmip7_pre_industrial_branch_concentrations(concentrations)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            concentrations=concentrations, output_specs=output_specs
        ),
        n_inputs=len(concentrations),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterConcentrationDrivenFromCMIP6PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CMIP-style concentration-driven experiments from CMIP6 pre-industrial

    As for [AdapterConcentrationDrivenFromCMIP7PreIndustrial][(m).],
    except that the adapter starts from its CMIP6 pre-industrial state.
    """  # noqa: E501

    def __call__(
        self,
        concentrations: tuple[CMIP6PreIndustrialBranchConcentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        concentrations
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `concentrations`
        """


def run_concentration_driven_from_cmip6_pre_industrial(
    concentrations: tuple[CMIP6PreIndustrialBranchConcentrations, ...],
    *,
    adapters: tuple[AdapterConcentrationDrivenFromCMIP6PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterConcentrationDrivenFromCMIP6PreIndustrial]:
    """
    Run CMIP-style concentration-driven experiments from CMIP6 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    concentrations
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """  # noqa: E501
    if run_checks:
        verify_cmip6_pre_industrial_branch_concentrations(concentrations)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            concentrations=concentrations, output_specs=output_specs
        ),
        n_inputs=len(concentrations),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterCO2EmissionDrivenFromCMIP7PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CO2-emission-driven experiments from CMIP7 pre-industrial

    Idealised experiments in which only the CO2 emissions change
    (e.g. esm-flat10).

    The adapter is responsible for starting from its CMIP7 (esm-)pre-industrial state
    and holding everything other than CO2 at pre-industrial levels for the whole run.

    Forcing: CO2 only (its concentrations follow from the emissions).

    Open decisions: which feedbacks CO2-only runs include (decision [B16][b16])
    and what values to use as pre-industrial (decision [B19][b19]).
    """

    def __call__(
        self,
        co2_emissions: tuple[CMIP7PreIndustrialBranchCO2Emissions, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        co2_emissions
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `co2_emissions`
        """


def run_co2_emission_driven_from_cmip7_pre_industrial(
    co2_emissions: tuple[CMIP7PreIndustrialBranchCO2Emissions, ...],
    *,
    adapters: tuple[AdapterCO2EmissionDrivenFromCMIP7PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterCO2EmissionDrivenFromCMIP7PreIndustrial]:
    """
    Run CO2-emission-driven experiments from CMIP7 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    co2_emissions
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip7_pre_industrial_branch_co2_emissions(co2_emissions)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            co2_emissions=co2_emissions, output_specs=output_specs
        ),
        n_inputs=len(co2_emissions),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterCO2EmissionDrivenFromCMIP6PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CO2-emission-driven experiments from CMIP6 pre-industrial

    As for [AdapterCO2EmissionDrivenFromCMIP7PreIndustrial][(m).],
    except that the adapter starts from its CMIP6 (esm-)pre-industrial state.
    """

    def __call__(
        self,
        co2_emissions: tuple[CMIP6PreIndustrialBranchCO2Emissions, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        co2_emissions
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `co2_emissions`
        """


def run_co2_emission_driven_from_cmip6_pre_industrial(
    co2_emissions: tuple[CMIP6PreIndustrialBranchCO2Emissions, ...],
    *,
    adapters: tuple[AdapterCO2EmissionDrivenFromCMIP6PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterCO2EmissionDrivenFromCMIP6PreIndustrial]:
    """
    Run CO2-emission-driven experiments from CMIP6 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    co2_emissions
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip6_pre_industrial_branch_co2_emissions(co2_emissions)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            co2_emissions=co2_emissions, output_specs=output_specs
        ),
        n_inputs=len(co2_emissions),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterESMFromCMIP7PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CMIP esm-style experiments from CMIP7 pre-industrial

    Experiments in which CO2 is emission-driven
    and the other GHGs are concentration-driven,
    as in CMIP's esm experiments (e.g. esm-hist).

    The adapter is responsible for starting from its CMIP7 (esm-)pre-industrial state.

    Forcing: from the CO2 emissions (via the carbon cycle),
    the other GHG concentrations, the natural forcing
    and the aerosol and ozone precursor emissions.

    Open decisions: how land-use forcing is handled (decision [B07][b07]),
    when chemistry and other feedbacks are on (decision [B18][b18]),
    what values to use as pre-industrial (decision [B19][b19])
    and the form of the natural forcing (decision [B22][b22]).
    """

    def __call__(
        self,
        esm_inputs: tuple[CMIP7PreIndustrialBranchESMInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        esm_inputs
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `esm_inputs`
        """


def run_esm_from_cmip7_pre_industrial(
    esm_inputs: tuple[CMIP7PreIndustrialBranchESMInput, ...],
    *,
    adapters: tuple[AdapterESMFromCMIP7PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterESMFromCMIP7PreIndustrial]:
    """
    Run CMIP esm-style experiments from CMIP7 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    esm_inputs
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip7_pre_industrial_branch_esm_inputs(esm_inputs)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(esm_inputs=esm_inputs, output_specs=output_specs),
        n_inputs=len(esm_inputs),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterESMAllGHGFromCMIP7PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CMIP esm-allGHG-style experiments from CMIP7 pre-industrial

    Experiments in which every GHG is emission-driven.

    The adapter is responsible for starting from its CMIP7 (esm-)pre-industrial state.

    Forcing: from the GHG emissions (via the gas cycles), the natural forcing
    and the aerosol and ozone precursor emissions.

    Open decisions: how land-use forcing is handled (decision [B07][b07]),
    when chemistry and other feedbacks are on (decision [B18][b18]),
    what values to use as pre-industrial (decision [B19][b19])
    and the form of the natural forcing (decision [B22][b22]).
    """

    def __call__(
        self,
        esm_all_ghg_inputs: tuple[CMIP7PreIndustrialBranchESMAllGHGInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        esm_all_ghg_inputs
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `esm_all_ghg_inputs`
        """


def run_esm_all_ghg_from_cmip7_pre_industrial(
    esm_all_ghg_inputs: tuple[CMIP7PreIndustrialBranchESMAllGHGInput, ...],
    *,
    adapters: tuple[AdapterESMAllGHGFromCMIP7PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterESMAllGHGFromCMIP7PreIndustrial]:
    """
    Run CMIP esm-allGHG-style experiments from CMIP7 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    esm_all_ghg_inputs
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip7_pre_industrial_branch_esm_all_ghg_inputs(esm_all_ghg_inputs)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            esm_all_ghg_inputs=esm_all_ghg_inputs, output_specs=output_specs
        ),
        n_inputs=len(esm_all_ghg_inputs),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterESMFromCMIP6PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CMIP esm-style experiments from CMIP6 pre-industrial

    As for [AdapterESMFromCMIP7PreIndustrial][(m).],
    except that the adapter starts from its CMIP6 (esm-)pre-industrial state.
    """

    def __call__(
        self,
        esm_inputs: tuple[CMIP6PreIndustrialBranchESMInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        esm_inputs
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `esm_inputs`
        """


def run_esm_from_cmip6_pre_industrial(
    esm_inputs: tuple[CMIP6PreIndustrialBranchESMInput, ...],
    *,
    adapters: tuple[AdapterESMFromCMIP6PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterESMFromCMIP6PreIndustrial]:
    """
    Run CMIP esm-style experiments from CMIP6 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    esm_inputs
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip6_pre_industrial_branch_esm_inputs(esm_inputs)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(esm_inputs=esm_inputs, output_specs=output_specs),
        n_inputs=len(esm_inputs),
        output_specs=output_specs,
        run_checks=run_checks,
    )


class AdapterESMAllGHGFromCMIP6PreIndustrial(OutputCapabilities, Protocol):
    """
    Adapter that can run CMIP esm-allGHG-style experiments from CMIP6 pre-industrial

    As for [AdapterESMAllGHGFromCMIP7PreIndustrial][(m).],
    except that the adapter starts from its CMIP6 (esm-)pre-industrial state.
    """

    def __call__(
        self,
        esm_all_ghg_inputs: tuple[CMIP6PreIndustrialBranchESMAllGHGInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """
        Run the experiments

        Adapters don't have to verify the inputs (the `run_*` function does).

        Parameters
        ----------
        esm_all_ghg_inputs
            Inputs to run (each element is exactly one experiment)

        output_specs
            Outputs to return

        Returns
        -------
        :
            One output per input, in the same order as `esm_all_ghg_inputs`
        """


def run_esm_all_ghg_from_cmip6_pre_industrial(
    esm_all_ghg_inputs: tuple[CMIP6PreIndustrialBranchESMAllGHGInput, ...],
    *,
    adapters: tuple[AdapterESMAllGHGFromCMIP6PreIndustrial, ...],
    output_specs: OutputSpecs,
    run_checks: bool = True,
) -> RunResults[AdapterESMAllGHGFromCMIP6PreIndustrial]:
    """
    Run CMIP esm-allGHG-style experiments from CMIP6 pre-industrial with each adapter

    This is the interface we recommend:
    calling adapters directly is for experts
    (adapters don't have to verify their inputs).

    Parameters
    ----------
    esm_all_ghg_inputs
        Inputs to run (each element is exactly one experiment)

    adapters
        Adapters to run the experiments with

    output_specs
        Outputs to return.
        If `run_checks`, an adapter which doesn't support them all isn't called
        (the error is recorded in its result).

    run_checks
        Whether to verify the inputs and check each adapter's output support.
        Only turn this off if you know what you are doing.
        The checks of the returned outputs (count and type) are always done
        and adapters may still do their own checks.

    Returns
    -------
    :
        Result for each adapter, in the same order as `adapters`
    """
    if run_checks:
        verify_cmip6_pre_industrial_branch_esm_all_ghg_inputs(esm_all_ghg_inputs)

    return run_adapters(
        adapters,
        call=lambda adapter: adapter(
            esm_all_ghg_inputs=esm_all_ghg_inputs, output_specs=output_specs
        ),
        n_inputs=len(esm_all_ghg_inputs),
        output_specs=output_specs,
        run_checks=run_checks,
    )
