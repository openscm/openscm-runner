"""
Canonical CICERO-SCM v2.x output variables and structural limits.

The CICEROSCMPY2 adapter passes user-supplied ``output_variables``
straight through to
:func:`ciceroscm.parallel.distributionrun.DistributionRun.run_over_distribution`,
which in turn looks them up in
:data:`ciceroscm.formattingtools.reformat_cscm_results.openscm_to_cscm_dict`
(direct variables) and :data:`carbon_cycle_outputs` (back-calculated
variables). Anything not in either dict is silently dropped from the
returned ``ScmRun`` — the user sees no error, just missing variables
in the result.

This module fixes that by:

1. Snapshotting the canonical openscm-naming set CICERO-SCM v2.x can
   produce (~120 variables, sourced live from the upstream dicts so
   the snapshot stays in sync as upstream adds variables).
2. Documenting the RCMIP variables that CICERO-SCM v2.x is
   structurally incapable of producing, with reasons.
3. Exposing a :func:`validate_output_variables` validator that the
   adapter's ``_run`` calls before dispatching. Any requested variable
   that is neither in the supported set nor a known carbon-cycle
   variable raises ``ValueError`` with a categorised suggestion list,
   so failures surface up-front rather than as quiet zeros in the
   output.

**What CICERO-SCM v2.x supports** (categories, summary; the live
authoritative list is :data:`SUPPORTED_VARIABLES`):

- Surface Air Temperature variants (3): blended, sea, air-only.
- Total / Anthropogenic ERF + aerosol decomposition (~7),
  per-GHG ERF (CO2, CH4, N2O, F-Gases aggregate, stratospheric H2O,
  stratospheric & tropospheric O3).
- F-Gases × 23 species × {ERF, Concentrations} = 46
  (e.g. ``Effective Radiative Forcing|Anthropogenic|F-Gases|HFC|HFC125``).
- Montreal gases × 19 species × {ERF, Concentrations} = 38
  (e.g. ``Effective Radiative Forcing|Anthropogenic|Montreal Gases|CFC|CFC11``).
- Emissions back-calculation: CO2, CH4, N2O (when conc-driven).
- Heat Uptake (W/m²), Heat Content total + 0-700 m.
- Carbon-cycle diagnostics (6): biosphere/ocean fluxes, biosphere/
  ocean pools, airborne fraction, net flux to atmosphere. These are
  expensive (~30–50× per-member runtime on conc-driven runs); the
  adapter only computes them when actually requested.

**What CICERO-SCM v2.x cannot produce** (RCMIP3 variables that no
amount of adapter work will surface, with reasons):

- ``Sea Level Change`` and all sub-entries (~6 variables): no
  sea-level module.
- ``Effective Radiative Forcing|Anthropogenic|Albedo Change|Land use``:
  CICERO-SCM treats land-use albedo as a forcing input (read from
  ``LUCalbedo_RCMIP_*_RCMIP3.txt`` in the bundle) rather than an
  output diagnostic.
- ``Effective Radiative Forcing|Natural|{Solar, Volcanic}``: same —
  these are forcing inputs from the bundle's ``solar_RCMIP_*`` and
  ``VOLC_RCMIP_*`` files, summed into the ``+sunvolc`` total but not
  individually back-reported.
- ``Effective Radiative Forcing|Anthropogenic|Aerosol-cloud
  Interactions|*`` per-species splits (BC, OC, Sulfate, ...): the
  indirect aerosol forcing is a single ``SO4_IND`` term in
  CICERO-SCM; no per-species decomposition.
- ``Effective Radiative Forcing|Anthropogenic|Tropospheric Ozone|
  {NOx, CO, VOC, CH4} Contribution``: tropospheric ozone forcing is
  a lumped ``TROP_O3`` term; no precursor-attributed split.
- ``Effective Radiative Forcing|Anthropogenic|Other|{Contrails,
  BC on Snow, CH4 Oxidation Stratospheric H2O}``: stratospheric H2O
  from CH4 oxidation is exposed as ``STRAT_H2O``; the remaining
  "Other" subspecies are not modelled.
- ``Emissions|CO2|MAGICC {Fossil and Industrial, AFOLU}``: the back-
  calculated emissions reflect total CO2 only; CICERO-SCM does not
  attribute back-calculated CO2 to source sectors.
- ``Natural Fluxes|CH4|*`` and ``Natural Fluxes|N2O|*``: source-side
  decompositions of natural emissions are not produced (natural
  emissions are read from ``natemis_*`` files in the bundle).
- ``Ocean pH``: no carbonate chemistry module.
- ``Permafrost {CH4, CO2} Flux``: no permafrost module.

For users coming from FaIRv2: the structural-limits picture is
roughly opposite. FaIR has the more detailed aerosol decomposition
and Stratospheric/Tropospheric O3 source attribution; CICERO-SCM has
the more detailed carbon-cycle (compartmental pools, back-calculated
fluxes) and richer Montreal-gas species set. The unsupported set
here is what FaIR has and CICERO-SCM does not; the unsupported set
in :mod:`openscm_runner.adapters.fair2_adapter._output_extractor` is
what CICERO-SCM has and FaIR does not.
"""
from __future__ import annotations

