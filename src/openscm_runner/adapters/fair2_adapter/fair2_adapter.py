"""
Adapter for FaIR 2.x (native-calibration mode, v1 scope).

This adapter is a sibling to :class:`openscm_runner.adapters.fair_adapter.FAIR`
(which wraps FaIR 1.6) and does not replace it. The 1.6 adapter is kept
working for downstream users that depend on its outputs; this one
targets the AR7-relevant calibrations of FaIR 2.x.

**Scope of this first version**

Native-calibration mode only. Each entry in the per-model ``cfgs`` list
must carry a ``native_calibration`` sidecar key pointing at a FaIR 2.x
calibration bundle (a directory of CSVs as published on Zenodo, e.g.
https://zenodo.org/records/18828694). The runner loads the bundle,
builds a single :class:`fair.FAIR` instance per cfg entry whose
``config`` dimension is the calibration's parameter posterior (optionally
subset by ``member_indices``), and dispatches to FaIR's native xarray
ensemble API.

Translated-cfg mode (the FaIR 1.6 adapter's pattern of hand-built
per-member dicts) is deliberately **not** implemented in this PR. It
will land in a follow-up; until then, cfg dicts without a
``native_calibration`` key raise :class:`NotImplementedError`.

Variable mapping is currently minimal: emissions inputs supported are
the four main GHGs (CO2 FFI, CO2 AFOLU, CH4, N2O), and outputs are
Surface Air Temperature Change, total Effective Radiative Forcing, and
the CO2 concentration. Unmapped emissions species are logged at WARNING
and ignored (FaIR's bundle-provided historical / default values are
used in their place). The full mapping is a follow-up; see the
architecture notes.

**Per-cfg sidecar keys**

- ``native_calibration`` (native mode, required): filesystem path to
  the bundle directory, or an in-memory
  :class:`NativeFairCalibration` instance.
- ``member_indices`` (native mode, optional, default = all members):
  sequence of zero-based ``int`` selecting which rows of the
  parameter posterior to use as the FaIR config dimension.
  ``range(N)`` gives "first N members"; an explicit list lets the
  user stratify or reproduce a specific subset.
- ``emissions_bundle`` (translated mode, optional): filesystem path
  to a calibration bundle (or a :class:`NativeFairCalibration`).
  When set, the bundle's historical emissions, species_configs and
  natural forcings are used as the baseline; only the cfg dict's
  climate parameters vary per member. All cfgs in one call must
  share the same value. When omitted, translated mode falls back to
  FaIR's ``fill_from_rcmip()`` (known to break against fair 2.2.4
  for some species).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any

import pandas as pd
from scmdata import ScmRun, run_append

from ..._run_mode import RunMode
from ..base import _Adapter
from ._compat import HAS_FAIR2, fair2
from ._emissions_translator import build_emissions_df
from ._native_calibration import NativeFairCalibration
from ._output_extractor import extract_outputs

LOGGER = logging.getLogger(__name__)


class FAIR2(_Adapter):
    """
    Adapter for running FaIR 2.x with a native calibration bundle.

    Registered under ``model_name = "FaIRv2"`` (distinct from the
    existing ``"FaIR"`` which is the FaIR 1.6 adapter).
    """

    model_name = "FaIRv2"
    supported_modes = frozenset(
        {RunMode.EMISSIONS_DRIVEN, RunMode.CONCENTRATION_DRIVEN}
    )

    def _init_model(self):
        if not HAS_FAIR2:
            raise ImportError(
                "FaIR 2.x is not installed. Run 'pip install \"fair>=2.2,<3\"' "
                "or 'pip install openscm-runner[fair2]'. Note this conflicts "
                "with the FaIR 1.6 adapter's 'fair<2' pin; only one major "
                "version of fair can be installed at a time."
            )

    def _run(self, scenarios, cfgs, output_variables, output_config):
        if output_config is not None:
            raise NotImplementedError(
                "`output_config` not implemented for FaIRv2"
            )

        # Apply adapter-level driving mode uniformly: ``self.mode`` is
        # the canonical public surface, the per-cfg
        # ``fair2_conc_driven`` boolean is an internal detail. Setting
        # the flag here means downstream code (``_run_native_cfgs``,
        # ``_run_one_calibration``) keeps reading the same key it
        # always has.
        cfgs = [_with_mode_applied(cfg, self.mode) for cfg in cfgs]

        # Mode detection: each cfg dict is either native (carries a
        # `native_calibration` sidecar key, expands to the calibration's
        # parameter posterior) or translated (FaIR 2.x parameter names
        # as dict keys, becomes a single config in FaIR's config dim).
        # Mixed cfgs are rejected for now; supporting them is a
        # straightforward follow-up but adds bookkeeping that is not
        # warranted by any current use case.
        native_flags = ["native_calibration" in cfg for cfg in cfgs]
        if all(native_flags):
            out = _run_native_cfgs(scenarios, cfgs, output_variables)
        elif not any(native_flags):
            out = _run_translated_cfgs(scenarios, cfgs, output_variables)
        else:
            raise NotImplementedError(
                "FaIRv2 cfgs must be all-native or all-translated; mixing "
                "native and translated cfgs in one call is not supported "
                "in v1. Run the two modes in separate run.run calls."
            )

        out["climate_model"] = f"FaIRv{self.get_version()}"
        return out

    @classmethod
    def from_native_distribution(
        cls,
        native_distribution_path,
        mode: RunMode = RunMode.EMISSIONS_DRIVEN,
        member_indices=None,
        output_variables: Iterable[str] | None = None,
        output_config: Iterable[str] | None = None,
        **cfg_overrides: Any,
    ) -> "FAIR2":
        """
        Construct from a FaIR 2.x calibration bundle on disk.

        Parameters
        ----------
        native_distribution_path
            Directory of CSVs as published on Zenodo (e.g. record
            18828694). Must contain at least the parameter posterior
            and species_configs files; see
            :class:`NativeFairCalibration` for the full file list.
        mode
            Driving mode. ``RunMode.CONCENTRATION_DRIVEN`` requires
            ``fair2_conc_bundle_dir`` to be passed as a ``cfg_override``
            (path to the CICERO RCMIP bundle whose ``{scen}_conc_*``
            files the adapter reads).
        member_indices
            Optional zero-based row indices into the parameter
            posterior. ``None`` (default) selects all members.
        output_variables, output_config
            Forwarded to the adapter constructor.
        **cfg_overrides
            Forwarded as keys on the single native cfg dict. Useful
            keys: ``fair2_conc_bundle_dir`` (optional fallback for CD
            mode -- only used when the scenarios DataFrame has no
            ``Atmospheric Concentrations|*`` rows),
            ``fair2_conc_gases_ep`` (default ``"gases_vupdate_2024_WMO_added_new.txt"``),
            ``fair2_stochastic_run`` (default ``False``).

        Returns
        -------
        FAIR2
            Configured adapter, ready to call ``.run(scenarios)``.

        Notes
        -----
        Construction does not check whether CD mode will have
        concentrations available. If neither the scenarios DataFrame
        passed at ``.run()`` time nor ``fair2_conc_bundle_dir`` supplies
        them, the adapter raises ``ValueError`` from inside
        ``.run()``.
        """
        calibration = NativeFairCalibration(native_distribution_path)
        cfg: dict[str, Any] = {"native_calibration": calibration}
        if member_indices is not None:
            cfg["member_indices"] = member_indices
        cfg.update(cfg_overrides)

        return cls(
            cfgs=[cfg],
            mode=mode,
            output_variables=output_variables,
            output_config=output_config,
        )

    @staticmethod
    def get_version():
        """Return the installed FaIR version string (e.g. ``"2.2.4"``)."""
        if not HAS_FAIR2:
            raise ImportError("FaIR 2.x is not installed")
        return fair2.__version__


def _with_mode_applied(cfg: dict[str, Any], mode: RunMode) -> dict[str, Any]:
    """
    Inject the adapter-level ``mode`` into a cfg as the internal
    ``fair2_conc_driven`` flag.

    Returns a new dict; the caller's cfg is not mutated.
    """
    new = dict(cfg)
    new["fair2_conc_driven"] = mode == RunMode.CONCENTRATION_DRIVEN
    return new


def _zero_fill_year_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace NaN with 0.0 in the year columns of an emissions or
    concentrations DataFrame.

    Year columns are detected as columns whose name is a digit string
    (e.g. ``"1850"``); meta columns (``scenario``, ``variable``, ...)
    are left untouched. Used as one of two NaN-tolerance layers on the
    way into FaIR; see also :func:`_zero_fill_fair_arrays`.
    """
    year_cols = [c for c in df.columns if isinstance(c, str) and c.isdigit()]
    if not year_cols:
        return df
    out = df.copy()
    out[year_cols] = out[year_cols].fillna(0.0)
    return out


