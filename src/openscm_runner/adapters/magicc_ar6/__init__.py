"""
Adapters for MAGICC as used in its AR6 probabilistic configuration

These all use MAGICC v7.5.3
with the AR6 probabilistic distribution (600 ensemble members).
Neither ships with this package, so you pass their locations in
(via [MAGICCAR6AdapterConfiguration][(p).], which every adapter takes)
or download them with a magicc.org token
([MAGICCAR6AdapterConfiguration.from_token][(p).]).
[MAGICCAR6AdapterConfiguration.from_environment][(p).] does either,
depending on which environment variables are set (it's what our tests use).
You can get the token (or download them yourself)
from https://magicc.org/download/magicc7 after logging in.

Implemented:

- AR6 scenarios, including anthropogenic-only and CO2-forcing-only versions
- CMIP experiments branching off CMIP6 or CMIP7 pre-industrial:
  CO2-concentration-driven, concentration-driven, CO2-emission-driven,
  esm-style and esm-allGHG-style
- ERF-driven experiments starting from equilibrium

!!! note "We probably won't implement any more adapters for MAGICC AR6"

    Setting MAGICC v7.5.3 up for anything other than
    the AR6 scenario runs it was built for is too annoying,
    as getting the CMIP-style runs to work properly showed
    (see [openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch][]).
    So these are likely the only adapters there will be for MAGICC AR6.
    In particular, there won't be an AR7 scenario adapter
    ([MAGICCAR6AdapterAR7Scenario][(p).] raises `NotImplementedError`).
    The exception: we could do an adapter for an experiment starting in 1750
    if we needed it (that is how MAGICC v7.5.3 was set up to run,
    so it would be much easier than the CMIP-style runs).

!!! warning "Emissions-driven CMIP-style runs differ from AR6's setup"

    In the CO2-emission-driven, esm-style and esm-allGHG-style adapters,
    the CO2 fertilisation, carbon cycle temperature feedback
    and CH4/N2O lifetime feedbacks start at the start of the run
    (relative to the piControl state),
    rather than in the calendar years AR6's setup uses (1900, 1900, 1927, 1925).
    We had to change this to get sensible emissions-driven runs from piControl,
    but it means these adapters' carbon cycle (and CH4/N2O cycles) don't behave
    exactly as in AR6, e.g. CO2 fertilisation acts relative to
    the piControl concentration rather than the 1900 concentration.
    See [openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch][].

Layers:

- `base`: the configuration and running shared by the adapters
- `ar_scenarios`, `cmip_pre_industrial_branch`, `erf`: the adapters
- `naming`: translating our names and units to and from MAGICC's
- `running`: runs the MAGICC executable (serially or in parallel),
  knows nothing about experiments
- `io`: MAGICC's file formats
- `ensemble`, `pre_industrial`: fixed inputs
  (the AR6 probabilistic distribution, piControl values)
- `download`: getting MAGICC and the distribution from magicc.org
"""

from .ar_scenarios import (
    MAGICCAR6AdapterAR6Scenario,
    MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
    MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
    MAGICCAR6AdapterAR7Scenario,
)
from .base import (
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6NotFoundError,
    undo_magicc_emissions_averaging,
)
from .cmip_pre_industrial_branch import (
    MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial,
    MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial,
    MAGICCAR6AdapterESMFromCMIP6PreIndustrial,
    MAGICCAR6AdapterESMFromCMIP7PreIndustrial,
)
from .download import (
    MAGICCAR6AdapterPieces,
    MAGICCDownloadError,
    get_magicc_ar6_adapter_pieces,
)
from .erf import MAGICCAR6AdapterERFDrivenFromEquilibrium

__all__ = [
    "MAGICCAR6AdapterAR6Scenario",
    "MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly",
    "MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly",
    "MAGICCAR6AdapterAR7Scenario",
    "MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial",
    "MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial",
    "MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial",
    "MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial",
    "MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial",
    "MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial",
    "MAGICCAR6AdapterConfiguration",
    "MAGICCAR6AdapterERFDrivenFromEquilibrium",
    "MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial",
    "MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial",
    "MAGICCAR6AdapterESMFromCMIP6PreIndustrial",
    "MAGICCAR6AdapterESMFromCMIP7PreIndustrial",
    "MAGICCAR6AdapterPieces",
    "MAGICCAR6NotFoundError",
    "MAGICCDownloadError",
    "get_magicc_ar6_adapter_pieces",
    "undo_magicc_emissions_averaging",
]
