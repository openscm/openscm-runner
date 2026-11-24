"""
Pre-industrial (piControl) values for the CMIP pre-industrial branch adapters

The adapters run MAGICC with its pre-industrial state set to the piControl state
(see [openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch][]).
For concentrations, MAGICC (v7.5.3) reads its pre-industrial reference values
from the concentration input files in its pre-industrial reference year
(`RF_PREIND_REFERENCEYR`), which the adapters set to the year before 1850.
So the piControl concentrations here are both
the state the experiments branch from and MAGICC's reference concentrations
(v7.5.3 only lets you state a reference concentration directly for CO2,
`CO2_PREINDCO2CONC`, so we don't).

The piControl concentrations are also used to fill in
the species a CO2-only input doesn't provide.

/// warning | This isn't perfect, it is something we need to fix
- The AR6 probabilistic distribution was calibrated with the CMIP6 history
  and MAGICC's references at their 1750 values
  (CMIP6: CO2 277.147 ppm, CH4 731.406 ppb, N2O 273.865 ppb;
  for CMIP7 they would be CO2 278.00745 ppm, CH4 720.8548 ppb, N2O 266.57 ppb).
  Here the references are the piControl (1850) values instead.
  That isn't a recalibration (no parameters change),
  but the GHG forcing formulae aren't logarithms of ratios alone
  (e.g. the CO2-N2O overlap terms), so the forcing for a given change
  in concentrations differs slightly from what the AR6 setup would give.
- Neither setup is calibrated to CMIP7:
  the CMIP7 adapters are the AR6 calibration
  starting from the CMIP7 piControl state.
- Halon1202 isn't in the CMIP concentration datasets.
  We use zero (the ERF is of order 1e-6 W/m^2 anyway).
- The numbers are hard-coded here
  (retrieved with `scripts/get-rcmip3-pre-industrial-values.py`).
- What values to use as pre-industrial is still to be decided
  (decision B19): CMIP's guidance usually says to repeat the 1850 values,
  RCMIP phase 3's protocol doesn't always (e.g. for CO2 emissions).
///

Sources: the RCMIP phase 3 protocol
(https://gitlab.com/rcmip/rcmip-phase-3, tag v3.0.1),
retrieved with `scripts/get-rcmip3-pre-industrial-values.py`:
TODO: update to use https://zenodo.org/records/23347317

- piControl concentrations: CMIP7 from the `piControl` experiment,
  CMIP6 from the `historical-cmip6` experiment in 1850
  (RCMIP phase 3 has no CMIP6 piControl concentrations)
- historical emissions in 1850: the `historical-cmip6` (CMIP6)
  and `historical` (CMIP7) experiments
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from .naming import FGAS_NAMES, MHALO_NAMES

ALL_CONCENTRATION_GASES: tuple[str, ...] = (
    "CO2",
    "CH4",
    "N2O",
    *FGAS_NAMES,
    *MHALO_NAMES,
)
"""Every gas MAGICC v7.5.3 can be concentration-driven with (MAGICC's names)"""


def _complete(non_zero: dict[str, float]) -> MappingProxyType[str, float]:
    unknown = set(non_zero) - set(ALL_CONCENTRATION_GASES)
    if unknown:
        raise AssertionError(unknown)

    return MappingProxyType({g: non_zero.get(g, 0.0) for g in ALL_CONCENTRATION_GASES})


@dataclass(frozen=True)
class PreIndustrialValues:
    """Pre-industrial values for one CMIP era (all in MAGICC's names and units)"""

    name: str
    """Name of the CMIP era"""

    pi_control_concentrations: MappingProxyType[str, float] = field(repr=False)
    """
    piControl (1850) concentrations

    These are also MAGICC's pre-industrial reference concentrations.
    """

    historical_emissions_1850: MappingProxyType[str, tuple[float, str]] = field(
        repr=False
    )
    """
    Emissions in 1850 in this CMIP era's historical experiment

    `(value, unit)`, the units are MAGICC's
    and can be parsed by openscm-units (e.g. to convert to other units).
    Species which aren't listed are zero.
    The adapters use these as their piControl emissions,
    except for CO2, which is zero
    (see `get_pi_control_emissions` in
    [openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch][]
    and decision B19).
    """


CMIP6_PRE_INDUSTRIAL = PreIndustrialValues(
    name="CMIP6",
    pi_control_concentrations=_complete(
        {
            "CO2": 284.3169987996419,
            "CH4": 808.2490285237631,
            "N2O": 273.0210469563802,
            "CF4": 34.04999923706055,
            "C2F6": 1.2887821417469545e-06,
            "HFC32": 0.0002183888949123,
            "HFC227EA": 3.952903853132739e-06,
            "SO2F2": 2.100204331630569e-05,
            "CCL4": 0.0250004289361337,
            "CH3CL": 457.00000254313153,
            "CH2CL2": 6.912761330604553,
            "CHCL3": 5.99999996026357,
            "CH3BR": 5.299997806549072,
            "HALON1211": 0.0044465725465367,
        }
    ),
    historical_emissions_1850=MappingProxyType(
        {
            "CO2I": (0.051353778897682424, "Gt C/yr"),
            "CO2B": (0.5022039312521428, "Gt C/yr"),
            "CH4": (43.142363653343445, "Mt CH4/yr"),
            "N2O": (0.3557483535357818, "Mt N2ON/yr"),
            "BC": (2.5711244787427185, "Mt BC/yr"),
            "OC": (18.22682478664064, "Mt OC/yr"),
            "CO": (411.4628743194825, "Mt CO/yr"),
            "NMVOC": (66.78304875030415, "Mt NMVOC/yr"),
            "SOX": (2.272231887773452, "Mt S/yr"),
            "NOX": (4.095479910026472, "Mt N/yr"),
            "NH3": (7.909310341080795, "Mt N/yr"),
            "CCL4": (0.024856862, "kt CCl4/yr"),
            "CH2CL2": (246.6579, "kt CH2Cl2/yr"),
            "CH3BR": (104.93295, "kt CH3Br/yr"),
            "CH3CL": (4267.6083, "kt CH3Cl/yr"),
            "CHCL3": (300.92479, "kt CHCl3/yr"),
            "HFC227EA": (4.4373643e-06, "kt HFC227ea/yr"),
            "HFC32": (0.00037413425, "kt HFC32/yr"),
            "HALON1211": (0.0077232726, "kt Halon1211/yr"),
            "C2F6": (0.00022473666, "kt C2F6/yr"),
            "CF4": (0.010071225, "kt CF4/yr"),
            "SO2F2": (1.4342164e-05, "kt SO2F2/yr"),
        }
    ),
)
"""
CMIP6 pre-industrial values

The piControl concentrations are RCMIP phase 3's CMIP6 historical concentrations
in 1850 (the same as MAGICC v7.5.3's own files, to ~6 significant figures).
The tiny non-zero 1850 values for some HFCs/PFCs/SO2F2 are in the data
(they make no practical difference).
"""

CMIP7_PRE_INDUSTRIAL = PreIndustrialValues(
    name="CMIP7",
    pi_control_concentrations=_complete(
        {
            "CO2": 284.29727,
            "CH4": 798.79926,
            "N2O": 271.57,
            "CF4": 34.05,
            "CH3CL": 457.0,
            "CH2CL2": 6.9,
            "CHCL3": 6.0,
            "CH3BR": 5.3,
        }
    ),
    historical_emissions_1850=MappingProxyType(
        {
            "CO2I": (0.05211779560611025, "Gt C/yr"),
            "CO2B": (0.720144575, "Gt C/yr"),
            "CH4": (39.21780406063876, "Mt CH4/yr"),
            "N2O": (0.784293240459599, "Mt N2ON/yr"),
            "BC": (2.814269164728321, "Mt BC/yr"),
            "OC": (19.035016751338222, "Mt OC/yr"),
            "CO": (406.2903038989944, "Mt CO/yr"),
            "NMVOC": (67.30101512737843, "Mt NMVOC/yr"),
            "SOX": (2.19738058904595, "Mt S/yr"),
            "NOX": (6.136302854595311, "Mt N/yr"),
            "NH3": (7.54547236103348, "Mt N/yr"),
            "CH2CL2": (215.97319706707253, "kt CH2Cl2/yr"),
            "CH3BR": (111.76597076095555, "kt CH3Br/yr"),
            "CH3CL": (4554.415614763551, "kt CH3Cl/yr"),
            "CHCL3": (261.03253777014686, "kt CHCl3/yr"),
            "CF4": (0.0144533451923196, "kt CF4/yr"),
        }
    ),
)
"""
CMIP7 pre-industrial values

The piControl concentrations are RCMIP phase 3's CMIP7 piControl concentrations.
"""