def _zero_fill_fair_arrays(f) -> None:
    """
    Replace NaN with 0.0 in ``f.emissions`` / ``f.concentration`` /
    ``f.forcing`` in-place.

    :meth:`fair.FAIR.run` checks per-species input arrays for NaN
    before computing anything (``fair.FAIR._check_properties``) and
    raises ``ValueError`` if any input-mode species has NaN. This
    bites the scenarios-driven CD path: the user may supply only
    ``Atmospheric Concentrations|CO2``, which fills FaIR's ``CO2``
    species (concentration mode) but leaves ``CO2 FFI`` and
    ``CO2 AFOLU`` (still emissions mode) with NaN for years outside
    the bundle's historical span.

    The non-NaN-but-zero state is the right physical interpretation:
    species not covered by user inputs simply contribute nothing.
    For emissions-mode species this means zero forcing; for
    concentration-mode species the zero emissions array is unused
    (the concentration trajectory drives the simulation). Same for
    the forcing-mode array on natural forcing species the caller did
    not provide.
    """
    import numpy as np

    for attr in ("emissions", "concentration", "forcing"):
        arr = getattr(f, attr, None)
        if arr is None:
            continue
        values = getattr(arr, "values", None)
        if values is None:
            continue
        mask = np.isnan(values)
        if mask.any():
            values[mask] = 0.0


def _resolve_calibration(value: Any) -> NativeFairCalibration:
    """
    Accept either a path-like or an already-loaded
    :class:`NativeFairCalibration` and return a calibration instance.
    """
    if isinstance(value, NativeFairCalibration):
        return value
    return NativeFairCalibration(value)


def _run_native_cfgs(scenarios, cfgs, output_variables) -> ScmRun:
    """
    Native-calibration dispatch: each cfg is a calibration choice
    that expands to its parameter posterior on FaIR's config dim.

    Each entry in ``cfgs`` becomes one FAIR run; results are
    concatenated. ``run_id`` is assigned sequentially across all
    members of all cfgs so the combined ScmRun has unique run_ids.
    """
    results = []
    # Up-front cfg validation: catch user errors before we touch any
    # calibration files (so the error doesn't depend on a valid
    # bundle being available). Conc-driven mode needs concentrations
    # from somewhere -- either the scenarios DataFrame (preferred,
    # Atmospheric Concentrations|*) or a bundle directory of CICERO-
    # format `{scen}_conc_*` files. If neither source is available,
    # raise here rather than waiting for fair.FAIR.run to fail with
    # an opaque "missing input" error.
    scenarios_have_conc = (
        scenarios is not None
        and not scenarios.empty
        and not scenarios.filter(
            variable="Atmospheric Concentrations|*", log_if_empty=False
        ).empty
    )
    for cfg in cfgs:
        conc_driven = cfg.get("fair2_conc_driven") is True
        if conc_driven and not cfg.get("fair2_conc_bundle_dir") and not scenarios_have_conc:
            raise ValueError(
                "FaIRv2 conc-driven mode needs concentrations from "
                "either the scenarios DataFrame "
                "(``Atmospheric Concentrations|*`` rows) or a bundle "
                "directory of RCMIP-format ``{scen}_conc_*`` files "
                "(``fair2_conc_bundle_dir`` cfg key). Neither was "
                "supplied."
            )

    run_id_offset = 0
    for cfg_index, cfg in enumerate(cfgs):
        calibration = _resolve_calibration(cfg["native_calibration"])
        member_indices = cfg.get("member_indices")
        members = calibration.select_members(member_indices)

        LOGGER.info(
            "Running FaIRv2 (cfg %d/%d, native) with %d ensemble "
            "members from %s",
            cfg_index + 1,
            len(cfgs),
            len(members),
            calibration.path,
        )

        scmrun_chunk = _run_one_calibration(
            scenarios=scenarios,
            calibration=calibration,
            members=members,
            output_variables=output_variables,
            run_id_offset=run_id_offset,
            conc_driven=cfg.get("fair2_conc_driven"),
            conc_bundle_dir=cfg.get("fair2_conc_bundle_dir"),
            conc_gases_ep=cfg.get(
                "fair2_conc_gases_ep",
                "gases_vupdate_2024_WMO_added_new.txt",
            ),
            stochastic_run=cfg.get("fair2_stochastic_run", False),
            rcmip3_bundle_path=cfg.get("rcmip3_bundle_path"),
            scenario_to_category=cfg.get("scenario_to_category"),
        )
        results.append(scmrun_chunk)
        run_id_offset += len(members)

    return run_append(results)


