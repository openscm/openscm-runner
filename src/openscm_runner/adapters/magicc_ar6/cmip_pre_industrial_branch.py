"""
MAGICC AR6 adapters for CMIP experiments branching off pre-industrial

[This should be double checked once we lock these experiment definitions down exactly.]
All of MAGICC's forcing agents are included.
Everything the inputs don't prescribe
(land use, stratospheric water vapour etc.)
is calculated by MAGICC from the concentrations and from emissions.
So in a piControl experiment everything stays at exactly zero,
and e.g. ozone responds to changes in CH4 and N2O concentrations.

How the runs are set up:

1. **MAGICC's pre-industrial is the piControl state.**
   MAGICC starts in [MAGICC_START_YEAR][(m).] (1830)
   and runs [PI_CONTROL_SPIN_UP_YEARS][(m).] (20) years in the piControl state,
   and output is returned from 1850 (the experiment's first year).
   MAGICC's pre-industrial reference year (`RF_PREIND_REFERENCEYR`)
   is set to the start year, and forcing is relative to pre-industrial
   (`RF_INITIALIZATION_METHOD = "JUMPSTART"`).
   So every pre-industrial reference MAGICC uses
   (the CO2, CH4 and N2O reference concentrations,
   the aerosol precursor emissions, each member's natural SO2 emissions,
   the aerosol and land-use forcing etc.) is the piControl state,
   all forcing is zero in the start year and the model starts in equilibrium.
    - This isn't a recalibration: the AR6 calibration's parameters are unchanged.
      But it does change the reference concentrations in the GHG forcing
      formulae compared to the AR6 setup (1750 values),
      which matters a little because the formulae aren't
      logarithms of ratios alone (e.g. the CO2-N2O overlap terms),
      see [openscm_runner.adapters.magicc_ar6.pre_industrial][].
      This is a good illustration of the fact
      that we have been loose with our definition of physics up until now
      (are pre-industrial states physics or not),
      we would like to be better with this in future if we can
      (or maybe differences like this are already correct).
    - Starting before 1850 is needed for experiments like abrupt-4xCO2:
      if MAGICC started in 1850, 4 x piControl CO2 would be the reference
      and the output wouldn't be what we want.
      More than one year of spin-up is needed for emissions-driven runs
      (see point 2).
    - We first tried shifting all forcing to zero in the first year instead
      (`ZEROSTARTSHIFT`) with MAGICC's default (1750) reference year.
      That doesn't work cleanly with v7.5.3:
      the ozone forcing due to N2O doesn't respect the flag
      (giving a constant ~0.003 W/m^2 in a CMIP7 piControl)
      and the first year's tropospheric ozone isn't calculated
      but has the shift subtracted (a one-year pulse of ~0.04 W/m^2,
      giving a ~0.002 K drift).
      With the set up we have now, these issues go away.
2. **Concentrations and emissions.**
   Each of MAGICC's gas groups (CO2, CH4, N2O, F-gases, Montreal Protocol gases,
   [GAS_GROUPS][(m).]) is emissions-driven from 1850
   if the input has emissions for it,
   otherwise concentration-driven for the whole run
   (`*_SWITCHFROMCONC2EMIS_YEAR`).
   The `CONC.IN` files hold the piControl concentrations before 1850
   and the input from 1850
   (see [openscm_runner.adapters.magicc_ar6.pre_industrial][]),
   so emissions-driven gases start from their piControl concentrations.
   This is how the CMIP6 and CMIP7 adapters differ.
    - CH4 and N2O: MAGICC derives natural emissions
      so that the concentrations are in balance with the emissions
      over the 10 years before `CH4_LASTBUDGETYEAR` and `N2O_LASTBUDGETYEAR`.
      We set these to 1849, so the natural emissions are those which balance
      the piControl concentrations and piControl emissions
      (which is why the spin-up is longer than a year).
    - Halogenated gases: MAGICC has no natural emissions for these,
      so the input's emissions are totals (including natural emissions,
      e.g. of CH3Cl and CH3Br, as in the AR6 scenarios).
      If the piControl emissions (see point 4) aren't in balance
      with MAGICC's lifetimes and the piControl concentrations,
      the concentrations drift
      (with MAGICC's own 1850 emissions, CH3Cl and CH3Br drop ~1% in the first year
      then stay roughly constant).
    - CO2: we use zero piControl CO2 emissions
      (no fossil emissions and no land-use change,
      as RCMIP phase 3's CMIP6 esm-piControl does).
      This is a choice, not a given:
      CMIP's guidance usually says to repeat the 1850 values,
      which would mean non-zero CO2 emissions (decision [B19][b19]).
      The carbon cycle starts close to, but not exactly in, equilibrium:
      with zero emissions, CO2 drifts up by a few tenths of a ppm over 150 years.
3. **Solar and volcanic forcing** come from the input
   (zero for the CO2-only inputs) and are zero before 1850,
   i.e. the piControl natural forcing is zero
   and the input is relative to piControl.
   This is a choice which is still to be confirmed:
   what zero (piControl) natural forcing means is still to be decided
   (e.g. RCMIP phase 3's natural forcing isn't zero in 1850, see decision [B19][b19]).
   Without this, MAGICC would apply its default historical solar
   and volcanic forcing.
   See the warnings below: the input isn't used as-is.
4. **Emissions** are written to a `.SCEN7` from MAGICC's start year
   (see [make_scenario_emissions][(m).]).
   The piControl emissions are hard-coded for each CMIP era
   ([get_pi_control_emissions][(m).]): the era's historical emissions in 1850
   (CO2: zero, see point 2), a choice which is still to be confirmed
   (decision [B19][b19]).
   They are used for the spin-up years
   and, for the whole run, for gases which aren't in the input.
   So if the input isn't at piControl in its first year,
   there is a response in the first year
   (as for concentrations, see point 2).
   MAGICC wants the emissions split into fossil/industrial and biomass burning,
   we split the totals using the split of MAGICC's own historical emissions
   in 1850, held fixed (see [make_scenario_emissions][(m).]).
   MAGICC adds the oxidation of fossil CH4 to fossil CO2,
   so piControl CH4 emissions are all put in the biomass burning sector
   (otherwise they would be a constant source of CO2 in emissions-driven runs)
   and only the change in CH4 emissions from piControl is split
   into fossil and biomass burning.
   MAGICC splits global emissions 50/50 between the hemispheres
   (the same as it does for its own, global, historical emissions),
   so that is the (fixed) regional pattern of the emissions.
   Nitrate, aerosol-cloud and tropospheric ozone forcing respond to these emissions
   via MAGICC's usual calculations
   (but see point 7 and the warning on aerosol-cloud forcing below).
5. **Direct aerosol, aerosol-cloud and BC on snow forcing.**
   MAGICC v7.5.3 takes these (and the optical thicknesses
   the aerosol-cloud forcing is calculated from) from its historical files
   and only uses emissions to extend the files beyond their last year.
   That extension can't start from piControl
   (for some files it divides by emissions relative to pre-industrial,
   which are zero in piControl).
   So we write these files ourselves, for the whole run,
   using MAGICC's own extension rule as if the files ended in 1850
   (see [EmissionsDrivenFile][(m).] and [derive_emissions_driven_files][(m).]).
   This means the regional pattern of each forcing is fixed at its 1850 pattern
   (in MAGICC's history files),
   which is the best we can do with global-only inputs.
   You can prescribe other patterns by calling
   [run_pre_industrial_branch_experiments][(m).] directly.
6. **Land use and mineral dust.** MAGICC drives land-use albedo
   and mineral dust forcing with cumulative biosphere CO2 emissions.
   We write these files in the same way as the aerosol files (point 5),
   driven by the biosphere CO2 emissions accumulated since piControl
   (zero unless the input has biosphere CO2 emissions,
   in which case the forcing stays at piControl).
   The sea salt and natural OC optical thickness files ([HELD_HISTORY_FILES][(m).])
   are written held at their 1850 values for the whole run
   (otherwise MAGICC would apply its own historical values).
7. **Regional normalisation (`RF_REGIONS_NORMYEAR`).**
   MAGICC v7.5.3 normalises several things by their value
   in `RF_REGIONS_NORMYEAR`, whatever the configuration:

    - the aerosol-cloud forcing in each region is the change in cloud droplet number
      divided by its change in `RF_REGIONS_NORMYEAR`,
      times each member's `RF_REGIONS_CLOUD_ALBEDO` and scaling factor
      (`src/MAGICC7.f90`, v7.5.3, around line 14954).
      If the change in `RF_REGIONS_NORMYEAR` is zero,
      the aerosol-cloud forcing in that region is zero for the whole run.
    - the regional split of nitrate forcing is overwritten with its split
      in `RF_REGIONS_NORMYEAR` (around line 4736), which is NaN if it is zero
      (`RF_REGIONS_NO3` only sets the land/ocean split; there is no way to
      prescribe it instead, later MAGICC versions add `RF_REGIONS_APPLY`)
    - the regional patterns used for the internal efficacies
      of the aerosol, land-use etc. forcings

   In AR6, `RF_REGIONS_NORMYEAR` is 2000, so all of these
   are normalised by (pinned to) the calibrated historical state in 2000.
   `RF_REGIONS_NORMYEAR` has to be in the run, but our runs don't include 2000.
   So we put MAGICC's historical aerosol state in 2000
   (its aerosol and aerosol/ozone precursor emissions
   and all the history files in 2000)
   into the last [NORMALISATION_ANCHOR_N_YEARS][(m).] years of the run
   and make the first of these `RF_REGIONS_NORMYEAR`
   ([NORMALISATION_ANCHOR_YEAR][(m).], [anchor_scenario_emissions][(m).]).
   These are buffer years, so we never return their output
   (and there is a normal buffer year between them and the output we do return).

/// warning | Some of MAGICC's settings are tied to calendar years
MAGICC v7.5.3 is set up for runs which start in 1750
and follow history, so some of its settings are calendar years.

- The carbon cycle's temperature feedback and CO2 fertilisation
  start in 1900 by default (relative to the state then),
  the CH4 and N2O lifetime feedbacks in 1927 and 1925.
  We start them in [MAGICC_START_YEAR][(m).] instead,
  see the warning below.
- These are left at MAGICC's defaults
  (they matter for runs which go past these years,
  as nominal years in idealised experiments):
  stratospheric ozone forcing is zero until 1979
  and relative to the 1979 EESC after that (`STRATOZ_THRESHOLD_YEAR`),
  stratospheric lifetimes respond to warming above the 1980 temperature
  (`GEN_CHANGE_MERIDIONALFLUX_YR`)
  and land-use and mineral dust forcing are constant after 2018
  (`RF_LANDUSE_CONSTANTAFTERYR`, `RF_MINERALDUST_CONSTANTAFTERYR`).
///

/// warning | Difference from AR6: when the carbon cycle and CH4/N2O feedbacks start
MAGICC v7.5.3's CO2 fertilisation and carbon cycle temperature feedback
start in 1900 by default (relative to the state then),
its CH4 and N2O lifetime feedbacks in 1927 and 1925.
These are calendar years, set up for runs which start in 1750.
For runs branching off piControl, we start them in [MAGICC_START_YEAR][(m).]
([FEEDBACK_START_YEAR_SETTINGS][(m).]),
so they act relative to the piControl state from the start.
Otherwise, e.g., an emissions-driven 1pctCO2 run
would have no CO2 fertilisation for its first 50 years
and the carbon cycle feedbacks would kick in part way through.

This is a difference from AR6's setup:
there, e.g., CO2 fertilisation acts relative to the 1900 concentration
(and not at all before 1900).
So the emissions-driven adapters' carbon cycle
(and CH4 and N2O cycles) don't behave exactly as in AR6,
even though the calibration's parameters are unchanged.
(For the concentration-driven adapters,
these feedbacks don't affect the outputs we return.)
///

/// note | Where MAGICC averages emissions over each year and the next
MAGICC v7.5.3's convention is that the emissions in year `t`
are the total for year `t`,
and the state at the start of year `t + 1` is calculated
from the state at the start of year `t` and the emissions in year `t`
(`src/MAGICC7.f90`, v7.5.3, around line 127).
The gas cycles, tropospheric ozone and nitrate use each year's emissions as given.

The exception is the aerosol forcing and optical thickness MAGICC derives
from emissions (direct aerosol, BC on snow
and, via the optical thicknesses, aerosol-cloud forcing).
These are start-of-year values calculated from the average of the emissions
in year `t` and year `t + 1`
(`extend_rf_box_from_switchyear_with_emissions` in MAGICC v7.5.3),
so for these a step change in emissions in year `y`
is half applied in year `y - 1`.
[undo_magicc_emissions_averaging][openscm_runner.adapters.magicc_ar6.base.]
gives emissions which these calculations see exactly as you want them,
but be careful: the same emissions also go, unaveraged,
into the gas cycles, tropospheric ozone and nitrate.

These adapters don't do anything about this:
we pass the emissions on as given,
because that is the behaviour MAGICC v7.5.3 has always had.
One side effect: because of this emissions averaging,
changing aerosol emissions in year `y` changes aerosol forcing
in years `y` and `y - 1`.
Then, sub-annual forcing is linearly interpolated,
so the forcing over year `y - 2` is the interpolation
of the `y - 2` and `y - 1` values.
Putting that together, altering aerosol emissions in year `y`
changes heat uptake in year `y - 2`.
(MAGICC v7.5.3's annual mean heat uptake also covers February to February,
rather than January to January, which looks like a bug.
This makes the change in `y - 2` bigger, but isn't what causes it,
see `src/MAGICC7.f90` in MAGICC v7.5.3, around lines 5250 and 6115.)

Land-use albedo and mineral dust forcing are calculated the same way,
from cumulative biosphere CO2 emissions,
so they see biosphere CO2 emissions half a year early too.
E.g. if the input's first year has non-zero biosphere CO2 emissions,
these forcings are already non-zero in the last spin-up year (1849),
so MAGICC isn't exactly in its piControl state before 1850.
There is nothing we can do about this with MAGICC v7.5.3's set up.
///

/// warning | The regional pattern of aerosol forcing is fixed at 1850
Direct aerosol, aerosol-cloud and BC on snow forcing respond to emissions
with the regional pattern (and, for fossil/industrial emissions,
the forcing per unit emissions) of MAGICC's history files in 1850.
In MAGICC's historical runs, this pattern changes over time
(as emissions move between regions).
For scenarios, MAGICC uses the pattern in the files' last year (2015).
For experiments branching off piControl,
1850 is the natural choice, but it means the same emissions change
gives different forcing here than in a scenario run.
///

/// warning | The aerosol-cloud forcing normalisation isn't perfect
The normalisation anchor (point 7 above) is the best we can do
with MAGICC v7.5.3, but it isn't the same as AR6.
The aerosol-cloud forcing is normalised by the change in cloud droplet number
from pre-industrial to 2000.
In AR6, pre-industrial is 1750.
Here, it is the piControl state (roughly MAGICC's 1850 state),
which already has more aerosol than 1750.
The change from pre-industrial to 2000 is therefore smaller here,
so the aerosol-cloud forcing for a given change in emissions
is somewhat stronger than AR6's calibration implies.
Fixing this exactly would need MAGICC's cloud droplet number calculation
to be re-implemented outside MAGICC (to correct each member's scaling).
///

/// warning | The solar and volcanic ERF you put in isn't the ERF MAGICC applies
The input solar and volcanic forcing is passed to MAGICC
as its solar and volcanic forcing input files.
Each member of the AR6 probabilistic distribution then:

- scales it: `RF_SOLAR_SCALE` (0.50-1.30, median 0.91)
  and `RF_VOLCANIC_SCALE` (0.50-1.10, median 0.77)
- applies its efficacy: `RF_EFFICACY_SOLAR` (0.60-1.10, median 0.84)
  and `RF_EFFICACY_VOLC` (0.67-1.23, median 0.93).
  These are parameters of each member (part of the calibration),
  not something MAGICC calculates.
  (MAGICC also calculates an internal efficacy from the regional pattern
  of each forcing, but that cancels out of the ERF.)

This is how AR6 used MAGICC (the scalings are part of the calibration
and represent the uncertainty in these forcings).
So the ERF applied is the input times scale times efficacy,
which differs from member to member.
Across the ensemble, the median factor is 0.75 for solar
(5-95%: 0.41-1.18) and 0.71 for volcanic (5-95%: 0.43-1.12).
The output `Effective Radiative Forcing|Solar` and
`Effective Radiative Forcing|Volcanic` are the ERF actually applied,
so they differ from the input
(also, the annual volcanic output is a mid-year to mid-year mean,
so a one-year volcanic input is spread over two years of output).
If you need the input ERF applied exactly, this adapter doesn't do that.
(TODO: decide what the input definition should mean here,
see `CMIP_NATURAL_FORCING_VARIABLES`.)
///

/// warning | Annual volcanic forcing isn't ideal for MAGICC
MAGICC works best with volcanic forcing prescribed monthly
(it runs on a monthly timestep and volcanic forcing varies within a year).
The input definition only has annual values, so we repeat each annual value
for every month of that year.
This isn't an ideal way to use MAGICC,
but it is what the input definition requires.
///

/// note | Should the ozone response to warming be in idealised CO2 runs?
With all forcing agents included, the total ERF includes MAGICC's
ozone response to warming (`OZDUETOTEMPERATURE_SCALE`,
about -0.038 W/m^2 per K for the median member, 5-95%: -0.054 to -0.020).
In 1pctCO2 after 140 years, that's roughly -0.16 W/m^2.
It's not clear whether this should be in idealised CO2-only experiments
(e.g. 1pctCO2, abrupt-4xCO2) or not:
ESMs with interactive chemistry would include it,
ESMs with prescribed ozone wouldn't.
///

All the adapters use the same back-end
([run_pre_industrial_branch_experiments][(m).]).
The CO2-only adapters hold every other gas at its piControl concentration,
emissions at piControl and solar and volcanic forcing at zero.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
import pandas as pd

from openscm_runner.cmip_pre_industrial_branch import (
    AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
    AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
    AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
    AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
    AdapterConcentrationDrivenFromCMIP6PreIndustrial,
    AdapterConcentrationDrivenFromCMIP7PreIndustrial,
    AdapterESMAllGHGFromCMIP6PreIndustrial,
    AdapterESMAllGHGFromCMIP7PreIndustrial,
    AdapterESMFromCMIP6PreIndustrial,
    AdapterESMFromCMIP7PreIndustrial,
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
from openscm_runner.output import OpenSCMRunnerOutput
from openscm_runner.output_specs import OutputSpecs

from .base import (
    END_YEAR_BUFFER,
    FILE_HEADER,
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6Experiment,
    format_conc_in,
    format_forcing_in,
    format_hemispheric_monthly_forcing_in,
    format_scen7,
    get_experiment_levels,
    run_experiments,
)
from .io import format_tabular_file, read_namelist, read_tabular_file
from .naming import (
    EMISSIONS_UNIT_CONVERSION_CONTEXTS,
    EMISSIONS_VARIABLES,
    FGAS_NAMES,
    MHALO_NAMES,
    OUTPUT_VARIABLES,
    convert_units,
    get_output_variables,
    split_emissions,
    split_natural_forcing,
    to_magicc_concentrations,
    to_magicc_emissions,
)
from .pre_industrial import (
    ALL_CONCENTRATION_GASES,
    CMIP6_PRE_INDUSTRIAL,
    CMIP7_PRE_INDUSTRIAL,
    PreIndustrialValues,
)
from .running import NO_EXTRA_SCENARIO_FILES, MAGICCInstallation

PI_CONTROL_SPIN_UP_YEARS = 20
"""
Number of years MAGICC runs in the piControl state before the experiment starts

