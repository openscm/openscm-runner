"""
Standardised interfaces for running simple climate models (SCMs)

The pieces:

- input definitions: a type alias per kind of input
  (e.g. [AR7Scenario][openscm_runner.ar_scenarios.inputs.]),
  defined by its `verify_*` function
  (e.g. [verify_ar7_scenarios][openscm_runner.ar_scenarios.inputs.]).
  If your input passes the `verify_*` function,
  it matches the definition (or there is a bug in our code).
- adapter protocols
  (e.g. [AdapterAR7Scenario][openscm_runner.ar_scenarios.running.]):
  what adapters implement.
  Adapters don't have to verify their inputs (but can if they wish).
- run functions
  (e.g. [run_ar7_scenarios][openscm_runner.ar_scenarios.running.]): what users call.
  They verify the inputs once, run each adapter
  and return the results in a [RunResults][openscm_runner.output.] container.

Each group of experiments lives in its own subpackage
([ar_scenarios][openscm_runner.ar_scenarios],
[cmip_pre_industrial_branch][openscm_runner.cmip_pre_industrial_branch],
[erf][openscm_runner.erf]).
"""

import importlib.metadata

# Rename adapter_errors to just errors ?
from .adapter_errors import InvalidInputError, UnsupportedOutputError
from .ar_scenarios import (
    AdapterAR6Scenario,
    # TODO: note details still being worked out
    AdapterAR6ScenarioAnthropogenicOnly,
    # TODO: note details still being worked out
    AdapterAR6ScenarioCO2ForcingOnly,
    AdapterAR7Scenario,
    AR6Scenario,
    # TODO: note details still being worked out
    AR6ScenarioCO2Emissions,
    AR7Scenario,
    run_ar6_scenarios,
    run_ar6_scenarios_anthropogenic_only,
    run_ar6_scenarios_co2_forcing_only,
    run_ar7_scenarios,
    # TODO: note details still being worked out
    verify_ar6_scenario_co2_emissions,
    verify_ar6_scenarios,
    verify_ar7_scenarios,
)
from .cmip_pre_industrial_branch import (
    # TODO: note details still being worked out
    AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
    # TODO: note details still being worked out
    AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
    # TODO: note details still being worked out
    AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
    # TODO: note details still being worked out
    AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
    AdapterConcentrationDrivenFromCMIP6PreIndustrial,
    AdapterConcentrationDrivenFromCMIP7PreIndustrial,
    AdapterESMAllGHGFromCMIP6PreIndustrial,
    AdapterESMAllGHGFromCMIP7PreIndustrial,
    AdapterESMFromCMIP6PreIndustrial,
    AdapterESMFromCMIP7PreIndustrial,
    CMIP6PreIndustrialBranchCO2Concentrations,
    # Rename to CMIP6PreIndustrialBranchIdealisedCO2Emissions once we clarify usage?
    CMIP6PreIndustrialBranchCO2Emissions,
    CMIP6PreIndustrialBranchConcentrations,
    CMIP6PreIndustrialBranchESMAllGHGInput,
    CMIP6PreIndustrialBranchESMInput,
    CMIP7PreIndustrialBranchCO2Concentrations,
    # Rename to CMIP7PreIndustrialBranchIdealisedCO2Emissions once we clarify usage?
    CMIP7PreIndustrialBranchCO2Emissions,
    CMIP7PreIndustrialBranchConcentrations,
    CMIP7PreIndustrialBranchESMAllGHGInput,
    CMIP7PreIndustrialBranchESMInput,
    run_co2_concentration_driven_from_cmip6_pre_industrial,
    run_co2_concentration_driven_from_cmip7_pre_industrial,
    run_co2_emission_driven_from_cmip6_pre_industrial,
    run_co2_emission_driven_from_cmip7_pre_industrial,
    run_concentration_driven_from_cmip6_pre_industrial,
    run_concentration_driven_from_cmip7_pre_industrial,
    run_esm_all_ghg_from_cmip6_pre_industrial,
    run_esm_all_ghg_from_cmip7_pre_industrial,
    run_esm_from_cmip6_pre_industrial,
    run_esm_from_cmip7_pre_industrial,
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
from .erf import (
    ERF,
    AdapterERFDrivenFromEquilibrium,
    run_erf_driven_from_equilibrium,
    verify_erf,
)
from .output import (
    AdapterOutputError,
    AdapterRunResult,
    EnsembleMemberResult,
    OpenSCMRunnerOutput,
    RunResults,
)
from .output_specs import (
    STANDARD_OUTPUT_VARIABLES,
    OutputCapabilities,
    OutputSpecs,
    validate_output_request,
)
from .running import run_adapters

__all__ = [
    "ERF",
    "STANDARD_OUTPUT_VARIABLES",
    "AR6Scenario",
    "AR6ScenarioCO2Emissions",
    "AR7Scenario",
    "AdapterAR6Scenario",
    "AdapterAR6ScenarioAnthropogenicOnly",
    "AdapterAR6ScenarioCO2ForcingOnly",
    "AdapterAR7Scenario",
    "AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial",
    "AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial",
    "AdapterCO2EmissionDrivenFromCMIP6PreIndustrial",
    "AdapterCO2EmissionDrivenFromCMIP7PreIndustrial",
    "AdapterConcentrationDrivenFromCMIP6PreIndustrial",
    "AdapterConcentrationDrivenFromCMIP7PreIndustrial",
    "AdapterERFDrivenFromEquilibrium",
    "AdapterESMAllGHGFromCMIP6PreIndustrial",
    "AdapterESMAllGHGFromCMIP7PreIndustrial",
    "AdapterESMFromCMIP6PreIndustrial",
    "AdapterESMFromCMIP7PreIndustrial",
    "AdapterOutputError",
    "AdapterRunResult",
    "CMIP6PreIndustrialBranchCO2Concentrations",
    "CMIP6PreIndustrialBranchCO2Emissions",
    "CMIP6PreIndustrialBranchConcentrations",
    "CMIP6PreIndustrialBranchESMAllGHGInput",
    "CMIP6PreIndustrialBranchESMInput",
    "CMIP7PreIndustrialBranchCO2Concentrations",
    "CMIP7PreIndustrialBranchCO2Emissions",
    "CMIP7PreIndustrialBranchConcentrations",
    "CMIP7PreIndustrialBranchESMAllGHGInput",
    "CMIP7PreIndustrialBranchESMInput",
    "EnsembleMemberResult",
    "InvalidInputError",
    "OpenSCMRunnerOutput",
    "OutputCapabilities",
    "OutputSpecs",
    "RunResults",
    "UnsupportedOutputError",
    "run_adapters",
    "run_ar6_scenarios",
    "run_ar6_scenarios_anthropogenic_only",
    "run_ar6_scenarios_co2_forcing_only",
    "run_ar7_scenarios",
    "run_co2_concentration_driven_from_cmip6_pre_industrial",
    "run_co2_concentration_driven_from_cmip7_pre_industrial",
    "run_co2_emission_driven_from_cmip6_pre_industrial",
    "run_co2_emission_driven_from_cmip7_pre_industrial",
    "run_concentration_driven_from_cmip6_pre_industrial",
    "run_concentration_driven_from_cmip7_pre_industrial",
    "run_erf_driven_from_equilibrium",
    "run_esm_all_ghg_from_cmip6_pre_industrial",
    "run_esm_all_ghg_from_cmip7_pre_industrial",
    "run_esm_from_cmip6_pre_industrial",
    "run_esm_from_cmip7_pre_industrial",
    "validate_output_request",
    "verify_ar6_scenario_co2_emissions",
    "verify_ar6_scenarios",
    "verify_ar7_scenarios",
    "verify_cmip6_pre_industrial_branch_co2_concentrations",
    "verify_cmip6_pre_industrial_branch_co2_emissions",
    "verify_cmip6_pre_industrial_branch_concentrations",
    "verify_cmip6_pre_industrial_branch_esm_all_ghg_inputs",
    "verify_cmip6_pre_industrial_branch_esm_inputs",
    "verify_cmip7_pre_industrial_branch_co2_concentrations",
    "verify_cmip7_pre_industrial_branch_co2_emissions",
    "verify_cmip7_pre_industrial_branch_concentrations",
    "verify_cmip7_pre_industrial_branch_esm_all_ghg_inputs",
    "verify_cmip7_pre_industrial_branch_esm_inputs",
    "verify_erf",
]

__version__ = importlib.metadata.version("openscm_runner")