def _run_translated_cfgs(  # noqa: PLR0912, PLR0915
    scenarios, cfgs, output_variables
) -> ScmRun:
    """
    Translated-cfg dispatch: each cfg dict is one ensemble member
    whose keys are FaIR 2.x parameter names.

    All cfgs go into a single FAIR instance with ``config`` dim sized
    to ``len(cfgs)``, which is much faster than spawning one FAIR
    per cfg. Climate configs are populated from the cfg dicts.

    Two sub-modes, distinguished by the optional ``emissions_bundle``
    sidecar key:

    - **Bundle-backed (recommended).** Each cfg carries
      ``emissions_bundle`` pointing at a calibration bundle (all
      cfgs in one call must agree). Species configs, historical
      emissions splice (with user ScmRun on top) and natural
      forcings come from the bundle. This is the workhorse path
      for parameter-sweep studies on realistic emissions.

    - **RCMIP-defaults fallback.** No cfg carries
      ``emissions_bundle``. Species configs come from FaIR's
      shipped AR6 defaults and emissions are seeded from FaIR's
      ``fill_from_rcmip()``. Note: fair 2.2.4's RCMIP loader is
      known to break on HFC-4310mee (compound-convert key mismatch
      with the upstream RCMIP CSV); use the bundle-backed path
      until upstream fixes it.

    Supported cfg keys are anything FaIR 2.x exposes on
    ``climate_configs`` or ``species_configs``, plus the
    ``emissions_bundle`` sidecar. Unknown keys are logged at
    WARNING and ignored. If after population some required
    climate_configs value is still NaN, FaIR's ``run()`` raises
    ``ValueError`` which we re-raise with a hint pointing back at
    native-calibration mode.
    """
    from fair.interface import fill
    from fair.io import read_properties

    scenario_run = ScmRun(scenarios.timeseries()) if scenarios is not None else None
    scenario_names = (
        sorted(set(scenario_run["scenario"]))
        if scenario_run is not None and not scenario_run.empty
        else ["historical"]
    )

    # All cfgs in one call share a single FAIR instance, so they must
    # also share the bundle (which sets the species list, time axis
    # of historical emissions, and natural forcings). Reject mixed
    # configurations rather than silently using only one.
    bundle_values = [cfg.get("emissions_bundle") for cfg in cfgs]
    unique_bundles = {id(b) if not isinstance(b, (str, type(None))) else b
                      for b in bundle_values}
    if len(unique_bundles) > 1:
        raise NotImplementedError(
            "All cfgs in a single FaIRv2 translated-cfg call must "
            "share the same `emissions_bundle` value (or all omit "
            "it). Got %d distinct values." % len(unique_bundles)
        )
    bundle_value = bundle_values[0]
    calibration = _resolve_calibration(bundle_value) if bundle_value else None

    # All cfgs in one call must agree on the RCMIP3 forcing inputs
    # too: the natural-forcing fill is shared. Same uniqueness rule
    # as `emissions_bundle` above.
    rcmip3_values = [cfg.get("rcmip3_bundle_path") for cfg in cfgs]
    if len(set(rcmip3_values)) > 1:
        raise NotImplementedError(
            "All cfgs in a single FaIRv2 translated-cfg call must "
            "share the same `rcmip3_bundle_path` (or all omit it). "
            f"Got {len(set(rcmip3_values))} distinct values."
        )
    rcmip3_bundle_path = rcmip3_values[0]
    scenario_to_category_values = [
        cfg.get("scenario_to_category") for cfg in cfgs
    ]
    # dict isn't hashable; compare by id-or-content. Same rule applies.
    if (
        any(v is not None for v in scenario_to_category_values)
        and not all(
            v == scenario_to_category_values[0]
            for v in scenario_to_category_values
        )
    ):
        raise NotImplementedError(
            "All cfgs in a single FaIRv2 translated-cfg call must "
            "share the same `scenario_to_category` (or all omit it)."
        )
    scenario_to_category = scenario_to_category_values[0]

    # SCIENTIFIC CHOICE: same defaults as native mode (1750 start,
    # 1-year step). Made configurable in a follow-up.
    start_year = 1750
    end_year = (
        int(scenario_run.time_points.years().max())
        if scenario_run is not None and not scenario_run.empty
        else 2100
    )

    if calibration is not None:
        species, properties = read_properties(
            filename=calibration.file("species_configs")
        )
    else:
        species, properties = read_properties()

    config_labels = [f"config_{i}" for i in range(len(cfgs))]

    f = fair2.FAIR()
    f.define_time(start_year, end_year, 1)
    f.define_scenarios(scenario_names)
    f.define_configs(config_labels)
    f.define_species(species, properties)
    f.allocate()

    # allocate() leaves state arrays as NaN, which FaIR's run() then
    # propagates forward from t=0. Initialise to zero so the
    # integration has a defined starting point. See _run_one_calibration
    # for the equivalent in native mode.
    from fair.interface import initialise as _initialise

    _initialise(f.temperature, 0)
    _initialise(f.forcing, 0)
    _initialise(f.concentration, 0)
    _initialise(f.cumulative_emissions, 0)
    _initialise(f.airborne_emissions, 0)

    if calibration is not None:
        f.fill_species_configs(filename=calibration.file("species_configs"))
    else:
        f.fill_species_configs()

    LOGGER.info(
        "Running FaIRv2 (translated, %s) with %d ensemble members; "
        "climate_configs values come from cfg dicts",
        "bundle-backed" if calibration is not None else "RCMIP defaults",
        len(cfgs),
    )

    unknown_keys: set[str] = set()
    for cfg_idx, cfg in enumerate(cfgs):
        for key, value in cfg.items():
            if key == "emissions_bundle":
                continue  # sidecar, handled above
            if key in f.climate_configs:
                fill(f.climate_configs[key], value, config=config_labels[cfg_idx])
            elif key in f.species_configs:
                fill(f.species_configs[key], value, config=config_labels[cfg_idx])
            else:
                unknown_keys.add(key)

    if unknown_keys:
        LOGGER.warning(
            "FaIRv2 translated-cfg mode ignored unknown parameter "
            "names: %s. Valid names are FaIR 2.x climate_configs / "
            "species_configs keys.",
            sorted(unknown_keys),
        )

    if calibration is not None:
        bundle_emissions_csv = calibration.file("historical_emissions")
        flags = _resolve_protocol_flags(scenario_run, scenario_names)
        natural_off = tuple(s for s, (nat, _) in flags.items() if nat)
        land_use_zero = tuple(s for s, (_, lu) in flags.items() if lu)
        if bundle_emissions_csv is not None or (
            scenario_run is not None and not scenario_run.empty
        ):
            # Mixed-mode ScmRuns carry Atmospheric Concentrations rows
            # alongside Emissions; the conc path handles those, so
            # filter to Emissions|* here to avoid unit-conversion
            # warnings in the emissions translator.
            emissions_run = (
                scenario_run.filter(variable="Emissions|*")
                if scenario_run is not None and not scenario_run.empty
                else scenario_run
            )
            # Genuinely idealised scenarios (natural_forcing=off AND
            # land_use_forcing=constant_zero — esm-flat*, esm-bell-*,
            # esm-pi-*, 1pctCO2*, abrupt-*) get non-CO2 zeroed across
            # all years after the splice. Without this, the bundle's
            # historical_emissions leaks through for species the
            # loader doesn't supply (the protocol's flat/bell/pi/etc.
            # CSV rows are CO2-only by construction) and FaIR runs
            # with full historical CH4/Sulfur/NOx — the same
            # "historical leak in idealised" bug CICERO's issue-5
            # fix addresses on the other adapter.
            idealised_scenarios = tuple(
                s for s, (nat, lu) in flags.items() if nat and lu
            )
            emissions_df = build_emissions_df(
                emissions_run, bundle_emissions_csv, scenario_names,
                co2_only_scenarios=idealised_scenarios,
            )
            if not emissions_df.empty:
                # fair.FAIR.run rejects NaN in any species' emissions
                # array, even ones the user has flipped to
                # concentration-driven (CD species' arrays get
                # overwritten by fill_from_pandas(mode="concentration")
                # downstream, but the NaN-check fires before that).
                # Zero-fill so the CD override has a clean slate to
                # write over.
                emissions_df = _zero_fill_year_columns(emissions_df)
                f.fill_from_pandas(mode="emissions", df=emissions_df)
        _fill_natural_forcings(
            f, calibration,
            zero_natural_scenarios=natural_off,
            zero_land_use_scenarios=land_use_zero,
            rcmip3_bundle_path=rcmip3_bundle_path,
            scenario_to_category=scenario_to_category,
        )
    else:
        # No bundle: fall back to FaIR's RCMIP defaults. Known to
        # break on fair 2.2.4 for HFC-4310mee; recommend bundle path.
        # User emissions overrides via the ScmRun input are NOT merged
        # on top in this path (fill_from_pandas requires complete
        # coverage of every species, or it errors on the unit lookup).
        try:
            f.fill_from_rcmip()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.warning(
                "FaIRv2 translated mode could not seed emissions from "
                "RCMIP defaults (%s). Pass `emissions_bundle` in each "
                "cfg to use a calibration bundle for emissions instead.",
                exc,
            )
        if scenario_run is not None and not scenario_run.empty:
            LOGGER.warning(
                "FaIRv2 translated mode without `emissions_bundle` "
                "ignores the user's `scenarios` input (RCMIP defaults "
                "are used). Pass `emissions_bundle` to splice user "
                "scenarios on top of bundle historicals."
            )

    try:
        f.run(progress=False, suppress_warnings=True)
    except ValueError as exc:
        if "NaN values" in str(exc):
            raise ValueError(
                "FaIR 2.x rejected the run because required "
                "climate_configs values are missing. Translated-cfg "
                "mode requires each cfg to fully specify the climate "
                "parameters FaIR needs (ocean_heat_capacity, "
                "ocean_heat_transfer, deep_ocean_efficacy, "
                "forcing_4co2 at minimum). For runs that should use "
                "a published calibration as the baseline, pass "
                "'native_calibration' in the cfg instead. Original "
                f"FaIR error: {exc}"
            ) from exc
        raise

    return extract_outputs(
        f,
        scenario_names,
        pd.DataFrame(index=range(len(cfgs))),  # one row per ensemble member
        output_variables,
        run_id_offset=0,
        properties_df=getattr(f, "properties_df", None),
    )


