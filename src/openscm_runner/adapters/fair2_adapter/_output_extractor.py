"""
Convert FaIR 2.x's xarray outputs into an openscm-runner ScmRun.

Variable name conventions are openscm-runner's (compatible with the
output of the FaIR 1.6 and MAGICC7 adapters where possible). FaIR 2.x
species names are hyphenated where the IAMC / openscm-runner
convention is not (e.g. FaIR "CFC-11" / openscm "CFC11"), so the
output mapping mirrors the inverse of
:data:`._emissions_translator.OPENSCM_TO_FAIR2_SPECIES` plus a few
special cases.

Supported output variables in this version:

- ``Surface Air Temperature Change`` (FaIR's surface layer)
- ``Surface Air Ocean Blended Temperature Change`` (scaled by
  ``GMST_TO_GSAT_SCALE``; documented scientific choice)
- ``Surface Ocean Temperature Change`` (FaIR's ``temperature[layer=1]``)
- ``Effective Radiative Forcing`` (FaIR's ``forcing_sum``)
- ``Effective Radiative Forcing|<species>`` for every FaIR 2.x species
  with a known openscm-runner name (see
  :data:`OUTPUT_LEAF_TO_FAIR2_SPECIES`). RCMIP hierarchical paths
  (``…|Anthropogenic|F-Gases|HFC|HFC125``) resolve to the same species
  data as the flat form (``…|HFC125``) via leaf-segment lookup.
- ``Effective Radiative Forcing|<category>`` aggregations including
  the RCMIP-aligned hierarchy:
  ``Anthropogenic|{CO2, CH4, F-Gases, F-Gases|HFC, F-Gases|PFC,
  Montreal Gases, Montreal Gases|{CFC, HCFC, Halon}, Aerosol,
  Aerosol|{Aerosol-radiation Interactions, Aerosol-cloud Interactions},
  Albedo Change, Other|{Contrails, BC on Snow, CH4 Oxidation
  Stratospheric H2O}}`` and ``Natural|{Solar, Volcanic}``.
- ``Atmospheric Concentrations|<species>`` for every FaIR 2.x species
  with a known openscm-runner name (flat or hierarchical form).
- ``Emissions|<species>`` (forward or back-calculated; FaIR's run loop
  calls ``unstep_concentration`` per timestep for species in
  ``concentration`` input_mode, populating ``f.emissions``).
- ``Cumulative Emissions|<species>`` (from ``cumulative_emissions``).
- ``Airborne Emissions|<species>`` (from ``airborne_emissions``).
- ``Net Flux to Atmosphere|<species>`` (year-over-year diff of
  cumulative emissions; equals the per-year emission rate).
- ``Atmospheric Lifetime|<species>`` (``alpha_lifetime`` * baseline
  from species_configs; in years).
- ``Heat Content``, ``Heat Content|Ocean`` (FaIR's
  ``ocean_heat_content_change``, converted J -> ZJ)
- ``Heat Uptake``, ``Heat Uptake|Ocean`` (FaIR's ``toa_imbalance``
  converted W/m^2 -> ZJ/yr via Earth surface area * seconds/yr)
- ``Net Energy Imbalance`` (native W/m^2 from ``toa_imbalance``)
- ``Airborne Fraction`` (FaIR's ``airborne_fraction`` summed over
  CO2 FFI + CO2 AFOLU)

**Variables NOT supported (FaIR 2.x structural limits)**:

These are RCMIP variables that no amount of extractor work will
expose, because FaIR 2.x's model design does not produce them:

- ``Sea Level Change`` and all sub-entries (6 variables): FaIR has
  no sea-level module.
- ``Carbon Pool|{Land, Ocean}|{Vegetation, Litter, Soil, Wood,
  Surface, Deep, Inorganic, Organic, ...}`` and the corresponding
  ``Carbon Flux`` sub-entries (~30 variables): FaIR's carbon cycle
  is a Joos-style impulse-response with no compartmental pools
  (no land/ocean partitioning of CO2 uptake, no biosphere
  compartments).
- ``Natural Fluxes|CH4|{Wetland, Permafrost, Soil Sink,
  Stratosphere, Troposphere, ...}`` and source decompositions
  (``Emissions|CH4|{Biomass Burning, Fossil, AFOLU, Other}``):
  FaIR models CH4 as a single species with a lumped lifetime; no
  source-side or sink-side breakdown.
- ``Heat Uptake|{Atmosphere, Land, Ice, Other}`` (4 variables):
  FaIR's energy balance puts all heat into the ocean; no
  separate non-ocean heat uptake.
- ``Heat Content|Ocean|{0-700m, 700-2000m, below-2000m}``
  (3 variables): FaIR's 2-layer ocean (mixed + deep box) has no
  depth resolution within those boxes.
- ``Effective Radiative Forcing|...|Aerosol-radiation
  Interactions|{Biomass Burning, Fossil and Industrial}|{BC, NH3,
  Nitrate, OC, Sulfate}`` and similar 3-way splits (~15 variables):
  FaIR's aerosol forcing is per emission species, not partitioned
  by emission source sector.
- ``Natural Fluxes|N2O`` and ``Natural Fluxes|N2O|*`` (~3 variables):
  N2O modelled as a single species; no separate natural source
  partitioning.
- ``Effective Radiative Forcing|Anthropogenic|{Stratospheric,
  Tropospheric} Ozone`` and tropospheric ozone precursor splits:
  FaIR has a lumped ``Ozone`` species (exposed) but not the
  strat/trop split nor the precursor-attributed decomposition.
- ``Carbon Sequestration`` (CCS): no explicit CCS module; CCS
  fluxes appear only as a negative on the input emissions.
- ``Ocean pH``: FaIR has no carbonate chemistry.

Bottom line: ~180 of the protocol's 275 variables are reachable
from FaIR 2.x's natural outputs; the remaining ~95 are structurally
unsupported. Unrecognised variables are logged at DEBUG and silently
skipped (the same forgiving pattern the FaIR 1.6 adapter follows).
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scmdata import ScmRun

from ._emissions_translator import OPENSCM_TO_FAIR2_SPECIES

LOGGER = logging.getLogger(__name__)


# Scientific choice: factor used to convert surface temperature change
# (layer-0 of FaIR's temperature array, a model-internal "GSAT" proxy)
# to the GMST-blended convention reported in many observed datasets.
# 1/1.04 mirrors the value the FaIR 1.6 adapter has used (Cowtan et
# al. 2015 scaling, used in AR6 WGI Table 7.SM.1).
GMST_TO_GSAT_SCALE = 1.0 / 1.04

# Joules to zettajoules (10^21 J). FaIR 2.x exposes
# ocean_heat_content_change in J; openscm-runner uses ZJ.
J_TO_ZJ = 1e-21

# Earth surface area (m^2) and seconds in a year, for converting
# `toa_imbalance` (W/m^2) to Heat Uptake (ZJ/yr).
_EARTH_SURFACE_AREA = 5.101e14
_SECONDS_PER_YEAR = 365.25 * 24 * 3600
# W/m^2 -> ZJ/yr scaling factor: W * (m^2) * (s/yr) / (J/ZJ)
_TOA_W_PER_M2_TO_ZJ_PER_YR = _EARTH_SURFACE_AREA * _SECONDS_PER_YEAR * J_TO_ZJ


# Output leaf names (the part after "Atmospheric Concentrations|" or
# "Effective Radiative Forcing|") -> FaIR 2.x species names.
#
# Derived from OPENSCM_TO_FAIR2_SPECIES by stripping the leading "|"
# and skipping the CO2 FFI/AFOLU split (output uses the calculated
# total "CO2"). Aliases collapse to one entry.
_BASE_OUTPUT_LEAVES = {
    suffix.lstrip("|"): fair_name
    for suffix, fair_name in OPENSCM_TO_FAIR2_SPECIES.items()
    if not suffix.startswith("|CO2|")
}
OUTPUT_LEAF_TO_FAIR2_SPECIES: dict[str, str] = {
    **_BASE_OUTPUT_LEAVES,
    # Output side uses the calculated total CO2, not the FFI/AFOLU split
    "CO2": "CO2",
}


# Per-species concentration units (FaIR 2.x's internal units, used as
# the output unit string). ppm for CO2, ppb for CH4 and N2O, ppt for
# everything else.
_CONCENTRATION_UNITS = {"CO2": "ppm", "CH4": "ppb", "N2O": "ppb"}


def _concentration_unit(species_name: str) -> str:
    return _CONCENTRATION_UNITS.get(species_name, "ppt")


# Forcing-aggregation recipes. Keyed by the openscm-runner output
# variable name; value is a callable that takes (forcing_da,
# properties_df, available_species) and returns a 1-D numpy array
# along the time axis (or None if the recipe can't be computed against
# the species set FaIR actually ran).
def _forcing_to_numpy(forcing_da):
    """
    Materialise FaIR's forcing DataArray as a plain numpy array once.

    Returns ``(forcing_np, species_index)`` where ``forcing_np`` has axis
    order ``(timebounds, scenario, config, specie)`` and ``species_index``
    maps species name -> position on the last axis. Extracting/aggregating
    per (scenario, member) against this numpy array with integer indexing
    is orders of magnitude faster than repeated xarray ``.sel().isel()``
    orthogonal indexing (the dominant cost for large ensembles), and is
    numerically identical (same species order, same summation order).
    """
    da = forcing_da.transpose("timebounds", "scenario", "config", "specie")
    species = list(da["specie"].values)
    return np.asarray(da.values), {name: i for i, name in enumerate(species)}


def _sum_forcing_over(
    forcing_np,
    species_index: "dict[str, int]",
    sc_idx: int,
    member_offset: int,
    species_to_sum: list[str],
) -> np.ndarray:
    """Sum the forcing array over a list of species names (numpy path)."""
    idx = [species_index[s] for s in species_to_sum if s in species_index]
    if not idx:
        return None
    return forcing_np[:, sc_idx, member_offset, idx].sum(axis=-1)


def _species_by_property(properties_df, predicate) -> list[str]:
    """Return the species names where ``predicate(row)`` is truthy."""
    return [
        name for name, row in properties_df.iterrows() if predicate(row)
    ]


def _build_forcing_aggregations(  # noqa: PLR0912, PLR0915
    forcing_np, species_index, species_in_run, sc_idx: int,
    member_offset: int, properties_df,
) -> "dict[str, tuple[np.ndarray, str]]":
    """
    Build the value arrays for the supported forcing aggregations.

    Returns a dict keyed by openscm-runner variable name; values are
    ``(values, unit)`` tuples. Aggregations whose species list does
    not intersect FaIR's actual species are omitted, not zero-filled.
    Operates on the pre-materialised numpy forcing array (see
    :func:`_forcing_to_numpy`) for speed.
    """
    def sum_over(species_list: list[str]) -> np.ndarray:
        return _sum_forcing_over(
            forcing_np, species_index, sc_idx, member_offset, species_list
        )

    ghgs = _species_by_property(
        properties_df, lambda r: bool(r.get("greenhouse_gas", False))
    )
    f_gases = _species_by_property(
        properties_df, lambda r: r.get("type") == "f-gas"
    )
    montreal = _species_by_property(
        properties_df,
        lambda r: r.get("type") in ("cfc-11", "other halogen"),
    )

    # Kyoto basket = CO2 + CH4 + N2O + F-gases (the basket the Kyoto
    # Protocol covers; CFCs are governed by the Montreal Protocol).
    kyoto = [s for s in ("CO2", "CH4", "N2O") if s in species_in_run] + f_gases

    aero_indirect = [
        s
        for s in ("Aerosol-cloud interactions",)
        if s in species_in_run
    ]
    aero_direct = [
        s
        for s in ("Aerosol-radiation interactions",)
        if s in species_in_run
    ]

    out: dict[str, tuple[np.ndarray, str]] = {}
    forcing_unit = "W/m^2"

    def maybe(name: str, values):
        if values is None:
            return
        out[name] = (values, forcing_unit)

    # Anthropogenic = total forcing minus Solar minus Volcanic
    total = forcing_np[:, sc_idx, member_offset, :].sum(axis=-1)
    natural_species = [s for s in ("Solar", "Volcanic") if s in species_in_run]
    if natural_species:
        natural = sum_over(natural_species)
        anthro = total - natural if natural is not None else None
        maybe("Effective Radiative Forcing|Anthropogenic", anthro)
    else:
        maybe("Effective Radiative Forcing|Anthropogenic", total)

    maybe("Effective Radiative Forcing|Greenhouse Gases", sum_over(ghgs))
    maybe("Effective Radiative Forcing|F-Gases", sum_over(f_gases))
    maybe("Effective Radiative Forcing|Kyoto Gases", sum_over(kyoto))
    maybe(
        "Effective Radiative Forcing|CO2, CH4 and N2O",
        sum_over([s for s in ("CO2", "CH4", "N2O") if s in species_in_run]),
    )
    maybe(
        "Effective Radiative Forcing|Montreal Protocol Halogen Gases",
        sum_over(montreal),
    )
    maybe(
        "Effective Radiative Forcing|Aerosols",
        sum_over(aero_direct + aero_indirect),
    )
    maybe(
        "Effective Radiative Forcing|Aerosols|Direct Effect", sum_over(aero_direct)
    )
    maybe(
        "Effective Radiative Forcing|Aerosols|Indirect Effect",
        sum_over(aero_indirect),
    )

    # Single-species pass-throughs that the FaIR 1.6 adapter exposes
    # under openscm-runner names that differ from the FaIR 2.x species
    # name. Map: openscm-runner name -> FaIR 2.x specie label.
    single_specie_aliases = {
        "Effective Radiative Forcing|Ozone": "Ozone",
        "Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O": (
            "Stratospheric water vapour"
        ),
        "Effective Radiative Forcing|Contrails": "Contrails",
        "Effective Radiative Forcing|Land-use Change": "Land use",
        "Effective Radiative Forcing|Black Carbon on Snow": (
            "Light absorbing particles on snow and ice"
        ),
        "Effective Radiative Forcing|Volcanic": "Volcanic",
        "Effective Radiative Forcing|Solar": "Solar",
    }
    for openscm_name, fair_specie in single_specie_aliases.items():
        if fair_specie not in species_index:
            continue
        values = forcing_np[:, sc_idx, member_offset, species_index[fair_specie]]
        maybe(openscm_name, values)

    # RCMIP-aligned hierarchical aggregations. Most are aliases for
    # entries we've already built above; a few (HFC, PFC, CFC, HCFC
    # sub-totals) are new sub-sums grouped by chemistry.
    hfcs = [s for s in species_in_run if s.startswith("HFC-")]
    pfcs = [s for s in species_in_run if s in (
        "CF4", "C2F6", "C3F8", "C4F10", "C5F12",
        "C6F14", "C7F16", "C8F18", "c-C4F8",
    )]
    cfcs = [
        s for s in species_in_run
        if s.startswith("CFC-") or s in (
            "CCl4", "CH3CCl3", "CH3Br", "CH3Cl",
        )
    ]
    hcfcs = [s for s in species_in_run if s.startswith("HCFC-")]
    halons = [s for s in species_in_run if s.startswith("Halon-")]

    erf = "Effective Radiative Forcing"
    aero_radiation = (
        f"{erf}|Anthropogenic|Aerosol|Aerosol-radiation Interactions"
    )
    aero_cloud = (
        f"{erf}|Anthropogenic|Aerosol|Aerosol-cloud Interactions"
    )
    strath2o = (
        f"{erf}|Anthropogenic|Other|CH4 Oxidation Stratospheric H2O"
    )
    rcmip_aggregations = {
        # Anthropogenic subcategory aliases for existing aggregations.
        f"{erf}|Anthropogenic|F-Gases":
            out.get(f"{erf}|F-Gases"),
        f"{erf}|Anthropogenic|Aerosol":
            out.get(f"{erf}|Aerosols"),
        aero_radiation:
            out.get(f"{erf}|Aerosols|Direct Effect"),
        aero_cloud:
            out.get(f"{erf}|Aerosols|Indirect Effect"),
        f"{erf}|Anthropogenic|Montreal Gases":
            out.get(f"{erf}|Montreal Protocol Halogen Gases"),
        f"{erf}|Natural|Solar":
            out.get(f"{erf}|Solar"),
        f"{erf}|Natural|Volcanic":
            out.get(f"{erf}|Volcanic"),
        f"{erf}|Anthropogenic|Albedo Change|Land use":
            out.get(f"{erf}|Land-use Change"),
        f"{erf}|Anthropogenic|Albedo Change":
            out.get(f"{erf}|Land-use Change"),
        strath2o:
            out.get(f"{erf}|CH4 Oxidation Stratospheric H2O"),
        f"{erf}|Anthropogenic|Other|Contrails":
            out.get(f"{erf}|Contrails"),
        f"{erf}|Anthropogenic|Other|BC on Snow":
            out.get(f"{erf}|Black Carbon on Snow"),
    }
    for name, value in rcmip_aggregations.items():
        if value is not None:
            out[name] = value

    # New sub-totals grouped by chemistry family.
    if hfcs:
        maybe(f"{erf}|Anthropogenic|F-Gases|HFC", sum_over(hfcs))
    if pfcs:
        maybe(f"{erf}|Anthropogenic|F-Gases|PFC", sum_over(pfcs))
    if cfcs:
        maybe(f"{erf}|Anthropogenic|Montreal Gases|CFC", sum_over(cfcs))
    if hcfcs:
        maybe(f"{erf}|Anthropogenic|Montreal Gases|HCFC", sum_over(hcfcs))
    if halons:
        maybe(f"{erf}|Anthropogenic|Montreal Gases|Halon", sum_over(halons))

    # Per-species CO2/CH4/N2O aliases used by RCMIP under the
    # |Anthropogenic| umbrella.
    for spec_leaf, spec in (
        ("CO2", "CO2"), ("CH4", "CH4"), ("N2O", "N2O"),
    ):
        if spec in species_index:
            v = forcing_np[:, sc_idx, member_offset, species_index[spec]]
            maybe(f"Effective Radiative Forcing|Anthropogenic|{spec_leaf}", v)

    return out


def _row(
    rows: list,
    scenario: str,
    variable: str,
    unit: str,
    run_id: int,
    values: np.ndarray,
):
    rows.append((scenario, "", "World", variable, unit, run_id, values))


def extract_outputs(  # noqa: PLR0913, PLR0912, PLR0915
    f,
    scenarios: list[str],
    members: pd.DataFrame,
    output_variables,
    run_id_offset: int,
    properties_df=None,
) -> ScmRun:
    """
    Convert FaIR 2.x's xarray output into an :class:`scmdata.ScmRun`.

    See module docstring for the supported variable set.
    """
    timebounds = np.asarray(f.timebounds, dtype=int)
    rows: list = []

    species_in_run = list(f.forcing["specie"].values)
    # Materialise the forcing array once (dominant cost otherwise is
    # repeated xarray orthogonal indexing per member); aggregate in numpy.
    forcing_np, forcing_species_index = _forcing_to_numpy(f.forcing)

    # Pre-compute aggregations once per (scenario, member) since the
    # recipes share intermediate sums.
    for sc_idx, scenario in enumerate(scenarios):
        for member_offset in range(len(members)):
            run_id = run_id_offset + member_offset

            aggregations = (
                _build_forcing_aggregations(
                    forcing_np, forcing_species_index, species_in_run,
                    sc_idx, member_offset, properties_df,
                )
                if properties_df is not None
                else {}
            )

            for variable in output_variables:
                # Scalars (no species suffix)
                if variable == "Surface Air Temperature Change":
                    values = (
                        f.temperature.isel(
                            scenario=sc_idx, config=member_offset, layer=0
                        )
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(rows, scenario, variable, "K", run_id, values)
                    continue
                if variable == "Surface Air Ocean Blended Temperature Change":
                    values = (
                        f.temperature.isel(
                            scenario=sc_idx, config=member_offset, layer=0
                        )
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(
                        rows,
                        scenario,
                        variable,
                        "K",
                        run_id,
                        values * GMST_TO_GSAT_SCALE,
                    )
                    continue
                if variable == "Effective Radiative Forcing":
                    values = (
                        f.forcing_sum.isel(scenario=sc_idx, config=member_offset)
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(rows, scenario, variable, "W/m^2", run_id, values)
                    continue
                if variable in ("Heat Content", "Heat Content|Ocean"):
                    values = (
                        f.ocean_heat_content_change.isel(
                            scenario=sc_idx, config=member_offset
                        )
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(
                        rows, scenario, variable, "ZJ", run_id, values * J_TO_ZJ
                    )
                    continue
                if variable in ("Heat Uptake", "Heat Uptake|Ocean"):
                    # RCMIP wants ZJ/yr. FaIR's toa_imbalance is the
                    # planetary net flux in W/m^2; convert to global
                    # ZJ/yr via Earth surface area * seconds in a year.
                    # `Heat Uptake|Ocean` approximated by total Heat
                    # Uptake: FaIR's 2-layer ocean is the dominant
                    # heat sink and atmosphere / land / ice splits
                    # aren't modelled separately.
                    values = (
                        f.toa_imbalance.isel(scenario=sc_idx, config=member_offset)
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(
                        rows, scenario, variable, "ZJ/yr", run_id,
                        values * _TOA_W_PER_M2_TO_ZJ_PER_YR,
                    )
                    continue
                if variable == "Net Energy Imbalance":
                    # Same source as Heat Uptake but reported in the
                    # native W/m^2 the underlying quantity has.
                    values = (
                        f.toa_imbalance.isel(scenario=sc_idx, config=member_offset)
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(rows, scenario, variable, "W/m^2", run_id, values)
                    continue
                if variable == "Surface Ocean Temperature Change":
                    # Mid-ocean layer (layer=1) in FaIR 2.x's stochastic
                    # energy-balance model; serves as the deeper-ocean
                    # temperature anomaly. FaIR's layer=0 is the
                    # surface (GSAT proxy), layer=2 is the deepest box.
                    if f.temperature.sizes.get("layer", 0) < 2:
                        continue
                    values = (
                        f.temperature.isel(
                            scenario=sc_idx, config=member_offset, layer=1
                        )
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(rows, scenario, variable, "K", run_id, values)
                    continue
                if variable == "Airborne Fraction":
                    co2_components = [
                        s
                        for s in ("CO2 FFI", "CO2 AFOLU")
                        if s in species_in_run
                    ]
                    if not co2_components:
                        continue
                    values = (
                        f.airborne_fraction.sel(specie=co2_components)
                        .isel(scenario=sc_idx, config=member_offset)
                        .sum(dim="specie")
                        .to_pandas()
                        .reindex(timebounds)
                    )
                    _row(
                        rows,
                        scenario,
                        variable,
                        "dimensionless",
                        run_id,
                        values,
                    )
                    continue

                # Forcing aggregations
                if variable in aggregations:
                    values, unit = aggregations[variable]
                    series = pd.Series(values, index=timebounds)
                    _row(rows, scenario, variable, unit, run_id, series)
                    continue

                # Per-species patterns. RCMIP uses both flat
                # `Emissions|HFC125` and hierarchical
                # `Emissions|F-Gases|HFC|HFC125` forms for the same
                # species, so we always take the LAST `|`-separated
                # segment as the leaf and look it up. Paths whose
                # leaf is not a species (e.g.
                # `Effective Radiative Forcing|Anthropogenic|F-Gases|HFC`,
                # `Atmospheric Concentrations|F-Gases`) fall through
                # to aggregation lookup below.
                # Per-species derived quantities (Carbon Cycle / Methane
                # / N2O lifetimes etc). Cumulative Emissions and Net
                # Flux to Atmosphere derive directly from FaIR's
                # cumulative_emissions / airborne_emissions arrays.
                # Atmospheric Lifetime is alpha_lifetime[specie] (a
                # dimensionless scaling factor times the baseline
                # lifetime stored in species_configs).
                handled = False
                for prefix, extractor in (
                    ("Atmospheric Concentrations|", _atmos_conc),
                    ("Effective Radiative Forcing|", _erf_per_species),
                    ("Emissions|", _emissions_per_species),
                    ("Cumulative Emissions|", _cumulative_emissions_per_species),
                    ("Atmospheric Lifetime|", _atmospheric_lifetime_per_species),
                    ("Net Flux to Atmosphere|", _net_flux_per_species),
                    ("Airborne Emissions|", _airborne_emissions_per_species),
                ):
                    if variable.startswith(prefix):
                        # Use the last segment after `|` as the species
                        # leaf; falls back to the full subpath if the
                        # variable name has no further `|` separator
                        # beyond the prefix (e.g. `Emissions|CO2`).
                        rest = variable[len(prefix) :]
                        leaf = rest.split("|")[-1] if "|" in rest else rest
                        # Special case: `Emissions|CO2|MAGICC Fossil and
                        # Industrial` is two segments where the leaf
                        # alone ("MAGICC Fossil and Industrial") isn't
                        # what _emissions_per_species keys on; preserve
                        # the existing `CO2|MAGICC …` form when the
                        # full rest already matches a known sub-key.
                        if extractor is _emissions_per_species and rest in (
                            "CO2|MAGICC Fossil and Industrial",
                            "CO2|MAGICC AFOLU",
                        ):
                            leaf = rest
                        result = extractor(
                            f, leaf, sc_idx, member_offset
                        )
                        if result is not None:
                            values, unit = result
                            series = pd.Series(values, index=timebounds)
                            _row(rows, scenario, variable, unit, run_id, series)
                            handled = True
                        break

                if not handled:
                    LOGGER.debug(
                        "FaIRv2 adapter does not emit %s; ignored", variable
                    )

    if not rows:
        return ScmRun(pd.DataFrame())
    return _build_scmrun(rows, timebounds)


def _atmos_conc(f, leaf: str, sc_idx: int, member_offset: int):
    species_name = OUTPUT_LEAF_TO_FAIR2_SPECIES.get(leaf)
    if species_name is None or species_name not in f.concentration["specie"].values:
        return None
    values = (
        f.concentration.sel(specie=species_name)
        .isel(scenario=sc_idx, config=member_offset)
        .values
    )
    return values, _concentration_unit(species_name)


def _erf_per_species(f, leaf: str, sc_idx: int, member_offset: int):
    species_name = OUTPUT_LEAF_TO_FAIR2_SPECIES.get(leaf)
    if species_name is None or species_name not in f.forcing["specie"].values:
        return None
    values = (
        f.forcing.sel(specie=species_name)
        .isel(scenario=sc_idx, config=member_offset)
        .values
    )
    return values, "W/m^2"


def _emissions_per_species(  # noqa: PLR0911
    f, leaf: str, sc_idx: int, member_offset: int
):
    """
    Read emissions for a species out of ``f.emissions``.

    Works for both emissions-driven runs (returns the input values
    interpolated onto FaIR's timepoints) and concentration-driven
    runs (returns back-calculated emissions; FaIR's run loop calls
    ``fair.gas_cycle.inverse.unstep_concentration`` per timestep
    for species in ``concentration`` input_mode).

    Special handling: ``Emissions|CO2`` is the TOTAL of FaIR's two
    CO2 emissions species (``CO2 FFI`` + ``CO2 AFOLU``); the
    sub-categorised leaves ``CO2|MAGICC Fossil and Industrial`` and
    ``CO2|MAGICC AFOLU`` map to the individual species.

    FaIR's emissions live on ``timepoints`` (year midpoints; length
    n_years), while the rest of the extractor reports on
    ``timebounds`` (year edges; length n_years + 1). We pad with a
    trailing NaN so the output array fits the timebound grid the
    caller uses for the resulting Series.
    """
    import numpy as np
    from fair.structure.units import desired_emissions_units

    def _read(spec: str):
        if spec not in f.emissions["specie"].values:
            return None
        vals = (
            f.emissions.sel(specie=spec)
            .isel(scenario=sc_idx, config=member_offset)
            .values
        )
        # Pad timepoints (length N) -> timebounds (length N+1) with NaN
        # so the caller's pd.Series(values, index=timebounds) lines up.
        # The final year has no emissions data; rather than fabricate
        # a value we leave it NaN.
        return np.concatenate([vals, [np.nan]])

    # Total CO2 = FFI + AFOLU (RCMIP "Emissions|CO2" convention).
    if leaf == "CO2":
        ffi = _read("CO2 FFI")
        afolu = _read("CO2 AFOLU")
        if ffi is None or afolu is None:
            return None
        unit = desired_emissions_units.get("CO2 FFI", "Gt C/yr")
        return ffi + afolu, unit

    # IAMC sub-categorised CO2 paths -> individual FaIR species.
    if leaf == "CO2|MAGICC Fossil and Industrial":
        values = _read("CO2 FFI")
        unit = desired_emissions_units.get("CO2 FFI", "Gt C/yr")
        return (None if values is None else (values, unit))
    if leaf == "CO2|MAGICC AFOLU":
        values = _read("CO2 AFOLU")
        unit = desired_emissions_units.get("CO2 AFOLU", "Gt C/yr")
        return (None if values is None else (values, unit))

    # Other species: same leaf-to-FaIR map the concentration / ERF
    # extractors use.
    species_name = OUTPUT_LEAF_TO_FAIR2_SPECIES.get(leaf)
    if species_name is None:
        return None
    values = _read(species_name)
    if values is None:
        return None
    unit = desired_emissions_units.get(species_name, "unknown")
    return values, unit


def _cumulative_emissions_per_species(f, leaf, sc_idx, member_offset):
    """Read cumulative emissions for ``leaf``; unit is Gt-equivalent."""
    from fair.structure.units import desired_emissions_units

    def _cum(spec):
        return _read_specie_array(
            f, "cumulative_emissions", spec, sc_idx, member_offset
        )

    if leaf == "CO2":
        ffi = _cum("CO2 FFI")
        afolu = _cum("CO2 AFOLU")
        if ffi is None or afolu is None:
            return None
        unit = desired_emissions_units.get("CO2 FFI", "Gt C/yr").replace("/yr", "")
        return ffi + afolu, unit
    species_name = OUTPUT_LEAF_TO_FAIR2_SPECIES.get(leaf)
    if species_name is None:
        return None
    values = _cum(species_name)
    if values is None:
        return None
    unit = desired_emissions_units.get(species_name, "unknown/yr").replace(
        "/yr", ""
    )
    return values, unit


def _atmospheric_lifetime_per_species(f, leaf, sc_idx, member_offset):
    """
    Effective atmospheric lifetime for a species.

    FaIR stores ``alpha_lifetime`` (dimensionless scaling factor on
    the baseline lifetime) per (timebound, scenario, config, specie).
    Multiplying by the species' baseline ``unperturbed_lifetime``
    from species_configs gives the effective lifetime in years.
    """
    species_name = OUTPUT_LEAF_TO_FAIR2_SPECIES.get(leaf)
    if species_name is None or species_name not in f.alpha_lifetime["specie"].values:
        return None
    alpha = (
        f.alpha_lifetime.sel(specie=species_name)
        .isel(scenario=sc_idx, config=member_offset)
        .values
    )
    # Baseline lifetime is per-config in species_configs (xarray:
    # `unperturbed_lifetime` dims (specie, config, gasbox)). For
    # single-lifetime species (CH4, N2O), gasbox=0 holds the value.
    try:
        baseline = float(
            f.species_configs["unperturbed_lifetime"]
            .sel(specie=species_name)
            .isel(config=member_offset, gasbox=0)
            .values
        )
    except Exception:  # pylint: disable=broad-except
        return None
    return alpha * baseline, "yr"


def _net_flux_per_species(f, leaf, sc_idx, member_offset):
    """
    Net flux to atmosphere (year-over-year cumulative emissions delta).

    For CO2 this is the net source/sink summed over FFI + AFOLU; for
    other GHGs it's the per-species annual flux. Unit matches the
    species' annual emissions unit (kt / Mt / Gt per yr).
    """
    import numpy as np
    from fair.structure.units import desired_emissions_units

    def _flux(spec):
        cum = _read_specie_array(
            f, "cumulative_emissions", spec, sc_idx, member_offset
        )
        if cum is None:
            return None
        # Net flux on each timebound = diff of cumulative (year-over-year).
        return np.concatenate([[np.nan], np.diff(cum)])

    if leaf == "CO2":
        ffi = _flux("CO2 FFI")
        afolu = _flux("CO2 AFOLU")
        if ffi is None or afolu is None:
            return None
        unit = desired_emissions_units.get("CO2 FFI", "Gt C/yr")
        return ffi + afolu, unit
    species_name = OUTPUT_LEAF_TO_FAIR2_SPECIES.get(leaf)
    if species_name is None:
        return None
    values = _flux(species_name)
    if values is None:
        return None
    unit = desired_emissions_units.get(species_name, "unknown/yr")
    return values, unit


def _airborne_emissions_per_species(f, leaf, sc_idx, member_offset):
    """Read FaIR's airborne_emissions for ``leaf`` (cumulative)."""
    from fair.structure.units import desired_emissions_units

    species_name = OUTPUT_LEAF_TO_FAIR2_SPECIES.get(leaf)
    if species_name is None:
        return None
    values = _read_specie_array(
        f, "airborne_emissions", species_name, sc_idx, member_offset
    )
    if values is None:
        return None
    unit = desired_emissions_units.get(species_name, "unknown/yr").replace(
        "/yr", ""
    )
    return values, unit


def _read_specie_array(
    f, array_name: str, spec: str, sc_idx: int, member_offset: int
):
    """Index a per-species (timebound, scenario, config) array on FAIR."""
    array = getattr(f, array_name)
    if spec not in array["specie"].values:
        return None
    return (
        array.sel(specie=spec)
        .isel(scenario=sc_idx, config=member_offset)
        .values
    )


def _build_scmrun(rows, timebounds) -> ScmRun:
    """
    Stack per-(scenario, member, variable) Series into a single
    :class:`scmdata.ScmRun`.
    """
    data = np.vstack([np.asarray(row[6]) for row in rows])
    meta = pd.DataFrame(
        [row[:6] for row in rows],
        columns=["scenario", "model", "region", "variable", "unit", "run_id"],
    )
    df = pd.DataFrame(
        data, index=pd.MultiIndex.from_frame(meta), columns=timebounds
    )
    return ScmRun(df)