These are needed so MAGICC can derive the natural CH4 and N2O emissions
from the piControl state (it uses the 10 years before the switch to emissions,
plus a year's delay for N2O), see the module docstring.
"""

# TODO: handle this better.
# Don't want hard-coded 1850.
# Don't want to assume a single pre-industrial branch year will apply for all CMIP eras.
MAGICC_START_YEAR = 1850 - PI_CONTROL_SPIN_UP_YEARS
"""
Year MAGICC starts in, holding the piControl state

This is also MAGICC's pre-industrial reference year (`RF_PREIND_REFERENCEYR`).
See the module docstring for why.
"""

FEEDBACK_START_YEAR_SETTINGS: tuple[str, ...] = (
    "co2_tempfeedback_yrstart",
    "co2_fertilization_yrstart",
    "ch4_feed_yrstart",
    "n2o_feed_yrstart",
)
"""
Settings for the years in which MAGICC's carbon cycle and CH4/N2O feedbacks start

MAGICC's defaults are calendar years (1900, 1900, 1927, 1925).
We set them to [MAGICC_START_YEAR][(m).], see the module docstring.
"""

NO_OZONE_DUE_TO_TEMPERATURE: dict[str, Any] = {"ozduetotemperature_scale": 0.0}
"""
Settings which turn off MAGICC's ozone forcing due to temperature

MAGICC adds an ozone forcing proportional to the warming
(`OZDUETOTEMPERATURE_SCALE` times the global-mean surface air temperature change,
about -0.04 W/m^2/K in the AR6 probabilistic distribution).
It is part of MAGICC's total ozone forcing,
but not its tropospheric or stratospheric ozone forcing.

The CO2-only adapters turn it off for now, so their only forcing is CO2 forcing.
It isn't clear which choice is right (see decisions [B16][b16] and [B18][b18]):
CMIP models with prescribed ozone wouldn't have this forcing,
CMIP models with interactive chemistry probably would.
We might make the opposite choice.
We could also offer both (a prescribed-ozone-like adapter
and an interactive-chemistry-like adapter),
but that opens up a huge number of cases to support,
so it's unlikely to be what we do.

The same question applies to the other CMIP adapters
(e.g. the full concentration-driven adapters),
which include this forcing at the moment.
They should probably follow the same logic as the CO2-only adapters.
At the moment, the two conflict:
the full concentration-driven adapters act like a model with interactive chemistry,
the CO2-only concentration-driven adapters like a model with prescribed ozone.
Deciding what we want is one thing.
Working out if and how MAGICC can do it is another:
e.g. in the full adapters, tropospheric ozone forcing also responds
to CH4 concentrations and ozone precursor emissions,
so turning this forcing off wouldn't be enough
to make them act like a model with prescribed ozone.
This doesn't affect the AR6 scenario adapters:
their CO2-forcing-only adapter only has CO2 forcing driving the climate anyway
(`RF_TOTAL_RUNMODUS = "CO2"`).
"""

HELD_HISTORY_FILES: tuple[str, ...] = (
    "file_ocn_ot",
    "file_ss_ot",
)
"""
Historical optical thickness files which we hold at their 1850 values

These are natural (organic carbon and sea salt), nothing in the inputs drives them.
"""

EMISSIONS_DRIVEN_FILE_RULES: dict[str, tuple[tuple[str, ...], str]] = {
    "file_soxi_rf": (("SOXI",), "relative"),
    "file_bci_rf": (("BCI",), "relative"),
    "file_oci_rf": (("OCI",), "relative"),
    "file_soxb_rf": (("SOXB",), "delta"),
    "file_bcb_rf": (("BCB",), "delta"),
    "file_ocb_rf": (("OCB",), "delta"),
    "file_bcsnow_rf": (("BCI", "BCB"), "absolute"),
    "file_soxi_ot": (("SOXI",), "absolute"),
    "file_soxnb_ot": (("SOXB", "SOXN"), "absolute"),
    "file_bci_ot": (("BCI",), "absolute"),
    "file_bcb_ot": (("BCB",), "absolute"),
    "file_oci_ot": (("OCI",), "absolute"),
    "file_ocb_ot": (("OCB",), "absolute"),
    "file_landuse_rf": (("CO2B",), "absolute-cumulative"),
    "file_mineraldust_rf": (("CO2B",), "absolute-cumulative"),
}
"""
History files which respond to emissions: the emissions which drive each one
and the rule MAGICC v7.5.3 uses to extend it beyond its last year

The rules (from `EXTRAP_RF_WITH_EMIS` and
`extend_rf_box_from_switchyear_with_emissions` in MAGICC v7.5.3,
with the settings in the AR6 probabilistic distribution
and MAGICC's defaults):

- `"relative"`: proportional to emissions relative to pre-industrial (1750)
  (`RF_*_DIR_APPLY = 2`)
- `"delta"`: the change in emissions is added
  (with the sign of the forcing),
  times the emissions' share in each hemisphere (0.5)
  (`RF_*_DIR_APPLY = 3`, MAGICC's default for the biomass burning species,
  which the AR6 distribution doesn't change)
- `"absolute"`: proportional to emissions
  (optical thicknesses and BC on snow)
- `"absolute-cumulative"`: proportional to cumulative emissions
  (land-use albedo and mineral dust, driven by cumulative biosphere CO2 emissions,
  cumulative since 1750 in MAGICC's history)

`SOXN` is MAGICC's natural SOx emissions (held constant).
"""

HEMISPHERE_EMISSIONS_SHARE = 0.5
"""Share of global emissions MAGICC puts in each hemisphere (for global input)"""

INSTALLATION_PRE_INDUSTRIAL_YEAR = 1750
"""
Pre-industrial year of MAGICC's historical files

The `"relative"` rule in [EMISSIONS_DRIVEN_FILE_RULES][(m).] is relative to this.
"""

# TODO: double check whether this should be 1830 so we can handle step changes in 1850
# for emissions-driven?
# Or maybe this is doing something different to what I think it is.
PATTERN_YEAR = 1850
"""Year whose regional pattern we use for the emissions-driven history files"""

NORMALISATION_ANCHOR_YEAR = 2000
"""
Year whose aerosol state we put in the normalisation years (see the module docstring)

This is AR6's (and MAGICC's default) `RF_REGIONS_NORMYEAR`.
"""

NORMALISATION_ANCHOR_N_YEARS = 2
"""
Number of years at the end of the run which hold the anchor state

The first of these is `RF_REGIONS_NORMYEAR`.
We use two so that the anchor state holds at both the start and the end
of `RF_REGIONS_NORMYEAR` (MAGICC uses both start-of-year values,
some calculated from the average of each year's and the next year's emissions,
and annual emissions, see the note in the module docstring).
They are buffer years, so their output is never returned
(and the buffer year before them keeps them away from the output we return).
"""
if END_YEAR_BUFFER < NORMALISATION_ANCHOR_N_YEARS + 1:  # pragma: no cover
    raise AssertionError(END_YEAR_BUFFER)

SCENARIO_FILE = "OPENSCM_RUNNER_EMMS.SCEN7"
SOLAR_FILE = "OPENSCM_RUNNER_SOLAR_RF.IN"
VOLCANIC_FILE = "OPENSCM_RUNNER_VOLCANIC_RF.MON"

SUPPORTED_OUTPUT_VARIABLES: tuple[str, ...] = tuple(OUTPUT_VARIABLES)
"""Outputs these adapters can provide"""

AEROSOL_GASES: tuple[str, ...] = ("SOX", "CO", "NMVOC", "NOX", "BC", "OC", "NH3")
"""Aerosol and aerosol/ozone precursor species (MAGICC's names, as totals)"""

SCEN7_GASES: tuple[str, ...] = (
    *(
        f"{gas}{sector}"
        for gas in ("CO2", "CH4", "N2O", *AEROSOL_GASES)
        for sector in ("I", "B")
    ),
    *FGAS_NAMES,
    *MHALO_NAMES,
)
"""Gases we write into the `.SCEN7` file (MAGICC's names)"""

SCEN7_UNITS: dict[str, str] = {
    **{
        f"{spec.gas}{sector}": spec.magicc_unit
        for spec in EMISSIONS_VARIABLES.values()
        if spec.gas in ("CH4", "N2O", *AEROSOL_GASES)
        for sector in ("I", "B")
    },
    "CO2I": EMISSIONS_VARIABLES["Emissions|CO2|Fossil"].magicc_unit,
    "CO2B": EMISSIONS_VARIABLES["Emissions|CO2|Biosphere"].magicc_unit,
    **{
        spec.gas: spec.magicc_unit
        for spec in EMISSIONS_VARIABLES.values()
        if spec.gas in (*FGAS_NAMES, *MHALO_NAMES)
    },
}
"""Units of the gases in [SCEN7_GASES][(m).] (MAGICC's units)"""


def load_historical_emissions(installation: MAGICCInstallation) -> pd.DataFrame:
    """
    Load the installation's historical emissions

    Parameters
    ----------
    installation
        MAGICC installation

    Returns
    -------
    :
        Global emissions of each gas in [SCEN7_GASES][(m).] (in [SCEN7_UNITS][(m).])
        plus natural SOx emissions (`"SOXN"`), years as columns.
        Back-filled with the first value if a file starts later than another
        (MAGICC does the same).
    """
    defaults = read_namelist(installation.run_dir / "MAGCFG_DEFAULTALL.CFG")[
        "nml_allcfgs"
    ]
    files = {
        **dict(zip(FGAS_NAMES, defaults["fgas_files_emis"], strict=True)),
        **dict(zip(MHALO_NAMES, defaults["mhalo_files_emis"], strict=True)),
    }
    values = {}
    for gas in (*SCEN7_GASES, "SOXN"):
        filename = files[gas] if gas in files else defaults[f"file_{gas.lower()}_emis"]
        data, _ = read_tabular_file(installation.run_dir / filename)
        values[gas] = data.sum(axis="index")

    return pd.DataFrame(values).T.sort_index(axis="columns").bfill(axis="columns")


@dataclass(frozen=True)
class EmissionsDrivenFile:
    """
    A history file which we write from emissions, with a fixed regional pattern

    The file's value in each box (northern ocean, northern land,
    southern ocean, southern land) is

    `reference_values + sensitivities * (drivers - reference_driver)`

    where `drivers` is the sum of the emissions of [drivers][(c).],
    averaged over each year and the next
    (the rule MAGICC uses for these files,
    see the note in the module docstring).
    """

    setting: str
    """The setting that points MAGICC at the file (e.g. `"file_soxi_rf"`)"""

    drivers: tuple[str, ...]
    """
    Emissions which drive the file (MAGICC's names)

    These are summed.
    """

    reference_values: tuple[float, float, float, float]
    """The file's values (in each box) when the drivers are at `reference_driver`"""

    cumulative: bool = field(default=False, kw_only=True)
    """
    Whether the file is driven by cumulative emissions

    If `True`, `drivers` are cumulative emissions:
    `reference_driver` plus the emissions accumulated since the first year
    given to [values][(c).] (in excess of that year's emissions).
    """

    reference_driver: float
    """Value of the drivers at which the file has `reference_values`"""

    sensitivities: tuple[float, float, float, float]
    """Change in the file's values (in each box) per unit change in the drivers"""

    def values(self, emissions: pd.DataFrame) -> pd.DataFrame:
        """
        Get the file's values

        Parameters
        ----------
        emissions
            Global emissions, indexed by MAGICC's name for each gas,
            including (at least) [drivers][(c).], years as columns

        Returns
        -------
        :
            The file's values: one row per box, years as columns
        """
        drivers = emissions.loc[list(self.drivers)].sum(axis="index")
        if self.cumulative:
            drivers = self.reference_driver + (drivers - drivers.iloc[0]).cumsum()

        # Average of each year and the next, the last year is held
        midyear = (drivers + drivers.shift(-1)) / 2
        midyear.iloc[-1] = midyear.iloc[-2]

        return pd.DataFrame(
            {
                year: np.array(self.reference_values)
                + np.array(self.sensitivities) * (value - self.reference_driver)
                for year, value in midyear.items()
            }
        )


def _to_box_values(
    values: np.ndarray[Any, Any],
) -> tuple[float, float, float, float]:
    if values.shape != (4,):  # pragma: no cover
        raise AssertionError(values.shape)

    return (float(values[0]), float(values[1]), float(values[2]), float(values[3]))


def derive_emissions_driven_files(
    installation: MAGICCInstallation, year: int = PATTERN_YEAR
) -> tuple[EmissionsDrivenFile, ...]:
    """
    Derive the emissions-driven history files from the installation's history

    This applies MAGICC v7.5.3's own extension rule
    (see [EMISSIONS_DRIVEN_FILE_RULES][(m).])
    as if the history files ended in `year`.
    So the regional pattern of each file is fixed at its pattern in `year`.

    Parameters
    ----------
    installation
        MAGICC installation

    year
        Year whose pattern to use

    Returns
    -------
    :
        The emissions-driven history files
    """
    defaults = read_namelist(installation.run_dir / "MAGCFG_DEFAULTALL.CFG")[
        "nml_allcfgs"
    ]
    historical_emissions = load_historical_emissions(installation)

    out = []
    for setting, (drivers, rule) in EMISSIONS_DRIVEN_FILE_RULES.items():
        data, _ = read_tabular_file(installation.run_dir / defaults[setting])
        reference_values = data[year].to_numpy(dtype=float)

        driver_history = historical_emissions.loc[list(drivers)].sum(axis="index")
        cumulative = rule == "absolute-cumulative"
        if cumulative:
            driver_history = driver_history.loc[
                INSTALLATION_PRE_INDUSTRIAL_YEAR:
            ].cumsum()

        reference_driver = float((driver_history[year] + driver_history[year + 1]) / 2)

        if rule == "relative":
            sensitivities = reference_values / (
                reference_driver - driver_history[INSTALLATION_PRE_INDUSTRIAL_YEAR]
            )
        elif rule == "delta":
            sensitivities = np.where(
                reference_values < 0.0,
                -HEMISPHERE_EMISSIONS_SHARE,
                HEMISPHERE_EMISSIONS_SHARE,
            )
        elif rule in ("absolute", "absolute-cumulative"):
            sensitivities = reference_values / reference_driver
        else:  # pragma: no cover
            raise NotImplementedError(rule)

        out.append(
            EmissionsDrivenFile(
                setting=setting,
                drivers=drivers,
                reference_values=_to_box_values(reference_values),
                reference_driver=reference_driver,
                sensitivities=_to_box_values(sensitivities),
                cumulative=cumulative,
            )
        )

    return tuple(out)


def make_concentration_files(
    concentrations: pd.DataFrame,
    pre_industrial: PreIndustrialValues,
    *,
    first_year: int,
    last_year: int,
) -> tuple[dict[str, str], dict[str, Any]]:
    """
    Make the concentration input files and the settings that point MAGICC at them

    Parameters
    ----------
    concentrations
        Concentrations in MAGICC's names (index), integer years as columns,
        starting in `first_year`.
        Gases MAGICC knows but which aren't given are held
        at their piControl value.

    pre_industrial
        Pre-industrial values to use

    first_year
        First year of the experiment
        (the years from [MAGICC_START_YEAR][(m).] until then
        hold the piControl state)

    last_year
        Last year to write (including any buffer)

    Returns
    -------
    files :
        File name to contents

    settings :
        Settings which point MAGICC at the files
    """
    files = {}
    filenames = {}
    pi_control_years = np.arange(MAGICC_START_YEAR, first_year)
    for gas in ALL_CONCENTRATION_GASES:
        if gas in concentrations.index:
            experiment = concentrations.loc[gas]
        else:
            experiment = pd.Series(
                pre_industrial.pi_control_concentrations[gas],
                index=concentrations.columns,
            )

        experiment = experiment.reindex(range(first_year, last_year + 1)).ffill()
        values = pd.Series(
            np.concatenate(
                [
                    np.full(
                        len(pi_control_years),
                        pre_industrial.pi_control_concentrations[gas],
                    ),
                    experiment.to_numpy(dtype=float),
                ]
            ),
            index=[*pi_control_years, *experiment.index],
        )
        filename = f"OPENSCM_RUNNER_{gas}_CONC.IN"
        files[filename] = format_conc_in(gas, values)
        filenames[gas] = filename

    settings = {
        "file_co2_conc": filenames["CO2"],
        "file_ch4_conc": filenames["CH4"],
        "file_n2o_conc": filenames["N2O"],
        # MAGICC matches these to gases by position,
        # in the order of its own `FGAS_NAMES` and `MHALO_NAMES`
        # (see the notes on `FGAS_NAMES`)
        "fgas_files_conc": [filenames[g] for g in FGAS_NAMES],
        "mhalo_files_conc": [filenames[g] for g in MHALO_NAMES],
    }

    return files, settings


def make_history_files(  # noqa: PLR0913
    installation: MAGICCInstallation,
    emissions_driven_files: Sequence[EmissionsDrivenFile],
    *,
    emissions: pd.DataFrame,
    first_year: int,
    last_year: int,
    anchor_years: Sequence[int],
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Make the aerosol, land use etc. history files (see the module docstring)

    Each file in [HELD_HISTORY_FILES][(m).] holds the installation's value
    in `first_year` from [MAGICC_START_YEAR][(m).] to `last_year`.
    The others are calculated from `emissions`.
    In `anchor_years`, every file holds the installation's value
    in [NORMALISATION_ANCHOR_YEAR][(m).].

    Parameters
    ----------
    installation
        MAGICC installation (the source of the held files and the files' layout)

    emissions_driven_files
        The files to calculate from emissions

    emissions
        Global emissions, indexed by MAGICC's name for each gas,
        including all the drivers of `emissions_driven_files`,
        years ([MAGICC_START_YEAR][(m).] to `last_year`) as columns

    first_year
        First year of the experiment

    last_year
        Last year of the run

    anchor_years
        Years which hold the installation's values
        in [NORMALISATION_ANCHOR_YEAR][(m).]

    Returns
    -------
    files :
        File name to contents

    settings :
        Settings which point MAGICC at the files
    """
    defaults = read_namelist(installation.run_dir / "MAGCFG_DEFAULTALL.CFG")[
        "nml_allcfgs"
    ]
    years = range(MAGICC_START_YEAR, last_year + 1)
    to_write: dict[str, tuple[pd.DataFrame | None, str]] = {
        setting: (
            None,
            f"held at {first_year}, "
            f"{NORMALISATION_ANCHOR_YEAR} values in {list(anchor_years)}",
        )
        for setting in HELD_HISTORY_FILES
    }
    for edf in emissions_driven_files:
        to_write[edf.setting] = (
            edf.values(emissions.loc[:, list(years)]),
            f"calculated from {'+'.join(edf.drivers)} emissions, "
            f"{NORMALISATION_ANCHOR_YEAR} values in {list(anchor_years)}",
        )

    files = {}
    settings = {}
    for setting, (values, description) in to_write.items():
        data, specifications = read_tabular_file(
            installation.run_dir / defaults[setting]
        )
        if values is None:
            if first_year not in data.columns:
                msg = f"{defaults[setting]} has no value for {first_year}"
                raise ValueError(msg)

            values_df = pd.DataFrame({y: data[first_year] for y in years})
        else:
            values_df = values.copy()

        for year in anchor_years:
            values_df[year] = data[NORMALISATION_ANCHOR_YEAR].to_numpy()

        name = f"OPENSCM_RUNNER_{setting.upper().removeprefix('FILE_')}.IN"
        files[name] = format_tabular_file(
            values_df,
            # The file's shape changes, so we don't copy the specifications
            # that describe it (`format_tabular_file` writes them)
            specifications={
                k: v
                for k, v in specifications.items()
                if k
                not in {
                    "THISFILE_DATACOLUMNS",
                    "THISFILE_DATAROWS",
                    "THISFILE_FIRSTYEAR",
                    "THISFILE_LASTYEAR",
                    "THISFILE_ANNUALSTEPS",
                    "THISFILE_FIRSTDATAROW",
                }
            },
            header=f"{FILE_HEADER} (layout of {defaults[setting]}, {description})",
            label_rows={"YEARS": [str(v) for v in data.index]},
        )
        settings[setting] = name

    return files, settings


def make_natural_forcing_files(
    natural_forcing: Mapping[str, pd.Series[float]],
    *,
    first_year: int,
    last_year: int,
) -> tuple[dict[str, str], dict[str, Any]]:
    """
    Make the solar and volcanic forcing files

    Parameters
    ----------
    natural_forcing
        MAGICC's name (`"SOLAR"`, `"VOLCANIC"`) to forcing,
        starting in `first_year`. Missing forcings are zero.

    first_year
        First year of the experiment (forcing is zero before this,
        i.e. the piControl natural forcing is zero,
        a choice which is still to be confirmed, see decision [B19][b19])

    last_year
        Last year to write (including any buffer)

    Returns
    -------
    files :
        File name to contents

    settings :
        Settings which point MAGICC at the files
    """
    years = range(first_year, last_year + 1)
    before = pd.Series(0.0, index=range(MAGICC_START_YEAR, first_year))

    def full(values: pd.Series[float] | None) -> pd.Series[float]:
        if values is None:
            return pd.concat([before, pd.Series(0.0, index=years)])

        return pd.concat([before, values.reindex(years).ffill()])

    files = {
        SOLAR_FILE: format_forcing_in("SOLAR_RF", full(natural_forcing.get("SOLAR"))),
        # Annual values, repeated for every month (see the module docstring)
        VOLCANIC_FILE: format_hemispheric_monthly_forcing_in(
            "VOLCANIC_ANNUAL_RF", full(natural_forcing.get("VOLCANIC"))
        ),
    }
    settings = {"file_solar_rf": SOLAR_FILE, "file_volcanic_rf": VOLCANIC_FILE}

    return files, settings


PI_CONTROL_EMISSIONS_GASES: tuple[str, ...] = (
    "CO2I",
    "CO2B",
    "CH4",
    "N2O",
    *AEROSOL_GASES,
    *FGAS_NAMES,
    *MHALO_NAMES,
)
"""Gases we need piControl emissions for (MAGICC's names, as totals except CO2)"""


def get_pi_control_emissions(pre_industrial: PreIndustrialValues) -> dict[str, float]:
    """
    Get the piControl emissions

    These are hard-coded (they don't come from the input),
    so an input which isn't at piControl in its first year
    causes a response in its first year.

    Parameters
    ----------
    pre_industrial
        Pre-industrial values (sets which CMIP era)

    Returns
    -------
    :
        piControl emissions of each gas in [PI_CONTROL_EMISSIONS_GASES][(m).]
        (MAGICC's units): the CMIP era's historical emissions in 1850
        (`pre_industrial.historical_emissions_1850`),
        except CO2, which is zero (no fossil emissions and no land-use change,
        a choice which is still to be confirmed, see decision [B19][b19]),
        and gases without historical emissions (zero)
    """
    spec_by_gas = {spec.gas: spec for spec in EMISSIONS_VARIABLES.values()}
    given = {
        gas: value_unit
        for gas, value_unit in pre_industrial.historical_emissions_1850.items()
        if gas not in ("CO2I", "CO2B")
    }
    out = dict.fromkeys(PI_CONTROL_EMISSIONS_GASES, 0.0)
    if not given:
        return out

    # The units of `historical_emissions_1850` are MAGICC's,
    # but not necessarily written the same way, so convert to be sure
    values = pd.DataFrame(
        [[value] for value, _ in given.values()],
        index=pd.MultiIndex.from_tuples(
            [(gas, unit) for gas, (_, unit) in given.items()],
            names=["variable", "unit"],
        ),
    )
    converted = convert_units(
        values,
        [spec_by_gas[gas].unit for gas in given],
        callable_name="get_pi_control_emissions",
        contexts=EMISSIONS_UNIT_CONVERSION_CONTEXTS,
    )
    for converted_gas, value in zip(
        converted.index.get_level_values("variable"), converted.iloc[:, 0], strict=True
    ):
        out[str(converted_gas)] = float(value)

    return out


def make_scenario_emissions(
    pre_industrial_emissions: pd.Series[float],
    pi_control_emissions: Mapping[str, float],
    input_emissions: pd.DataFrame | None,
    *,
    first_year: int,
    last_year: int,
) -> pd.DataFrame:
    """
    Make the emissions for the `.SCEN7` file

    The piControl emissions (before `first_year`) are `pi_control_emissions`
    (see [get_pi_control_emissions][(m).]),
    with CH4 all as biomass burning (MAGICC's `B` sector).
    MAGICC adds the oxidation of fossil (`I`) CH4 to fossil CO2,
    so fossil CH4 in piControl would be a constant source of CO2
    (and CO2 would drift in emission-driven runs).

    Gases in `input_emissions` replace these from `first_year`
    (so if the input isn't at piControl in `first_year`,
    there is a response in `first_year`),
    the other gases stay at their piControl emissions.
    Totals are split into fossil/industrial and biomass burning
    (MAGICC's `I` and `B`) using the split of `pre_industrial_emissions`
    (MAGICC's own historical emissions in 1850),
    except CH4, where only the change from piControl is split this way
    (so there is no fossil CH4 in piControl, see above).

    Parameters
    ----------
    pre_industrial_emissions
        MAGICC's own pre-industrial emissions of each gas in [SCEN7_GASES][(m).]
        (only used to split totals into sectors)

    pi_control_emissions
        piControl emissions of each gas in [PI_CONTROL_EMISSIONS_GASES][(m).]

    input_emissions
        Emissions from the input (MAGICC's names and units),
        starting in `first_year`.
        CO2 is given as `CO2I` and `CO2B`, other species as totals.
        If `None`, all emissions are held at their piControl values.

    first_year
        First year of the experiment

    last_year
        Last year of the run

    Returns
    -------
    :
        Emissions of each gas in [SCEN7_GASES][(m).] (in [SCEN7_UNITS][(m).]),
        years from [MAGICC_START_YEAR][(m).] to `last_year` as columns
    """

    def industrial_share(gas: str) -> float:
        industrial = pre_industrial_emissions[f"{gas}I"]
        biomass = pre_industrial_emissions[f"{gas}B"]

        return float(industrial / (industrial + biomass))

    pi_control = pd.Series(0.0, index=list(SCEN7_GASES))
    for gas in ("CO2I", "CO2B", *FGAS_NAMES, *MHALO_NAMES):
        pi_control[gas] = pi_control_emissions[gas]

    for gas in ("N2O", *AEROSOL_GASES):
        pi_control[f"{gas}I"] = pi_control_emissions[gas] * industrial_share(gas)
        pi_control[f"{gas}B"] = pi_control_emissions[gas] * (1 - industrial_share(gas))

    pi_control["CH4I"] = 0.0
    pi_control["CH4B"] = pi_control_emissions["CH4"]

    years = range(MAGICC_START_YEAR, last_year + 1)
    emissions = pd.DataFrame({y: pi_control for y in years})
    if input_emissions is None:
        return emissions

    spin_up_years = range(MAGICC_START_YEAR, first_year)
    for input_gas, values in input_emissions.iterrows():
        gas = str(input_gas)
        given = values.reindex(range(first_year, last_year + 1)).ffill()
        spin_up_value = pi_control_emissions[gas]
        full = pd.concat([pd.Series(spin_up_value, index=spin_up_years), given])

        if gas in ("CO2I", "CO2B", *FGAS_NAMES, *MHALO_NAMES):
            emissions.loc[gas] = full
            continue

        share = industrial_share(gas)
        if gas == "CH4":
            emissions.loc["CH4I"] = share * (full - spin_up_value)
            emissions.loc["CH4B"] = full - emissions.loc["CH4I"]
        else:
            emissions.loc[f"{gas}I"] = full * share
            emissions.loc[f"{gas}B"] = full * (1 - share)

    return emissions


def anchor_scenario_emissions(
    emissions: pd.DataFrame,
    historical_emissions: pd.DataFrame,
    *,
    anchor_years: Sequence[int],
) -> pd.DataFrame:
    """
    Put the historical aerosol emissions in the normalisation anchor years

    See the module docstring.

    Parameters
    ----------
    emissions
        Emissions (see [make_scenario_emissions][(m).])

    historical_emissions
        The installation's historical emissions
        (see [load_historical_emissions][(m).])

    anchor_years
        Years in which to put the emissions
        in [NORMALISATION_ANCHOR_YEAR][(m).]

    Returns
    -------
    :
        `emissions`, with the aerosol and aerosol/ozone precursor emissions
        in `anchor_years` set to their historical values
        in [NORMALISATION_ANCHOR_YEAR][(m).]
    """
    out = emissions.copy()
    gases = [f"{gas}{sector}" for gas in AEROSOL_GASES for sector in ("I", "B")]
    for year in anchor_years:
        out.loc[gases, year] = historical_emissions.loc[
            gases, NORMALISATION_ANCHOR_YEAR
        ]

    return out


# TODO: put in io?
def format_scenario_file(emissions: pd.DataFrame) -> str:
    """
    Format the `.SCEN7` file

    Parameters
    ----------
    emissions
        Emissions (see [make_scenario_emissions][(m).])

    Returns
    -------
    :
        Contents of the file
    """
    out = emissions.copy()
    out.index = pd.MultiIndex.from_tuples(
        [(gas, SCEN7_UNITS[gas]) for gas in out.index],
        names=["variable", "unit"],
    )

    return format_scen7(out)


GAS_GROUPS: dict[str, tuple[str, ...]] = {
    "co2": ("CO2I", "CO2B"),
    "ch4": ("CH4",),
    "n2o": ("N2O",),
    "fgas": FGAS_NAMES,
    "mhalo": MHALO_NAMES,
}
"""
MAGICC's gas groups (which switch from concentrations to emissions together)

With the gases (MAGICC's names) in each group.
"""


def get_emissions_driven_groups(input_emissions: pd.DataFrame | None) -> set[str]:
    """
    Get the gas groups which are emissions-driven

    A group is emissions-driven if any of its gases' emissions are in the input.
    Gases in an emissions-driven group without emissions in the input
    are held at their piControl emissions.

    Parameters
    ----------
    input_emissions
        Emissions from the input (MAGICC's names)

    Returns
    -------
    :
        Names of the emissions-driven groups (keys of [GAS_GROUPS][(m).])
    """
    if input_emissions is None:
        return set()

    gases = set(input_emissions.index)

    return {group for group, members in GAS_GROUPS.items() if gases & set(members)}


def run_pre_industrial_branch_experiments(  # noqa: PLR0913
    inputs: tuple[pd.DataFrame, ...],
    output_specs: OutputSpecs,
    *,
    configuration: MAGICCAR6AdapterConfiguration,
    pre_industrial: PreIndustrialValues,
    emissions_driven_files: Sequence[EmissionsDrivenFile] | None = None,
    extra_settings: Mapping[str, Any] | None = None,
) -> tuple[OpenSCMRunnerOutput, ...]:
    """
    Run experiments which branch off pre-industrial

    This is the back-end all the adapters in this module share.
    The inputs aren't verified here (that's up to the adapter).

    Parameters
    ----------
    inputs
        Inputs (each one is exactly one experiment).
        Concentrations, plus optionally natural forcing
        and aerosol emissions.

    output_specs
        Outputs to return

    configuration
        Configuration to run with

    pre_industrial
        Pre-industrial values to use (sets which CMIP era the experiments are for)

    emissions_driven_files
        How to calculate the aerosol history files from emissions
        (this is how you prescribe their regional patterns).
        If `None`, the 1850 patterns
        (see [derive_emissions_driven_files][(m).]).

    extra_settings
        Settings applied on top of the ones every experiment gets
        (e.g. [NO_OZONE_DUE_TO_TEMPERATURE][(m).])

    Returns
    -------
    :
        One output per input, in input order
    """
    output_variables = get_output_variables(
        output_specs.output_variables, SUPPORTED_OUTPUT_VARIABLES
    )
    installation = configuration.installation
    # TODO: handle this better
    first_year = 1850
    historical_emissions = load_historical_emissions(installation)
    pre_industrial_emissions = historical_emissions[first_year]
    pi_control_emissions = get_pi_control_emissions(pre_industrial)
    if emissions_driven_files is None:
        emissions_driven_files = derive_emissions_driven_files(installation)

    experiments = []
    for inp in inputs:
        rest, natural_forcing = split_natural_forcing(inp)
        rest, emissions = split_emissions(rest)
        concentrations = (
            to_magicc_concentrations(rest)
            if not rest.empty
            # Everything is emissions-driven
            else pd.DataFrame(columns=inp.columns, index=pd.Index([], name="variable"))
        )
        input_emissions = (
            None
            if emissions.empty
            else to_magicc_emissions(emissions).droplevel("unit")
        )
        emissions_driven = get_emissions_driven_groups(input_emissions)
        last_year = int(inp.columns.max())
        end_year = last_year + END_YEAR_BUFFER
        anchor_years = list(
            range(end_year - NORMALISATION_ANCHOR_N_YEARS + 1, end_year + 1)
        )

        concentration_files, concentration_settings = make_concentration_files(
            concentrations,
            pre_industrial,
            first_year=first_year,
            last_year=end_year,
        )
        scenario_emissions = make_scenario_emissions(
            pre_industrial_emissions,
            pi_control_emissions,
            input_emissions,
            first_year=first_year,
            last_year=end_year,
        )
        # Natural SOx emissions are constant
        driver_emissions = pd.concat(
            [
                scenario_emissions,
                pd.DataFrame(
                    {"SOXN": pre_industrial_emissions["SOXN"]},
                    index=scenario_emissions.columns,
                ).T,
            ]
        )
        history_files, history_settings = make_history_files(
            installation,
            emissions_driven_files,
            emissions=driver_emissions,
            first_year=first_year,
            last_year=end_year,
            anchor_years=anchor_years,
        )
        natural_files, natural_settings = make_natural_forcing_files(
            natural_forcing, first_year=first_year, last_year=end_year
        )
        experiments.append(
            MAGICCAR6Experiment(
                files={
                    **concentration_files,
                    **history_files,
                    **natural_files,
                    SCENARIO_FILE: format_scenario_file(
                        anchor_scenario_emissions(
                            scenario_emissions,
                            historical_emissions,
                            anchor_years=anchor_years,
                        )
                    ),
                },
                settings={
                    **concentration_settings,
                    **history_settings,
                    **natural_settings,
                    # Switch from concentrations to emissions
                    # in the first year for emissions-driven gases,
                    # never for the others
                    **{
                        f"{group}_switchfromconc2emis_year": (
                            first_year if group in emissions_driven else end_year + 1
                        )
                        for group in GAS_GROUPS
                    },
                    # Derive the natural CH4 and N2O emissions from piControl
                    "ch4_lastbudgetyear": first_year - 1,
                    "n2o_lastbudgetyear": first_year - 1,
                    **dict.fromkeys(FEEDBACK_START_YEAR_SETTINGS, MAGICC_START_YEAR),
                    "file_emisscen": SCENARIO_FILE,
                    **NO_EXTRA_SCENARIO_FILES,
                    "rf_initialization_method": "JUMPSTART",
                    "rf_preind_referenceyr": MAGICC_START_YEAR,
                    "rf_total_runmodus": "ALL",
                    "rf_regions_normyear": anchor_years[0],
                    **(extra_settings or {}),
                },
                start_year=MAGICC_START_YEAR,
                end_year=end_year,
                output_first_year=first_year,
                output_last_year=last_year,
                output_variables=output_variables,
                experiment_levels=get_experiment_levels(inp),
            )
        )

    return run_experiments(experiments, configuration=configuration)


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial:
    """
    MAGICC AR6 adapter for CMIP-style concentration-driven runs from CMIP7 pre-industrial

    For the experiment, see
    [AdapterConcentrationDrivenFromCMIP7PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    Uses the AR6 probabilistic distribution,
    with MAGICC's pre-industrial state set to the CMIP7 piControl state
    (see [openscm_runner.adapters.magicc_ar6.pre_industrial][]
    for why this isn't perfect).

    /// warning | Aerosol forcing is an approximation of MAGICC's AR6 setup
    Direct aerosol and BC on snow forcing use the regional pattern
    of MAGICC's history files in 1850
    and the aerosol-cloud forcing's normalisation isn't the same as AR6's
    (it is somewhat stronger).
    ///

    /// warning | Solar and volcanic forcing are scaled by each ensemble member
    The input solar and volcanic ERF isn't applied as-is:
    each member scales it and applies its efficacy (as in AR6).
    Across the ensemble, the median member applies ~75% of the input solar
    and ~70% of the input volcanic ERF (5-95%: roughly 40% to 115%).
    ///

    /// warning | Volcanic forcing is annual
    MAGICC works best with monthly volcanic forcing,
    which the input definition doesn't offer.
    (MAGICC's annual volcanic forcing output is an "end-of-year forcing",
    so with annual input it is (proportional to) the mean of the input
    in that year and the next.)
    ///

    /// warning | Includes MAGICC's ozone forcing due to temperature
    Unlike the CO2-only adapters, which turn it off.
    So at the moment these adapters act like a model with interactive chemistry,
    the CO2-only concentration-driven adapters like a model with prescribed ozone.
    What we want, and if and how MAGICC can do it,
    are still to be worked out
    (see [NO_OZONE_DUE_TO_TEMPERATURE][(m).] and decision [B18][b18]).
    ///

    See the module docstring
    ([openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch][])
    for details of all of these and of how the run is set up.
    """  # noqa: E501

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        concentrations: tuple[CMIP7PreIndustrialBranchConcentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip7_pre_industrial_branch_concentrations(concentrations)

        return run_pre_industrial_branch_experiments(
            concentrations,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP7_PRE_INDUSTRIAL,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial:
    """
    MAGICC AR6 adapter for CMIP-style concentration-driven runs from CMIP6 pre-industrial

    For the experiment, see
    [AdapterConcentrationDrivenFromCMIP6PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    As for [MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial][(m).]
    (including the warnings),
    with MAGICC's pre-industrial state set to the CMIP6 piControl state.
    """  # noqa: E501

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        concentrations: tuple[CMIP6PreIndustrialBranchConcentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip6_pre_industrial_branch_concentrations(concentrations)

        return run_pre_industrial_branch_experiments(
            concentrations,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP6_PRE_INDUSTRIAL,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial:
    """
    MAGICC AR6 adapter for CO2-concentration-driven runs from CMIP7 pre-industrial

    For the experiment, see
    [AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    Same back-end as
    [MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial][(m).],
    with every other gas held at its CMIP7 piControl concentration,
    emissions held at piControl,
    solar and volcanic forcing at zero
    and no ozone forcing due to temperature
    (see [NO_OZONE_DUE_TO_TEMPERATURE][(m).]).
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        co2_concentrations: tuple[CMIP7PreIndustrialBranchCO2Concentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip7_pre_industrial_branch_co2_concentrations(co2_concentrations)

        return run_pre_industrial_branch_experiments(
            co2_concentrations,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP7_PRE_INDUSTRIAL,
            # So the only forcing is CO2 forcing
            extra_settings=NO_OZONE_DUE_TO_TEMPERATURE,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial:
    """
    MAGICC AR6 adapter for CO2-concentration-driven runs from CMIP6 pre-industrial

    For the experiment, see
    [AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    As for [MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial][(m).],
    with CMIP6 pre-industrial values.
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        co2_concentrations: tuple[CMIP6PreIndustrialBranchCO2Concentrations, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip6_pre_industrial_branch_co2_concentrations(co2_concentrations)

        return run_pre_industrial_branch_experiments(
            co2_concentrations,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP6_PRE_INDUSTRIAL,
            # So the only forcing is CO2 forcing
            extra_settings=NO_OZONE_DUE_TO_TEMPERATURE,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial:
    """
    MAGICC AR6 adapter for CO2-emission-driven runs from CMIP7 pre-industrial

    For the experiment, see
    [AdapterCO2EmissionDrivenFromCMIP7PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    No biosphere CO2 emissions (no land-use change),
    every other gas held at its CMIP7 piControl concentration,
    emissions held at piControl,
    solar and volcanic forcing at zero
    and no ozone forcing due to temperature
    (see [NO_OZONE_DUE_TO_TEMPERATURE][(m).]).

    See the module docstring for how emission-driven runs are set up.

    /// warning | The carbon cycle and CH4/N2O feedbacks start at the start of the run
    Not in the calendar years AR6's setup uses,
    so these don't behave exactly as in AR6
    (see the module docstring).
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        co2_emissions: tuple[CMIP7PreIndustrialBranchCO2Emissions, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip7_pre_industrial_branch_co2_emissions(co2_emissions)

        return run_pre_industrial_branch_experiments(
            co2_emissions,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP7_PRE_INDUSTRIAL,
            # So the only forcing is CO2 forcing
            extra_settings=NO_OZONE_DUE_TO_TEMPERATURE,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterESMFromCMIP7PreIndustrial:
    """
    MAGICC AR6 adapter for CMIP esm-style runs from CMIP7 pre-industrial

    For the experiment, see
    [AdapterESMFromCMIP7PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    As for
    [MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial][(m).]
    (including the warnings), apart from the emission-driven CO2.

    See the module docstring for how emission-driven runs are set up.

    /// warning | The carbon cycle and CH4/N2O feedbacks start at the start of the run
    Not in the calendar years AR6's setup uses,
    so these don't behave exactly as in AR6
    (see the module docstring).
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        esm_inputs: tuple[CMIP7PreIndustrialBranchESMInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip7_pre_industrial_branch_esm_inputs(esm_inputs)

        return run_pre_industrial_branch_experiments(
            esm_inputs,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP7_PRE_INDUSTRIAL,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial:
    """
    MAGICC AR6 adapter for CMIP esm-allGHG-style runs from CMIP7 pre-industrial

    For the experiment, see
    [AdapterESMAllGHGFromCMIP7PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    As for
    [MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial][(m).]
    (including the warnings), apart from the emission-driven GHGs.

    See the module docstring for how emission-driven runs are set up.

    /// warning | The carbon cycle and CH4/N2O feedbacks start at the start of the run
    Not in the calendar years AR6's setup uses,
    so these don't behave exactly as in AR6
    (see the module docstring).
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        esm_all_ghg_inputs: tuple[CMIP7PreIndustrialBranchESMAllGHGInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip7_pre_industrial_branch_esm_all_ghg_inputs(esm_all_ghg_inputs)

        return run_pre_industrial_branch_experiments(
            esm_all_ghg_inputs,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP7_PRE_INDUSTRIAL,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial:
    """
    MAGICC AR6 adapter for CO2-emission-driven runs from CMIP6 pre-industrial

    For the experiment, see
    [AdapterCO2EmissionDrivenFromCMIP6PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    No biosphere CO2 emissions (no land-use change),
    every other gas held at its CMIP6 piControl concentration,
    emissions held at piControl,
    solar and volcanic forcing at zero
    and no ozone forcing due to temperature
    (see [NO_OZONE_DUE_TO_TEMPERATURE][(m).]).

    See the module docstring for how emission-driven runs are set up.

    /// warning | The carbon cycle and CH4/N2O feedbacks start at the start of the run
    Not in the calendar years AR6's setup uses,
    so these don't behave exactly as in AR6
    (see the module docstring).
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        co2_emissions: tuple[CMIP6PreIndustrialBranchCO2Emissions, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip6_pre_industrial_branch_co2_emissions(co2_emissions)

        return run_pre_industrial_branch_experiments(
            co2_emissions,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP6_PRE_INDUSTRIAL,
            # So the only forcing is CO2 forcing
            extra_settings=NO_OZONE_DUE_TO_TEMPERATURE,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterESMFromCMIP6PreIndustrial:
    """
    MAGICC AR6 adapter for CMIP esm-style runs from CMIP6 pre-industrial

    For the experiment, see
    [AdapterESMFromCMIP6PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    As for
    [MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial][(m).]
    (including the warnings), apart from the emission-driven CO2.

    See the module docstring for how emission-driven runs are set up.

    /// warning | The carbon cycle and CH4/N2O feedbacks start at the start of the run
    Not in the calendar years AR6's setup uses,
    so these don't behave exactly as in AR6
    (see the module docstring).
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        esm_inputs: tuple[CMIP6PreIndustrialBranchESMInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip6_pre_industrial_branch_esm_inputs(esm_inputs)

        return run_pre_industrial_branch_experiments(
            esm_inputs,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP6_PRE_INDUSTRIAL,
        )


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial:
    """
    MAGICC AR6 adapter for CMIP esm-allGHG-style runs from CMIP6 pre-industrial

    For the experiment, see
    [AdapterESMAllGHGFromCMIP6PreIndustrial][openscm_runner.cmip_pre_industrial_branch.running.].

    As for
    [MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial][(m).]
    (including the warnings), apart from the emission-driven GHGs.

    See the module docstring for how emission-driven runs are set up.

    /// warning | The carbon cycle and CH4/N2O feedbacks start at the start of the run
    Not in the calendar years AR6's setup uses,
    so these don't behave exactly as in AR6
    (see the module docstring).
    ///
    """

    supported_output_variables: ClassVar[frozenset[str]] = frozenset(
        SUPPORTED_OUTPUT_VARIABLES
    )
    """Output variables this adapter can provide"""

    configuration: MAGICCAR6AdapterConfiguration
    """Configuration to run with"""

    def __call__(
        self,
        esm_all_ghg_inputs: tuple[CMIP6PreIndustrialBranchESMAllGHGInput, ...],
        *,
        output_specs: OutputSpecs,
    ) -> tuple[OpenSCMRunnerOutput, ...]:
        """Run the experiments"""
        if self.configuration.run_checks:
            verify_cmip6_pre_industrial_branch_esm_all_ghg_inputs(esm_all_ghg_inputs)

        return run_pre_industrial_branch_experiments(
            esm_all_ghg_inputs,
            output_specs,
            configuration=self.configuration,
            pre_industrial=CMIP6_PRE_INDUSTRIAL,
        )


if TYPE_CHECKING:
    # mypy checks that the adapters satisfy their protocols
    # (see the note in `ar_scenarios`)
    def _check_conc_cmip7(
        adapter: MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
    ) -> AdapterConcentrationDrivenFromCMIP7PreIndustrial:
        return adapter

    def _check_conc_cmip6(
        adapter: MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
    ) -> AdapterConcentrationDrivenFromCMIP6PreIndustrial:
        return adapter

    def _check_co2_conc_cmip7(
        adapter: MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
    ) -> AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial:
        return adapter

    def _check_co2_conc_cmip6(
        adapter: MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
    ) -> AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial:
        return adapter

    def _check_co2emissiondriven_cmip7(
        adapter: MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
    ) -> AdapterCO2EmissionDrivenFromCMIP7PreIndustrial:
        return adapter

    def _check_esm_cmip7(
        adapter: MAGICCAR6AdapterESMFromCMIP7PreIndustrial,
    ) -> AdapterESMFromCMIP7PreIndustrial:
        return adapter

    def _check_esmallghg_cmip7(
        adapter: MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial,
    ) -> AdapterESMAllGHGFromCMIP7PreIndustrial:
        return adapter

    def _check_co2emissiondriven_cmip6(
        adapter: MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
    ) -> AdapterCO2EmissionDrivenFromCMIP6PreIndustrial:
        return adapter

    def _check_esm_cmip6(
        adapter: MAGICCAR6AdapterESMFromCMIP6PreIndustrial,
    ) -> AdapterESMFromCMIP6PreIndustrial:
        return adapter

    def _check_esmallghg_cmip6(
        adapter: MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial,
    ) -> AdapterESMAllGHGFromCMIP6PreIndustrial:
        return adapter