def _run_one_calibration(  # noqa: PLR0912, PLR0913, PLR0915
    scenarios,
    calibration: NativeFairCalibration,
    members: pd.DataFrame,
    output_variables,
    run_id_offset: int,
    conc_driven=None,
    conc_bundle_dir=None,
    conc_gases_ep="gases_vupdate_2024_WMO_added_new.txt",
    stochastic_run: bool = False,
    rcmip3_bundle_path=None,
    scenario_to_category=None,
) -> ScmRun:
    """
    Run FaIR 2.x once with a single calibration choice and return the
    requested output variables as an :class:`scmdata.ScmRun`.

    Each row in ``members`` becomes one entry in FaIR's ``config``
    dimension. Output run_ids are ``run_id_offset + i`` so that
    concatenations across multiple calibration choices in the same
    ``run.run`` call stay unique.

    Concentration-driven mode (``conc_driven=True`` and
    ``conc_bundle_dir`` set) flips the GHG species present in the
    bundle's concentration files from emissions/calculated input
    mode to ``concentration``, reads their trajectories per scenario
    via :func:`_concentrations_translator.build_concentrations_df`,
    and feeds them to FaIR via ``fill_from_pandas(mode="concentration")``.
    FaIR's run loop calls ``unstep_concentration`` per timestep to
    back-calculate emissions for those species; the output extractor
    reads them out as ``Emissions|*`` variables.

    Auto-detect (``conc_driven=None``): mirrors CICEROSCMPY2's
    convention - scenarios starting with ``esm-`` or ``methanemip``
    run emissions-driven; everything else runs concentration-driven
    if ``conc_bundle_dir`` is provided. With no bundle, defaults to
    emissions-driven regardless of scenario name.

    Stochastic forcing (``stochastic_run``) controls FaIR 2.x's
    AR(1) natural-variability term on the energy-balance model
    (Cummins et al. 2020). Default is ``False`` so the per-member
    trajectories are deterministic given the calibration parameters
    - i.e. ensemble spread reflects parameter uncertainty only, not
    internal-variability noise on top. The AR7-relevant
    ``fair-calibrate`` bundles ship ``stochastic_run=True`` for
    every posterior member (with per-member ``sigma_eta`` /
    ``sigma_xi`` / ``seed``); the adapter overrides this back to
    ``False`` after loading the calibration parameters. Set
    ``fair2_stochastic_run=True`` in the cfg to opt back in.
    """
    from fair.io import read_properties

    scenario_run = ScmRun(scenarios.timeseries()) if scenarios is not None else None
    scenario_names = (
        sorted(set(scenario_run["scenario"]))
        if scenario_run is not None and not scenario_run.empty
        else ["historical"]
    )

    # Time axis spans the bundle's historical period through whatever the
    # scenario goes out to. Default to 2100 if no scenario provided.
    # SCIENTIFIC CHOICE: timestep=1 year, start=1750 (matches the bundle's
    # historical_emissions file). Made configurable in a follow-up.
    start_year = 1750
    end_year = (
        int(scenario_run.time_points.years().max())
        if scenario_run is not None and not scenario_run.empty
        else 2100
    )

    species, properties = read_properties(filename=calibration.file("species_configs"))

    # Resolve conc-driven mode + build the conc DataFrame up-front so
    # we know which species to flip from emissions / calculated to
    # concentration input_mode before define_species pins the species
    # set on the FAIR instance.
    #
    # Auto-detect: scenarios starting with `esm-` or `methanemip` run
    # emissions-driven (matching CICEROSCMPY2's convention); everything
    # else runs concentration-driven WHEN a conc_bundle_dir is provided.
    # Without a bundle, default to emissions-driven regardless.
    conc_df = None
    use_conc = False
    if conc_driven is True:
        use_conc = True
    elif conc_driven is None and conc_bundle_dir is not None:
        # Auto-detect from first scenario name.
        first = scenario_names[0].lower()
        use_conc = not first.startswith(("esm-", "esm_", "methanemip"))

    # Mixed-mode (protocol-strict ED CO2-only) detection: the loader's
    # _load_mixed_mode_scenario returns a ScmRun containing both
    # Emissions|CO2|* and Atmospheric Concentrations|* (non-CO2).
    #
    # FaIR's input_mode is a per-species flag that applies to ALL
    # scenarios in the FAIR instance, so mixed mode is only safe when
    # EVERY scenario in this batch supplies the same set of
    # Atmospheric Concentrations|* species. If the batch mixes
    # mixed-mode scenarios (esm-ssp245) with non-mixed (esm-flat10),
    # we'd flip species to conc-mode but fill_from_pandas would crash
    # on the missing rows for non-mixed scenarios. In that case we
    # fall back to the bundle-based conc_df path (when available) or
    # plain emissions-driven.
    if scenario_run is not None and not scenario_run.empty:
        scenarios_in_run = set(scenario_run["scenario"].unique())
        conc_run_for_batch = scenario_run.filter(
            variable="Atmospheric Concentrations|*",
        )
        conc_scenarios_in_run = (
            set(conc_run_for_batch["scenario"].unique())
            if not conc_run_for_batch.empty else set()
        )
        all_batch_scenarios_supply_conc = (
            len(conc_scenarios_in_run) > 0
            and conc_scenarios_in_run == scenarios_in_run
        )
    else:
        all_batch_scenarios_supply_conc = False

    if all_batch_scenarios_supply_conc:
        from ._concentrations_translator import (
            build_concentrations_df_from_scmrun,
        )

        conc_df = build_concentrations_df_from_scmrun(
            scenario_run,
            fair_species=species,
            nystart=start_year, nyend=end_year,
        )
        if conc_df.empty:
            LOGGER.warning(
                "FaIRv2 mixed mode: loader provided Atmospheric "
                "Concentrations rows but none mapped to fair_species; "
                "falling back to emissions-driven.",
            )
        else:
            # Only flip species that have rows for EVERY scenario in
            # the batch (defensive: fill_from_pandas can't tolerate a
            # missing (species, scenario) cell once input_mode is
            # flipped to concentration).
            scenarios_in_run = set(scenario_run["scenario"].unique())
            species_per_scenario = (
                conc_df.groupby("scenario")["variable"]
                .agg(set).to_dict()
            )
            common_conc_species = set.intersection(
                *(species_per_scenario[s] for s in scenarios_in_run
                  if s in species_per_scenario)
            ) if species_per_scenario else set()
            if not common_conc_species:
                LOGGER.warning(
                    "FaIRv2 mixed mode: no concentration species "
                    "shared by all scenarios in the batch; falling "
                    "back to emissions-driven.",
                )
                conc_df = None
            else:
                conc_df = conc_df[conc_df["variable"].isin(common_conc_species)]
                use_conc = True
                for sp_name in common_conc_species:
                    if sp_name in properties:
                        properties[sp_name] = {
                            **properties[sp_name],
                            "input_mode": "concentration",
                        }
                LOGGER.info(
                    "FaIRv2 mixed mode (protocol-strict ED CO2-only): "
                    "consuming %d concentration species from the "
                    "loader's ScmRun (CO2 stays emissions-driven). %s",
                    len(common_conc_species),
                    "Bundle-based conc_df path skipped." if conc_bundle_dir
                    else "",
                )
    elif use_conc:
        # `conc_bundle_dir is not None` is guaranteed by the cfg-level
        # validation in _run_native_cfgs (raised before we get here).
        from ._concentrations_translator import build_concentrations_df

        conc_df = build_concentrations_df(
            bundle_dir=conc_bundle_dir,
            gases_ep=conc_gases_ep,
            scenario_names=scenario_names,
            fair_species=species,
            nystart=start_year,
            nyend=end_year,
        )
        if conc_df.empty:
            LOGGER.warning(
                "FaIRv2 conc-driven: empty concentrations DataFrame "
                "from bundle %s; falling back to emissions-driven.",
                conc_bundle_dir,
            )
            use_conc = False
        else:
            # Flip input_mode for the GHG species we're driving with
            # concentrations. Other species (aerosols, forcing-mode
            # natural drivers) keep their bundle-specified mode and
            # are populated via emissions / natural-forcing inputs.
            conc_species = set(conc_df["variable"].unique())
            for sp_name in conc_species:
                if sp_name in properties:
                    properties[sp_name] = {
                        **properties[sp_name],
                        "input_mode": "concentration",
                    }
            LOGGER.info(
                "FaIRv2 conc-driven: flipped %d species to "
                "input_mode='concentration' (CO2, CH4, N2O, halocarbons). "
                "FaIR will back-calculate emissions for these species via "
                "unstep_concentration; aerosols still come from emissions "
                "input.",
                len(conc_species),
            )

    # Config labels MUST match the row labels in the calibration CSV;
    # FaIR's override_defaults uses self.configs to index into the
    # parameter file via df_configs.loc[config, col], which is type-
    # sensitive. Pass the parameter DataFrame's index values through
    # with their native dtype (typically int seed labels for the
    # AR7-relevant fair-calibrate bundles).
    f = fair2.FAIR()
    f.define_time(start_year, end_year, 1)
    f.define_scenarios(scenario_names)
    f.define_configs(list(members.index))
    f.define_species(species, properties)
    f.allocate()

    # allocate() leaves temperature / forcing / concentration arrays
    # as NaN. FaIR's run() integrates forward from year 0 (1750) using
    # values from the previous timestep, so the NaN at t=0 propagates
    # to every subsequent timestep and the whole simulation comes out
    # NaN. Initialise the state variables to zero before populating
    # inputs and running.
    from fair.interface import initialise

    initialise(f.temperature, 0)
    initialise(f.forcing, 0)
    initialise(f.concentration, 0)
    initialise(f.cumulative_emissions, 0)
    initialise(f.airborne_emissions, 0)

    # Populate species configs and override defaults from the calibration
    # bundle. The override step writes the per-member parameter posterior
    # into FaIR's config dimension.
    f.fill_species_configs(filename=calibration.file("species_configs"))
    f.override_defaults(calibration.file("parameters"))

    # SCIENTIFIC CHOICE: the AR7-relevant fair-calibrate bundles ship
    # `stochastic_run=True` for every posterior member, which adds an
    # AR(1) natural-variability term (Cummins et al. 2020) on top of
    # the deterministic per-member trajectory. Per-member ensemble
    # spread then reflects parameter uncertainty AND internal noise.
    # For openscm-runner's typical use case (compare medians + spreads
    # across scenarios) we want parameter-only spread by default, so
    # we flip stochastic_run back to False here. Set
    # `fair2_stochastic_run=True` in the cfg to opt back in (useful
    # for variability-focused studies; bundle still drives the
    # sigma_eta / sigma_xi / seed values).
    if not stochastic_run:
        f.climate_configs["stochastic_run"][:] = False
    else:
        LOGGER.info(
            "FaIRv2: stochastic_run=True; per-member trajectories include "
            "AR(1) natural-variability noise on top of the parameter "
            "posterior. Bundle's sigma_eta / sigma_xi / seed values are "
            "used."
        )

    # Splice the bundle's historical emissions with the user's scenario
    # data and let FaIR ingest the combined frame. Bundle historical
    # provides the baseline for every user scenario; user values
    # overwrite per-year where supplied. Species the user does not
    # provide (and species not in OPENSCM_TO_FAIR2_SPECIES) stay at
    # bundle-historical values for the historical period; FaIR's
    # interpolator handles missing future years by leaving NaN, which
    # the model treats as zero forcing for those species.
    bundle_emissions_csv = calibration.file("historical_emissions")
    if bundle_emissions_csv is None:
        LOGGER.warning(
            "Calibration bundle at %s does not contain %s. The user's "
            "scenario data will be passed straight through to FaIR; "
            "FaIR's interpolator will leave NaN for years the user did "
            "not cover.",
            calibration.path,
            calibration.FILES["historical_emissions"],
        )

    flags = _resolve_protocol_flags(scenario_run, scenario_names)
    natural_off = tuple(s for s, (nat, _) in flags.items() if nat)
    land_use_zero = tuple(s for s, (_, lu) in flags.items() if lu)

    if bundle_emissions_csv is not None or (
        scenario_run is not None and not scenario_run.empty
    ):
        # Mixed-mode ScmRuns include Atmospheric Concentrations rows
        # (handled separately via the conc_df path above). Filter them
        # out before passing to build_emissions_df, otherwise the
        # emissions translator tries to coerce ppb/ppt -> kt/yr and
        # logs a unit-conversion warning per species.
        emissions_run = (
            scenario_run.filter(variable="Emissions|*")
            if scenario_run is not None and not scenario_run.empty
            else scenario_run
        )
        # Genuinely idealised scenarios (natural=off AND LU=constant_zero)
        # need their non-CO2 zeroed post-splice so the bundle's
        # historical_emissions don't leak through for species the
        # loader doesn't supply. See the parallel comment in
        # _run_translated_cfgs above and CICERO's issue-5 fix.
        idealised_scenarios = tuple(
            s for s, (nat, lu) in flags.items() if nat and lu
        )
        emissions_df = build_emissions_df(
            emissions_run, bundle_emissions_csv, scenario_names,
            co2_only_scenarios=idealised_scenarios,
        )
        if not emissions_df.empty:
            # See parallel comment in _run_translated_cfgs: zero-fill so
            # any species without scenario coverage (e.g. CD species
            # whose values are written back by the concentration fill)
            # gets a non-NaN array fair.FAIR.run will accept.
            emissions_df = _zero_fill_year_columns(emissions_df)
            f.fill_from_pandas(mode="emissions", df=emissions_df)

    # Fill concentrations for the species we flipped above. FaIR's
    # run loop calls unstep_concentration per timestep to back-
    # calculate emissions for these species (see
    # fair.gas_cycle.inverse). Their concentration trajectories come
    # from the bundle's per-scenario `{scen}_conc_…` files via the
    # _concentrations_translator helper.
    if use_conc and conc_df is not None and not conc_df.empty:
        f.fill_from_pandas(mode="concentration", df=conc_df)

    # Natural (solar/volcanic) and land-use (Land use, Irrigation)
    # forcings live in separate CSVs in the bundle and use forcing-mode
    # inputs rather than emissions. Per-scenario suppression is now
    # driven by the loader's protocol_natural_forcing /
    # protocol_land_use_forcing meta cols (see _resolve_protocol_flags
    # for the fallback when those cols are missing).
    _fill_natural_forcings(
        f, calibration,
        zero_natural_scenarios=natural_off,
        zero_land_use_scenarios=land_use_zero,
        rcmip3_bundle_path=rcmip3_bundle_path,
        scenario_to_category=scenario_to_category,
    )

    # Final NaN tolerance: zero-fill any species (or year) the caller
    # didn't cover. See _zero_fill_fair_arrays for rationale. This is
    # the safety net that makes the scenarios-driven CD path
    # (Atmospheric Concentrations|* in the scenarios DataFrame, no
    # bundle conc dir) work without panicking on the un-flipped
    # emissions-mode siblings (CO2 FFI / CO2 AFOLU when only CO2 is
    # supplied as a concentration, etc.).
    _zero_fill_fair_arrays(f)

    f.run(progress=False, suppress_warnings=True)

    return extract_outputs(
        f,
        scenario_names,
        members,
        output_variables,
        run_id_offset,
        properties_df=getattr(f, "properties_df", None),
    )