import logging
from typing import Iterable

LOGGER = logging.getLogger(__name__)


def _build_supported_sets() -> tuple[frozenset[str], frozenset[str]]:
    """
    Snapshot the upstream variable sets at import time.

    Returns ``(direct, carbon_cycle)``: the variables produced by
    each upstream code path. Imported lazily so this module can be
    imported even when ``ciceroscm`` is not installed; in that case
    both sets are empty and the validator no-ops (the adapter's
    ``_compat`` shim will raise a clear ``ImportError`` elsewhere).
    """
    try:
        from ciceroscm.formattingtools.reformat_cscm_results import (
            carbon_cycle_outputs,
            openscm_to_cscm_dict,
        )
    except ImportError:
        return frozenset(), frozenset()

    direct = frozenset(
        # Upstream's dict contains one stray key with a trailing
        # apostrophe ("Atmospheric Concentrations|Ozone|Tropospheric'").
        # That's an upstream typo; we exclude it so users cannot
        # legitimately request a name that round-trips to nothing.
        k for k in openscm_to_cscm_dict if "'" not in k
    )
    cc = frozenset(carbon_cycle_outputs)
    return direct, cc


SUPPORTED_VARIABLES, CARBON_CYCLE_VARIABLES = _build_supported_sets()
"""All canonical openscm names the CICEROSCMPY2 adapter can produce.

``SUPPORTED_VARIABLES`` covers the direct output path (forcing,
concentrations, temperature, heat uptake, back-calculated CO2/CH4/N2O
emissions); ``CARBON_CYCLE_VARIABLES`` covers the more expensive
carbon-cycle back-calculation (fluxes, pools, airborne fraction).
Their union is what :func:`validate_output_variables` accepts."""


# Structurally-unsupported variables, grouped by the reason CICERO-SCM
# v2.x cannot produce them. These are checked first when building the
# error message so users see a useful suggestion rather than the bare
# fact that the variable name is unknown.
_STRUCTURAL_LIMITS: dict[str, tuple[str, ...]] = {
    "no sea-level module": (
        "Sea Level Change",
        "Sea Level Change|Glaciers",
        "Sea Level Change|Greenland",
        "Sea Level Change|Antarctica",
        "Sea Level Change|Thermal Expansion",
    ),
    "no per-species aerosol-cloud (indirect) split — only the lumped SO4_IND term": (
        "Effective Radiative Forcing|Anthropogenic|Aerosol|Aerosol-cloud Interactions|BC",
        "Effective Radiative Forcing|Anthropogenic|Aerosol|Aerosol-cloud Interactions|OC",
        "Effective Radiative Forcing|Anthropogenic|Aerosol|Aerosol-cloud Interactions|Sulfate",
    ),
    "tropospheric ozone forcing is lumped (TROP_O3); no precursor decomposition": (
        "Effective Radiative Forcing|Anthropogenic|Tropospheric Ozone|NOx",
        "Effective Radiative Forcing|Anthropogenic|Tropospheric Ozone|CO",
        "Effective Radiative Forcing|Anthropogenic|Tropospheric Ozone|VOC",
        "Effective Radiative Forcing|Anthropogenic|Tropospheric Ozone|CH4",
    ),
    "input-side forcing in CICERO-SCM (read from bundle files, not back-reported)": (
        "Effective Radiative Forcing|Anthropogenic|Albedo Change|Land use",
        "Effective Radiative Forcing|Natural|Solar",
        "Effective Radiative Forcing|Natural|Volcanic",
    ),
    "back-calculated CO2 not attributed by sector (FFI vs AFOLU not separated)": (
        "Emissions|CO2|MAGICC Fossil and Industrial",
        "Emissions|CO2|MAGICC AFOLU",
    ),
    "natural emissions are inputs (natemis_* files); no source decomposition exposed": (
        "Natural Fluxes|CH4|Wetlands",
        "Natural Fluxes|N2O|Soils",
    ),
    "not modelled": (
        "Ocean pH",
        "Permafrost CH4 Flux",
        "Permafrost CO2 Flux",
        "Effective Radiative Forcing|Anthropogenic|Other|Contrails",
        "Effective Radiative Forcing|Anthropogenic|Other|BC on Snow",
    ),
}