# Legacy-path fallback: which column of the multi-scenario
# land_use_forcing / irrigation_forcing CSVs the precomputed FaIR
# calibration bundle ships (VL, LN, L, ML, M, H, HL). Used only by
# ``_fill_land_use_from_legacy_bundle``; the canonical path
# (``rcmip3_bundle_path`` cfg key) resolves per-scenario via
# :func:`openscm_runner.io.rcmip3.resolve_scenario_category` instead.
_DEFAULT_LAND_USE_SCENARIO = "M"


def _is_idealised(scenario_name: str) -> bool:
    """True for RCMIP3 idealised experiments that need zero natural forcing.

    Covers ``esm-flat*`` constant-emissions, ``esm-bell*`` and
    ``esm-pi-*`` impulse-response, ``1pctCO2*`` and ``abrupt-*``
    concentration-driven idealised runs.

    Legacy name-pattern fallback used by :func:`_resolve_protocol_flags`
    when the input ScmRun was constructed outside
    :func:`openscm_runner.scenarios.load_rcmip3_emissions` and therefore
    lacks the ``protocol_natural_forcing`` / ``protocol_land_use_forcing``
    meta columns. New code should prefer reading those columns directly.
    """
    s = scenario_name.lower()
    return (
        s.startswith("esm-flat") or s.startswith("esm-bell")
        or s.startswith("esm-pi-") or s.startswith("esm-1pct")
        or s.startswith("1pctco2") or s.startswith("abrupt")
    )


def _resolve_protocol_flags(
    scenario_run: ScmRun | None,
    scenario_names: Sequence[str],
) -> dict[str, tuple[bool, bool]]:
    """Return ``{scenario: (natural_forcing_off, land_use_zero)}`` per scenario.

    Reads ``protocol_natural_forcing`` and ``protocol_land_use_forcing``
    from the input ScmRun's meta columns when available; falls back to
    the legacy :func:`_is_idealised` name-pattern check for scenarios
    not covered by the meta (or for callers that constructed the ScmRun
    outside of ``load_rcmip3_*``). When the fallback fires, both flags
    move in lockstep — the legacy helper has no separate signal for
    land-use vs. natural forcing.
    """
    meta = getattr(scenario_run, "meta", None)
    have_meta = (
        meta is not None
        and "protocol_natural_forcing" in meta.columns
        and "protocol_land_use_forcing" in meta.columns
    )
    meta_by_scen: dict[str, tuple[bool, bool]] = {}
    if have_meta:
        grouped = meta.groupby("scenario")[
            ["protocol_natural_forcing", "protocol_land_use_forcing"]
        ]
        for scen_name, group in grouped:
            natural_off = set(group["protocol_natural_forcing"]) == {"off"}
            land_use_zero = (
                set(group["protocol_land_use_forcing"]) == {"constant_zero"}
            )
            meta_by_scen[str(scen_name)] = (natural_off, land_use_zero)

    result: dict[str, tuple[bool, bool]] = {}
    for name in scenario_names:
        if name in meta_by_scen:
            result[name] = meta_by_scen[name]
        else:
            ideal = _is_idealised(name)
            result[name] = (ideal, ideal)
    return result