def all_supported() -> frozenset[str]:
    """Return the union of direct + carbon-cycle variables."""
    return SUPPORTED_VARIABLES | CARBON_CYCLE_VARIABLES


def validate_output_variables(requested: Iterable[str]) -> None:
    """
    Raise ``ValueError`` if any ``requested`` variable will silently drop.

    The CICERO-SCM v2.x output formatter discards variables it does
    not know about; this validator surfaces the discard up-front
    with a categorised message: structurally-unsupported variables
    are flagged with the reason, and the suggested-close-matches list
    helps users catch typos.

    Idempotent on empty input; ``requested`` is consumed once
    (an iterable is fine).
    """
    requested_set = set(requested)
    supported = all_supported()
    if not supported:
        # ciceroscm not importable; the adapter's _compat shim will
        # raise the canonical ImportError when something tries to
        # actually use the adapter. Don't shadow that with our own.
        return

    unknown = requested_set - supported
    if not unknown:
        return

    structurally_unsupported: dict[str, list[str]] = {}
    other_unknown: list[str] = []
    for var in sorted(unknown):
        reason = _structural_reason(var)
        if reason is None:
            other_unknown.append(var)
        else:
            structurally_unsupported.setdefault(reason, []).append(var)

    lines = [
        "CICEROSCMPY2: requested output variables that the adapter "
        "cannot produce (would be silently dropped from the result):",
        "",
    ]
    for reason, vars_ in structurally_unsupported.items():
        lines.append(f"  Structural limit ({reason}):")
        lines.extend(f"    - {v}" for v in vars_)
        lines.append("")
    if other_unknown:
        lines.append(
            "  Not recognised (typo? see _output_variables.SUPPORTED_VARIABLES "
            "for the canonical set):"
        )
        lines.extend(f"    - {v}" for v in other_unknown)
        lines.append("")
    lines.append(
        f"Total supported: {len(supported)} variables. "
        f"Drop or correct the entries above and retry."
    )
    raise ValueError("\n".join(lines))


def _structural_reason(variable: str) -> str | None:
    """
    Return the structural-limits reason for ``variable``, or ``None``.

    Match is exact-string against the curated examples first; for
    variables that share a structural prefix with a documented entry
    (e.g. any ``Sea Level Change|*``) the same reason applies.
    """
    for reason, examples in _STRUCTURAL_LIMITS.items():
        if variable in examples:
            return reason
        # Prefix match for the per-category families.
        for example in examples:
            head = example.split("|", 1)[0]
            if variable == head or variable.startswith(head + "|"):
                if head == example or _shares_family(variable, example):
                    return reason
    return None


def _shares_family(variable: str, example: str) -> bool:
    """
    True when ``variable`` and ``example`` share enough leading path
    segments to be considered part of the same structural family.

    Conservative: require a 2-segment overlap so e.g. "Effective
    Radiative Forcing|Anthropogenic|CO2" does not match the
    Aerosol-cloud examples just because they share the
    "Effective Radiative Forcing|Anthropogenic|" prefix.
    """
    v_parts = variable.split("|")
    e_parts = example.split("|")
    overlap = min(len(v_parts), len(e_parts), 3)
    return v_parts[:overlap] == e_parts[:overlap]