def _fill_natural_forcings(
    f,
    calibration: NativeFairCalibration,
    *,
    zero_natural_scenarios: Iterable[str] = (),
    zero_land_use_scenarios: Iterable[str] = (),
    rcmip3_bundle_path: str | None = None,
    scenario_to_category: dict[str, str] | None = None,
) -> None:
    """
    Populate FaIR's forcing arrays for the bundle's forcing-input species.

    Solar, Volcanic, Land use, and Irrigation are forcing-input species
    in the v1.6.0 calibration bundle (the species_configs CSV overrides
    Land use and Irrigation from FaIR's default ``calculated`` mode to
    ``forcing`` mode). They bypass ``fill_from_pandas``'s emissions
    path, so we read each bundle CSV, reindex onto FaIR's timebounds,
    broadcast across scenario / config, and write into ``f.forcing``
    via ``fair.interface.fill``.

    All four species have two routes:

    * **Canonical RCMIP3 path** (``rcmip3_bundle_path`` set):

      - Solar / Volcanic come from per-scenario
        ``Effective Radiative Forcing|Natural|{Solar,Volcanic}`` rows
        in ``rcmip_phase3_forcing_v2.0.0.csv``.
      - Land use / Irrigation come from per-category
        ``input_datafiles_generation/data/Forcing_AFOLU_CO2.csv`` and
        ``Forcing_irrigation_population_scale.csv``, with the
        scenario resolved to a CMIP7 ScenarioMIP category via
        :func:`openscm_runner.io.rcmip3.resolve_scenario_category`
        (overrideable per scenario via ``scenario_to_category``).
      - Historical scenarios use the published per-component
        Albedo Change|{Land Use,Irrigation} breakdown in the
        canonical forcing CSV directly.

    * **Legacy bundle path** (``rcmip3_bundle_path is None``, default):
      reads the calibration bundle's per-species single-column CSVs
      (``solar_forcing``, ``volcanic_forcing``, ``land_use_forcing``,
      ``irrigation_forcing``). Solar / Volcanic broadcast a single
      trajectory across every scenario; Land use / Irrigation pick
      one CMIP7-target column for every scenario (``"M"`` per
      :data:`_DEFAULT_LAND_USE_SCENARIO`). This is the path we're
      moving away from.

    Two independent suppression sets:

    * ``zero_natural_scenarios`` zeros Solar and Volcanic forcing for
      the listed scenarios (RCMIP3 ``protocol_natural_forcing == "off"``:
      idealised experiments and piControl).
    * ``zero_land_use_scenarios`` zeros Land use and Irrigation for
      the listed scenarios (RCMIP3 ``protocol_land_use_forcing ==
      "constant_zero"``: same set in the current registry, but kept
      separate so a future scenario could combine on/off pairings).

    Missing CSVs leave the arrays at their default (zero) baseline.
    """
    import numpy as np

    from fair.interface import fill

    n_t = len(f.timebounds)
    n_scen = len(f.scenarios)
    n_cfg = len(f.configs)

    natural_mask = np.array(
        [s in zero_natural_scenarios for s in f.scenarios], dtype=bool,
    )
    land_use_mask = np.array(
        [s in zero_land_use_scenarios for s in f.scenarios], dtype=bool,
    )

    def _write(species_name, series, suppress_mask):
        # Reindex onto FaIR's timebounds and fill missing as zero.
        series = series.reindex(f.timebounds).fillna(0.0)
        per_scen = np.broadcast_to(
            series.values[:, None], (n_t, n_scen)
        ).copy()
        if suppress_mask.any():
            per_scen[:, suppress_mask] = 0.0
        broadcasted = np.broadcast_to(
            per_scen[:, :, None], (n_t, n_scen, n_cfg)
        )
        fill(f.forcing, broadcasted, specie=species_name)

    def _write_per_scenario(species_name, per_scen_2d, suppress_mask):
        # per_scen_2d shape: (n_t, n_scen). Already aligned to f.timebounds.
        per_scen = per_scen_2d.copy()
        if suppress_mask.any():
            per_scen[:, suppress_mask] = 0.0
        broadcasted = np.broadcast_to(
            per_scen[:, :, None], (n_t, n_scen, n_cfg)
        )
        fill(f.forcing, broadcasted, specie=species_name)

    # Solar + Volcanic: canonical RCMIP3 path if requested, else
    # legacy single-column bundle CSVs broadcast across scenarios.
    if rcmip3_bundle_path is not None:
        _fill_natural_from_rcmip3(
            f, rcmip3_bundle_path, natural_mask, _write_per_scenario,
        )
    else:
        _fill_natural_from_legacy_bundle(
            f, calibration, natural_mask, _write,
        )

    # Land use + Irrigation: canonical RCMIP3 path if requested,
    # otherwise legacy bundle path with the hardcoded "M" column.
    if rcmip3_bundle_path is not None:
        _fill_land_use_from_rcmip3(
            f, rcmip3_bundle_path, scenario_to_category,
            land_use_mask, _write_per_scenario,
        )
    else:
        _fill_land_use_from_legacy_bundle(
            f, calibration, land_use_mask, _write,
        )


def _fill_natural_from_legacy_bundle(f, calibration, natural_mask, _write):
    """
    Legacy bundle path for Solar + Volcanic forcings.

    Reads the calibration bundle's single-column ``solar_forcing`` /
    ``volcanic_forcing`` CSVs (year + value layout) and broadcasts a
    single trajectory across every scenario. Same behaviour as before
    the canonical RCMIP3 path was added; kept as a back-compat path
    when ``rcmip3_bundle_path`` isn't supplied.
    """
    single_col = {
        "Solar": ("solar_forcing", "solar_erf"),
        "Volcanic": ("volcanic_forcing", "volcanic_erf"),
    }
    for species_name, (bundle_key, value_col_prefix) in single_col.items():
        csv_path = calibration.file(bundle_key)
        if csv_path is None:
            LOGGER.warning(
                "Calibration bundle is missing %s; FaIR will use the "
                "default zero baseline for %s forcing.",
                calibration.FILES[bundle_key],
                species_name,
            )
            continue
        df = pd.read_csv(csv_path)
        year_col = next((c for c in df.columns if c.lower() == "year"), None)
        value_col = next(
            (c for c in df.columns if c.lower().startswith(value_col_prefix)),
            None,
        )
        if year_col is None or value_col is None:
            LOGGER.warning(
                "Unexpected layout for %s; expected year + %s_* columns, "
                "got %s. %s forcing left at default.",
                csv_path,
                value_col_prefix,
                list(df.columns),
                species_name,
            )
            continue
        _write(species_name, df.set_index(year_col)[value_col], natural_mask)


def _fill_natural_from_rcmip3(
    f, rcmip3_bundle_path, natural_mask, _write_per_scenario,
):
    """
    Canonical RCMIP3 path for Solar + Volcanic forcings.

    Reads per-scenario ``Effective Radiative Forcing|Natural|{Solar,
    Volcanic}`` rows from ``rcmip_phase3_forcing_v2.0.0.csv`` for each
    scenario in ``f.scenarios``. Scenarios in the natural-zero
    suppression set (``protocol_natural_forcing == "off"``) are left
    at zero. Scenarios with no matching row in the canonical CSV log
    a warning and stay at zero (e.g. native CMIP7
    ``scen7-{cat}`` names — the canonical CSV is keyed by SSP-RCP
    names).
    """
    import numpy as np

    from ...io.rcmip3 import load_rcmip3_forcings

    n_t = len(f.timebounds)
    n_scen = len(f.scenarios)

    components = {
        "Solar": (
            "Effective Radiative Forcing|Natural|Solar",
            np.zeros((n_t, n_scen)),
        ),
        "Volcanic": (
            "Effective Radiative Forcing|Natural|Volcanic",
            np.zeros((n_t, n_scen)),
        ),
    }

    for s_idx, scen in enumerate(f.scenarios):
        if natural_mask[s_idx]:
            continue
        for species_name, (variable, arr) in components.items():
            df = load_rcmip3_forcings(
                rcmip3_bundle_path,
                scenarios=[scen],
                variables=[variable],
            )
            if df.empty:
                LOGGER.warning(
                    "FaIR RCMIP3 natural-forcing path: scenario %r has "
                    "no %r row in the canonical forcing CSV. Leaving "
                    "%s at zero for that scenario.",
                    scen, variable, species_name,
                )
                continue
            year_cols = [c for c in df.columns if c.isdigit()]
            series = (
                df[year_cols].iloc[0]
                .rename(lambda y: int(y))
                .astype(float)
                .reindex(f.timebounds).fillna(0.0)
            )
            arr[:, s_idx] = series.values

    for species_name, (_, arr) in components.items():
        _write_per_scenario(species_name, arr, natural_mask)


def _fill_land_use_from_legacy_bundle(f, calibration, land_use_mask, _write):
    """
    Legacy bundle path for Land use + Irrigation forcings.

    Reads the precomputed multi-column CSVs
    (``land_use_forcing_timebounds_cmip7.csv``,
    ``irrigation_forcing_timebounds_cmip7.csv``) shipped with the
    FaIR calibration bundle, and picks
    :data:`_DEFAULT_LAND_USE_SCENARIO` (currently ``"M"``) as the
    column for every scenario. Same behaviour as openscm/openscm-runner#97
    before the canonical-RCMIP3 path was added; kept here as a
    back-compat path while bundles without RCMIP3-ready inputs exist.
    """
    multi_col = {
        "Land use": "land_use_forcing",
        "Irrigation": "irrigation_forcing",
    }
    for species_name, bundle_key in multi_col.items():
        csv_path = calibration.file(bundle_key)
        if csv_path is None:
            LOGGER.warning(
                "Calibration bundle is missing %s; FaIR will use the "
                "default zero baseline for %s forcing.",
                calibration.FILES[bundle_key],
                species_name,
            )
            continue
        df = pd.read_csv(csv_path, index_col=0)
        choice = _DEFAULT_LAND_USE_SCENARIO
        if choice not in df.columns:
            LOGGER.warning(
                "Bundle %s does not contain column %r; falling back to "
                "the first available column %r. %s forcing will reflect "
                "that choice. Pass `rcmip3_bundle_path` cfg key to use "
                "per-scenario canonical RCMIP3 lookups instead.",
                csv_path,
                choice,
                df.columns[0],
                species_name,
            )
            choice = df.columns[0]
        else:
            LOGGER.info(
                "Using %s column %r from %s for %s forcing (legacy "
                "bundle path; opt in to canonical per-scenario via "
                "`rcmip3_bundle_path`).",
                csv_path.name,
                choice,
                bundle_key,
                species_name,
            )
        _write(species_name, df[choice], land_use_mask)


def _fill_land_use_from_rcmip3(
    f, rcmip3_bundle_path, scenario_to_category, land_use_mask,
    _write_per_scenario,
):
    """
    Canonical RCMIP3 path for Land use + Irrigation forcings.

    For each scenario in ``f.scenarios``:

    * If the scenario is in the land-use-zero set (caller-side mask),
      leave the column as zeros.
    * If the scenario resolves to a CMIP7 ScenarioMIP category
      (``VL`` / ``LN`` / ``L`` / ``ML`` / ``M`` / ``H`` / ``HL``),
      read Land Use + Irrigation from the bundle's
      ``input_datafiles_generation/data/Forcing_AFOLU_CO2.csv`` and
      ``Forcing_irrigation_population_scale.csv``.
    * If the scenario is ``"historical"`` / ``"historical-cmip6"``,
      read the published per-component breakdown from
      ``rcmip_phase3_forcing_v2.0.0.csv``.
    * Otherwise, log a warning and leave as zeros.

    Both components are written separately to FaIR via
    ``_write_per_scenario`` so the species_configs declaration of
    Land use and Irrigation as distinct forcing-mode species is
    preserved.
    """
    import numpy as np

    from ...io.rcmip3 import (
        load_rcmip3_albedo_categories,
        load_rcmip3_forcings,
        resolve_scenario_category,
    )

    n_t = len(f.timebounds)
    n_scen = len(f.scenarios)

    # (component name -> per-scenario stack)
    components = {
        "Land Use": np.zeros((n_t, n_scen)),
        "Irrigation": np.zeros((n_t, n_scen)),
    }

    # Per-scenario data acquisition.
    for s_idx, scen in enumerate(f.scenarios):
        if land_use_mask[s_idx]:
            continue  # zero by suppression
        try:
            category = resolve_scenario_category(
                scen, overrides=scenario_to_category,
            )
        except KeyError as exc:
            LOGGER.warning(
                "FaIR RCMIP3 land-use path: scenario %r has no CMIP7 "
                "category mapping (%s). Leaving Land use + Irrigation "
                "at zero for that scenario.",
                scen, exc,
            )
            continue

        if category is None:
            # historical / historical-cmip6: read per-component
            # breakdown from the canonical forcing CSV.
            for component_name, var_suffix in (
                ("Land Use", "Albedo Change|Land Use"),
                ("Irrigation", "Albedo Change|Irrigation"),
            ):
                df = load_rcmip3_forcings(
                    rcmip3_bundle_path,
                    scenarios=[scen],
                    variables=[
                        f"Effective Radiative Forcing|Anthropogenic|"
                        f"{var_suffix}"
                    ],
                )
                if df.empty:
                    LOGGER.warning(
                        "FaIR RCMIP3 land-use path: scenario %r has no "
                        "%r row in the canonical forcing CSV. Leaving "
                        "%s at zero.",
                        scen, var_suffix, component_name,
                    )
                    continue
                year_cols = [c for c in df.columns if c.isdigit()]
                series = (
                    df[year_cols].iloc[0]
                    .rename(lambda y: int(y))
                    .astype(float)
                    .reindex(f.timebounds).fillna(0.0)
                )
                components[component_name][:, s_idx] = series.values
        else:
            albedo = load_rcmip3_albedo_categories(
                rcmip3_bundle_path, category=category,
            )
            for component_name in ("Land Use", "Irrigation"):
                series = (
                    albedo[component_name]
                    .reindex(f.timebounds).fillna(0.0)
                )
                components[component_name][:, s_idx] = series.values

    # Write into FaIR. species_configs labels these as "Land use" and
    # "Irrigation"; the RCMIP3 component names are "Land Use" / "Irrigation".
    _write_per_scenario("Land use", components["Land Use"], land_use_mask)
    _write_per_scenario("Irrigation", components["Irrigation"], land_use_mask)
