"""
Adapter for CICERO-SCM v2.x (DistributionRun mode, v1 scope).

This adapter is a sibling to
:class:`openscm_runner.adapters.ciceroscm_py_adapter.CICEROSCMPY`
(which wraps the v1.1.x release with a per-config loop) and does not
replace it. The v1.1.x adapter is kept working for downstream users
that depend on its outputs; this one targets the AR7-relevant v2.1.0
release and its native ``DistributionRun`` ensemble API.

**Scope of this first version**

DistributionRun mode only. Each entry in the per-model ``cfgs`` list
must carry a ``distribution_json`` sidecar key pointing at a CICERO-SCM
parameter-distribution JSON (a posterior of ``pamset_udm`` +
``pamset_emiconc`` dicts, e.g. ``draw_samples_500.json``). The runner
hands the JSON to upstream's :class:`ciceroscm.parallel.DistributionRun`
and lets it dispatch the ensemble in parallel (upstream already manages
its own ProcessPool sized by the ``max_workers`` sidecar key).

Translated-cfg mode (one parameter dict per ensemble member, like the
v1.1.x adapter) is **not** implemented in this version. The v2.1.0
DistributionRun API is the path AR7-relevant CICERO Monte-Carlo runs
take, and a translated path adds bookkeeping that is not warranted by
any current use case.

**Two input modes — bundle mode is the recommended default**

*Bundle mode* **(use this for any AR7-relevant or scientifically
defensible run)**. Set ``cicero_bundle_dir`` to a directory laid
out like Marit's ``cscm-calibrate`` RCMIP working directory (the
per-scenario ``{scen}_em_{gases_ep}``, ``{scen}_conc_{gases_ep}``,
``solar_RCMIP_{scen}_RCMIP3.txt``, ``VOLC_RCMIP_…``,
``LUCalbedo_RCMIP_…``, plus ``natemis_CH4_…`` / ``natemis_N2O_…``
and the gaspam). For each scenario in the user ``scenarios``
ScmRun the adapter picks the matching files from the bundle,
falling back to ``historical`` files when scenario-specific ones
don't exist (the same logic ``run_full_rcmip_protocol.py`` in
``cscm-calibrate@ben_rcmip_sandbox`` uses). The adapter's
``_build_scendata_list_bundle`` reproduces that reference protocol
bit-exactly on the ``draw_samples_500`` posterior — verified
2026-05-24 to the digit for every year of ssp119 against a 10-
member subset of the same posterior.

*Splice mode* (legacy, **carries a calibration-mismatch bias —
prefer bundle mode**). Set ``gaspam_file`` + ``concentrations_file``
directly; the v1.1.x ``SCENARIODATAGETTER`` splices the user
ScmRun on top of its bundled ``ssp245_em_RCMIP.txt`` historical.
That historical is a v1.1.x-era file that does **not** match what
modern v2.x calibrations such as ``draw_samples_500`` were fit
against, so the calibration "sees" the wrong present-day forcing
baseline and warming comes out 0.3-0.5 K too high. On ssp119 with
the same 10-member subset, splice mode gives 1.85 K of 2024
warming where bundle mode (and the reference protocol) give
1.50 K. The adapter emits a ``LOGGER.warning`` whenever splice
mode is invoked so the bias is not silent. Kept as a back-compat
path for callers that have not yet migrated.

**Per-cfg sidecar keys**

- ``distribution_json`` (always required): filesystem path to a
  parameter-posterior JSON readable by ``DistributionRun``. Either
  a flat list of cfg dicts or a
  ``{"meta_info": ..., "configurations": [...]}`` envelope is
  accepted (upstream handles both).
- ``cicero_bundle_dir`` (bundle mode): directory containing the
  per-scenario CICERO-format inputs. When set, all other file paths
  default to canonical names within this directory and can be
  overridden individually with the ``*_file`` keys.
- ``cicero_gases_ep`` (bundle mode, optional): gaspam-name suffix
  used to build per-scenario filenames. Default
  ``"gases_vupdate_2024_WMO_added_new.txt"``.
- ``gaspam_file`` (splice mode required, bundle mode optional):
  filesystem path to a gases parameter file. In bundle mode
  defaults to ``cicero_bundle_dir / cicero_gases_ep``.
- ``concentrations_file`` (splice mode required, bundle mode
  optional): historical concentrations covering ``nystart`` to
  ``emstart``. In bundle mode picked per-scenario from the bundle.
- ``member_indices`` (optional, default = all members in JSON):
  sequence of zero-based ``int`` selecting rows of the posterior.
- ``max_workers`` (optional): forwarded to
  ``DistributionRun.run_over_distribution``. Defaults to
  :func:`openscm_runner.settings.get_worker_count` with
  ``CICEROSCM_WORKER_NUMBER`` as the override env var.
- ``nystart`` / ``nyend`` / ``emstart`` (optional): time bounds.
  Defaults: ``nystart=1750``,
  ``nyend=max(scenario_year)``. ``emstart`` is auto-derived in
  bundle mode (1850 for ``esm-allghg-*``; ``nyend`` for other
  emissions-driven and all concentration-driven runs, matching
  Marit's ``run_full_rcmip_protocol.py``); splice mode keeps the
  first-user-scenario-year default.
- ``cicero_conc_run`` (bundle mode, optional): force
  concentration-driven (``True``) or emissions-driven (``False``).
  Default is auto-detect from scenario name: ``esm-*`` and
  ``methanemip-*`` are emissions-driven; everything else (ssp*,
  scen7-*, 1pctCO2*, abrupt*, hist-*, piControl) is
  concentration-driven, matching Marit's protocol runner.
- ``sunvolc`` (optional, default ``1``).
- Optional pass-through forcing-file overrides: ``rf_sun_file``,
  ``rf_volc_n_file``, ``rf_volc_s_file``, ``rf_volc_file``,
  ``rf_luc_file``, ``nat_ch4_file``, ``nat_n2o_file``. In bundle
  mode these override the per-scenario default lookup.

**ssp245 fallback note (splice mode only)**

The splice mode's SCENARIODATAGETTER reuses the v1.1.x bundled
``ssp245_em_RCMIP.txt`` for the historical period and for species
the user scenario omits (legacy halocarbons CFC-11/12/113/114/115,
HCFC-22/141b/123/142b, H-1211/1301/2402, CH3Br, CCl4, CH3CCl3, and
the biomass-burning aerosol subspecies BMB_AEROS_BC /
BMB_AEROS_OC). For non-ssp245 scenarios this silently uses ssp245
trajectories. Bundle mode does not have this issue: each scenario's
own emissions / concentrations file is used directly.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from scmdata import ScmRun, run_append

from ..._run_mode import RunMode
from ...settings import config
from ..base import _Adapter
from ..ciceroscm_py_adapter.make_scenario_data import SCENARIODATAGETTER
from ._compat import HAS_CICEROSCM_PY2, _ciceroscm_major_version, cscmpy2

try:
    # `get_worker_count` lands with the SLURM-aware worker sizing PR
    # (modernisation/worker-counts); fall through to the simpler env-
    # var lookup when reviewing this branch alone against main.
    from ...settings import get_worker_count
except ImportError:  # pragma: no cover
    def get_worker_count(override_env_var: str | None = None) -> int:
        """Fallback worker-count lookup (override env var > cpu_count)."""
        if override_env_var and (val := config.get(override_env_var, None)):
            return max(int(val), 1)
        return max(os.cpu_count() or 1, 1)

LOGGER = logging.getLogger(__name__)

# Bundled historical emissions used by the SCENARIODATAGETTER splice
# (CICERO-SCM expects emissions starting from nystart). Lives under
# the v1.1.x adapter's utils_templates directory and is reused here to
# avoid a redundant copy; if you need a different historical baseline,
# fork SCENARIODATAGETTER to accept an explicit path.
_BUNDLED_HISTORICAL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "ciceroscm_adapter", "utils_templates"
)


class CICEROSCMPY2(_Adapter):
    """
    Adapter for running CICERO-SCM v2.x with a parameter-distribution JSON.

    Registered under ``model_name = "CICERO-SCM-PY2"`` (distinct from
    the existing ``"CICERO-SCM-PY"`` which wraps v1.1.x).
    """

    model_name = "CICERO-SCM-PY2"
    supported_modes = frozenset(
        {RunMode.EMISSIONS_DRIVEN, RunMode.CONCENTRATION_DRIVEN}
    )

    def _init_model(self):
        if not HAS_CICEROSCM_PY2:
            raise ImportError(
                "ciceroscm is not installed. Run 'pip install \"ciceroscm>=2,<3\"' "
                "or 'pip install openscm-runner[ciceroscmpy2]'. Note this "
                "conflicts with the v1.1.x adapter's 'ciceroscm<2' pin; only "
                "one major version of ciceroscm can be installed at a time."
            )
        major = _ciceroscm_major_version()
        if major < 2:
            raise ImportError(
                f"ciceroscm major version {major} is installed but the "
                "CICEROSCMPY2 adapter requires >=2. Either upgrade "
                "('pip install \"ciceroscm>=2,<3\"') or use the v1.1.x "
                "adapter (CICEROSCMPY) instead."
            )

    def _run(self, scenarios, cfgs, output_variables, output_config):
        if output_config is not None:
            raise NotImplementedError(
                "`output_config` not implemented for CICEROSCMPY2"
            )

        # Surface unsupported variables up-front: upstream silently
        # drops anything not in its reformat mapping, which means a
        # user who asks for e.g. ``Sea Level Change`` sees an empty
        # column rather than a clear error.
        from ._output_variables import validate_output_variables

        validate_output_variables(output_variables)

        from ._upstream_patches import (
            _CARBON_CYCLE_VARIABLES,
            output_vars_need_carbon_cycle,
        )
        if output_vars_need_carbon_cycle(output_variables):
            triggering = sorted(set(output_variables) & _CARBON_CYCLE_VARIABLES)
            LOGGER.info(
                "CICEROSCMPY2: output_variables include %s, which require "
                "the CICERO-SCM carbon-cycle back-calculation. This adds "
                "~30-50x per-member runtime on conc-driven runs (back-"
                "calculated emissions, airborne fraction, biosphere/ocean "
                "fluxes). Drop those variables from output_variables for "
                "a much faster run if you only need GSAT / ERF / "
                "concentrations.",
                triggering,
            )

        for cfg in cfgs:
            if "distribution_json" not in cfg:
                raise ValueError(
                    "CICEROSCMPY2 cfg is missing required sidecar key "
                    "'distribution_json'. See the adapter docstring for the "
                    "full list of supported sidecar keys."
                )
            if "cicero_bundle_dir" in cfg:
                # Bundle mode: paths derived from the bundle directory.
                continue
            # Splice mode: need explicit gaspam + concentrations files.
            for key in ("gaspam_file", "concentrations_file"):
                if key not in cfg:
                    raise ValueError(
                        f"CICEROSCMPY2 cfg is missing required sidecar key "
                        f"{key!r}. Either supply gaspam_file + "
                        "concentrations_file (splice mode) or set "
                        "cicero_bundle_dir (bundle mode). See the adapter "
                        "docstring."
                    )

        # Apply adapter-level driving mode uniformly: ``self.mode`` is
        # the canonical public surface, the per-cfg ``cicero_conc_run``
        # boolean is an internal detail. Setting the flag here means
        # downstream code (``_run_one_distribution`` etc.) keeps
        # reading the same key it always has, but the protocol
        # auto-detect-by-scenario-name fallback in those code paths
        # is bypassed in favour of an explicit user-supplied mode.
        cfgs = [_with_mode_applied(cfg, self.mode) for cfg in cfgs]

        results = []
        for cfg_index, cfg in enumerate(cfgs):
            LOGGER.info(
                "Running CICEROSCMPY2 (cfg %d/%d) with distribution %s",
                cfg_index + 1,
                len(cfgs),
                cfg["distribution_json"],
            )
            results.append(_run_one_distribution(scenarios, cfg, output_variables))

        out = run_append(results)
        out["climate_model"] = f"CICERO-SCM-PY{self.get_version()}"
        return out

    @classmethod
    def from_native_distribution(
        cls,
        native_distribution_path,
        mode: RunMode = RunMode.EMISSIONS_DRIVEN,
        distribution_json=None,
        member_indices=None,
        output_variables=None,
        output_config=None,
        **cfg_overrides: Any,
    ) -> "CICEROSCMPY2":
        """
        Construct from a CICERO-SCM 2.x bundle on disk.

        The bundle directory is Marit's ``rcmip-march2026`` layout
        (or equivalent): the per-scenario CICERO-format inputs live
        directly under the directory, and a parameter posterior JSON
        lives there alongside them. The classmethod auto-locates the
        JSON (a single ``*distribution*.json`` in the directory) and
        wires the bundle directory into the cfg.

        Parameters
        ----------
        native_distribution_path
            Bundle directory root.
        mode
            Driving mode. Maps to ``cicero_conc_run`` on the cfg.
        distribution_json
            Optional explicit path to the parameter posterior JSON.
            Defaults to the single ``*distribution*.json`` in the
            bundle directory.
        member_indices
            Optional zero-based row indices into the parameter
            posterior. ``None`` (default) selects all members.
        output_variables, output_config
            Forwarded to the adapter constructor.
        **cfg_overrides
            Forwarded as keys on the single bundle cfg dict. Useful
            keys: ``cicero_gases_ep``, ``nystart``, ``nyend``,
            ``emstart``, ``sunvolc``, and the optional
            forcing-file overrides documented in the class docstring.

        Returns
        -------
        CICEROSCMPY2
            Configured adapter, ready to call ``.run(scenarios)``.
        """
        from pathlib import Path

        bundle_dir = Path(native_distribution_path)
        if not bundle_dir.exists():
            raise FileNotFoundError(
                f"CICERO-SCM bundle directory not found: {bundle_dir}"
            )
        if not bundle_dir.is_dir():
            raise FileNotFoundError(
                f"CICERO-SCM bundle path is not a directory: {bundle_dir}"
            )

        if distribution_json is None:
            candidates = sorted(bundle_dir.glob("*distribution*.json"))
            if not candidates:
                raise FileNotFoundError(
                    f"No ``*distribution*.json`` in {bundle_dir}; pass "
                    "``distribution_json`` explicitly to "
                    "CICEROSCMPY2.from_native_distribution."
                )
            if len(candidates) > 1:
                raise ValueError(
                    f"Multiple ``*distribution*.json`` files in {bundle_dir}: "
                    f"{[c.name for c in candidates]}. Pass "
                    "``distribution_json`` explicitly to disambiguate."
                )
            distribution_json = candidates[0]

        cfg: dict[str, Any] = {
            "distribution_json": str(distribution_json),
            "cicero_bundle_dir": str(bundle_dir),
        }
        if member_indices is not None:
            cfg["member_indices"] = member_indices
        cfg.update(cfg_overrides)

        return cls(
            cfgs=[cfg],
            mode=mode,
            output_variables=output_variables,
            output_config=output_config,
        )

    @classmethod
    def get_version(cls):
        """Return the installed ciceroscm version (e.g. ``"2.1.0"``)."""
        if not HAS_CICEROSCM_PY2:
            import sys as _sys

            raise ImportError(
                "ciceroscm is not installed (this Python interpreter "
                f"is {_sys.version.split()[0]}; ciceroscm 2.x requires "
                "Python >= 3.10). Run 'pip install \"ciceroscm>=2,<3\"' "
                "or 'pip install openscm-runner[ciceroscmpy2]'."
            )
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("ciceroscm")
        except PackageNotFoundError:
            # Fall back to runtime __version__ (a setuptools_scm dev
            # string for source installs); better than nothing.
            return cscmpy2.__version__


def _with_mode_applied(cfg: dict[str, Any], mode: RunMode) -> dict[str, Any]:
    """
    Inject the adapter-level ``mode`` into a cfg as the internal
    ``cicero_conc_run`` flag.

    Returns a new dict; the caller's cfg is not mutated. Overrides
    any pre-existing per-cfg ``cicero_conc_run`` because the
    adapter-level mode is authoritative under the AdapterLike
    reshape; the protocol auto-detect-by-scenario-name fallback in
    the downstream code paths is bypassed.
    """
    new = dict(cfg)
    new["cicero_conc_run"] = mode == RunMode.CONCENTRATION_DRIVEN
    return new


def _run_one_distribution(scenarios, cfg: dict[str, Any], output_variables) -> ScmRun:
    """
    Dispatch one ``DistributionRun`` for the cfg.

    Builds scenariodata dicts from ``scenarios``, applies any
    ``member_indices`` subset to the JSON cfgs, and returns the
    concatenated ScmRun across all scenarios and members.
    """
    from ciceroscm.parallel.distributionrun import DistributionRun

    distribution_json = cfg["distribution_json"]
    if not os.path.exists(distribution_json):
        raise FileNotFoundError(
            f"CICEROSCMPY2 cfg `distribution_json` not found: "
            f"{distribution_json}"
        )

    # Validate cheap cfg invariants before doing scenariodata work.
    member_indices = cfg.get("member_indices")
    if member_indices is not None:
        member_indices = list(member_indices)
        if not member_indices:
            raise ValueError(
                "CICEROSCMPY2 cfg `member_indices` selected zero members; "
                "omit the key (or pass a non-empty sequence) to run the "
                "full distribution."
            )

    scendata_list = _build_scendata_list(scenarios, cfg)

    # distro_config is unused when json_file_name exists (upstream
    # checks os.path.exists before falling back to .make_config_lists).
    dist = DistributionRun(distro_config=None, json_file_name=distribution_json)

    if member_indices is not None:
        dist.cfgs = [dist.cfgs[i] for i in member_indices]

    max_workers = cfg.get("max_workers")
    if max_workers is None:
        max_workers = get_worker_count("CICEROSCM_WORKER_NUMBER")

    LOGGER.info(
        "CICEROSCMPY2 dispatching %d members x %d scenarios with "
        "max_workers=%d",
        len(dist.cfgs),
        len(scendata_list),
        max_workers,
    )

    result = dist.run_over_distribution(
        scendata_list, list(output_variables), max_workers=max_workers
    )
    # DistributionRun returns a pandas DataFrame (concatenated upstream);
    # wrap it as ScmRun so the adapter's caller gets the documented type.
    return ScmRun(result) if not isinstance(result, ScmRun) else result


def _build_scendata_list(scenarios, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert ``scenarios`` into the list of dicts upstream expects.

    Dispatches on the presence of ``cicero_bundle_dir`` in ``cfg``:

    * Bundle mode: paths are resolved per-scenario from the bundle
      directory (Marit-aligned setup). The user's ScmRun is used only
      to enumerate scenario names and pick the end year.
    * Splice mode: legacy path that uses SCENARIODATAGETTER to splice
      the user's ScmRun on top of the bundled ssp245 historical
      emissions.
    """
    if cfg.get("cicero_bundle_dir") is not None:
        return _build_scendata_list_bundle(scenarios, cfg)
    return _build_scendata_list_splice(scenarios, cfg)


def _build_scendata_list_splice(
    scenarios, cfg: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Splice-mode scendata builder.

    One dict per (model, scenario) pair. Emissions are built by
    SCENARIODATAGETTER (v1.1.x-inherited), which splices user emissions
    on top of the bundled ssp245 historical.
    """
    if scenarios is None:
        raise ValueError(
            "CICEROSCMPY2 splice mode requires `scenarios` to be provided "
            "(an emissions ScmRun). Set cicero_bundle_dir to run from a "
            "pre-built bundle without user emissions instead."
        )

    # Splice mode uses a v1.1.x-era ssp245 historical that does not match
    # v2.x calibrations (e.g. draw_samples_500), so present-day warming
    # comes out 0.3-0.5 K too high relative to bundle mode and the
    # reference protocol. Bundle mode is the supported path for any
    # scientifically defensible run; this warning fires once per run so
    # the bias is not silent. See module docstring for the diagnosis.
    LOGGER.warning(
        "CICEROSCMPY2: running in splice mode. Splice mode overlays "
        "user emissions on the v1.1.x-bundled ssp245 historical, which "
        "does not match v2.x calibrations and produces a present-day "
        "warm bias of ~0.3-0.5 K. Use bundle mode (set "
        "`cicero_bundle_dir` to a Marit-RCMIP-aligned directory) for "
        "any scientifically defensible run. See the CICEROSCMPY2 "
        "adapter module docstring for details."
    )

    nystart = int(cfg.get("nystart", 1750))
    scenario_years = scenarios.time_points.years()
    nyend = int(cfg.get("nyend", max(scenario_years)))
    emstart = int(cfg.get("emstart", min(scenario_years)))
    sunvolc_cfg = cfg.get("sunvolc")

    sdatagetter = SCENARIODATAGETTER(_BUNDLED_HISTORICAL_DIR, nystart, nyend)

    scendata_list: list[dict[str, Any]] = []
    timeseries = scenarios.timeseries(time_axis="year")
    for (scenario_name, model_name), scen_df in timeseries.groupby(
        ["scenario", "model"]
    ):
        emissions_df = sdatagetter.get_scenario_data(scen_df, nystart)
        spec = _resolve_protocol_spec(scenarios, scenario_name)
        if sunvolc_cfg is not None:
            scen_sunvolc = int(sunvolc_cfg)
        else:
            scen_sunvolc = 0 if spec["natural_forcing"] == "off" else 1
        scendata: dict[str, Any] = {
            "nystart": nystart,
            "nyend": nyend,
            "emstart": emstart,
            "sunvolc": scen_sunvolc,
            "scenname": scenario_name,
            "gaspam_file": cfg["gaspam_file"],
            "concentrations_file": cfg["concentrations_file"],
            "emissions_data": emissions_df,
        }
        # Pass through any explicit forcing-file overrides if the user
        # wants to replace ciceroscm's bundled solar / volcanic / LUC
        # data. Forwarded as-is; CICEROSCM validates these on init.
        for opt_key in (
            "rf_sun_file", "rf_volc_n_file", "rf_volc_s_file",
            "rf_volc_file", "rf_luc_file", "nat_ch4_file", "nat_n2o_file",
        ):
            if opt_key in cfg:
                scendata[opt_key] = cfg[opt_key]
        LOGGER.debug(
            "CICEROSCMPY2 splice scendata for scenario=%s model=%s years=%d-%d",
            scenario_name,
            model_name,
            nystart,
            nyend,
        )
        scendata_list.append(scendata)

    return scendata_list


# Default natural-emissions filenames in Marit's bundle layout.
_DEFAULT_NATEMIS_CH4 = (
    "natemis_CH4_ode_method_from_March2026_vupdate_2024_WMO_added_new.txt"
)
_DEFAULT_NATEMIS_N2O = (
    "natemis_N2O_ode_method_from_March2026_vupdate_2024_WMO_added_new.txt"
)
# Default gaspam-name suffix used in scenario file lookups.
_DEFAULT_GASES_EP = "gases_vupdate_2024_WMO_added_new.txt"


def _pick_bundle_file(bundle_dir, candidates: list[str]) -> str:
    """
    Return the first existing path from ``candidates`` under ``bundle_dir``.

    Mirrors the historical-fallback logic in Marit's
    ``run_full_rcmip_protocol.make_scenariodata_argdict``: try the
    scenario-specific name first, fall back to ``historical``.
    """
    for name in candidates:
        p = os.path.join(bundle_dir, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        f"None of these files exist in {bundle_dir}: {candidates}"
    )


def _find_bundle_file(bundle_dir, candidates: list[str]) -> str | None:
    """Like :func:`_pick_bundle_file` but returns ``None`` instead of raising."""
    for name in candidates:
        p = os.path.join(bundle_dir, name)
        if os.path.exists(p):
            return p
    return None


def _bundle_basename_candidates(scenario_name: str) -> list[str]:
    """Ordered fallback basenames for ``{scenario}_em_/conc_`` resolution.

    The CICEROSCM bundle uses BARE scenario names for its ``_em_*`` /
    ``_conc_*`` files. Protocol ED/CD/CO2-only/all-GHG distinctions live
    in cfg rather than the filename, so e.g. ``ssp245_em_*`` is the
    shared file for ``ssp245`` (CD), ``esm-ssp245`` (ED CO2-only), and
    ``esm-allGHG-ssp245`` (ED all-GHG). This helper produces the
    candidate basenames to try in order:

    - ``esm-allGHG-X`` -> ``[esm-allGHG-X, esm-X, X]``: the first is for
      the rare scenario-specific file (e.g. the CH4-swap variants), the
      second falls back to the CO2-only ED file if shipped, and the
      third lands on the bare bundle file.
    - ``esm-X`` -> ``[esm-X, X]``: try the explicit ED file first, then
      the bare bundle file.
    - ``scen7-XC`` (CD suffix) -> ``[scen7-XC, scen7-X]``: the bundle's
      ``scen7-H_conc_*`` is the right trajectory for ``scen7-HC``.

    For ``_em_*`` resolution the caller may also need to prefer hybrid
    mode (loader's masked ScmRun) over a stripped bundle file when the
    scenario is ED-CO2-only — see the caller for that logic.
    """
    candidates = [scenario_name]
    if scenario_name.startswith("esm-allGHG-"):
        rest = scenario_name[len("esm-allGHG-"):]
        candidates.append(f"esm-{rest}")
        candidates.append(rest)
    elif scenario_name.startswith("esm-"):
        candidates.append(scenario_name[len("esm-"):])
    if (
        scenario_name.startswith("scen7-")
        and scenario_name.endswith("C")
        and not scenario_name.startswith("esm-")
    ):
        candidates.append(scenario_name[:-1])
    return candidates


def _load_natemis_dataframe(path: str, component: str, nystart: int):
    """
    Load a CICEROSCM natural-emissions file as a DataFrame.

    ``ciceroscm.input_handler.read_natural_emissions`` requires the
    file row count to match ``endyear - startyear + 1`` exactly and
    defaults to ``endyear=2500``. Marit's bundled files cover
    1750-2022 (273 rows), so we count rows and pass an explicit
    ``endyear`` to avoid the size-mismatch error.
    """
    from ciceroscm import input_handler

    with open(path) as fh:
        n_rows = sum(1 for _ in fh)
    file_endyear = nystart + n_rows - 1
    return input_handler.read_natural_emissions(
        path, component, startyear=nystart, endyear=file_endyear
    )


def _flatten_natemis_to_preindustrial(natemis_df, anchor_year: int = 1750):
    """Hold natural emissions constant at the pre-industrial value.

    For RCMIP3 idealised scenarios (esm-flat*, esm-bell*, esm-pi-*,
    esm-1pct-*, 1pctCO2*, abrupt-*) the protocol prescribes constant
    pre-industrial non-CO2 forcing. The bundled natemis_CH4/_N2O
    files carry a historical trajectory through 2022 then jump
    discontinuously to a flat 2024+ value (252 -> 280.65 Tg/yr for
    CH4); both the historical drift and the jump pollute the
    idealised diagnostics. This helper returns a copy of the natemis
    DataFrame with every row replaced by the ``anchor_year`` (1750)
    value, so CICERO sees a true pre-industrial natural-emissions
    baseline for the whole 1750-2500 window.
    """
    if anchor_year not in natemis_df.index:
        anchor_year = int(natemis_df.index.min())
    pi_row = natemis_df.loc[anchor_year]
    flat = natemis_df.copy()
    for col in flat.columns:
        flat[col] = pi_row[col]
    return flat


def _cicero_unit_to_pint(cicero_unit_raw: str, cicero_species: str) -> str:
    """
    Translate a CICERO gaspam EM_UNIT token to an openscm-units string.

    Mirrors :meth:`COMMONSFILEWRITER.initialize_units_comps` (the
    v1.1.x adapter's shared helper) so the same per-yr unit strings
    are used for conversion.

    - ``"Pg_C"``  -> ``"PgC / yr"``  (and the CO2 / CO2_lu species
      both use this; openscm-units handles the carbon-mass-vs-CO2
      conversion via the carbon context)
    - ``"Tg_N"`` for N2O is the AR-specific N2ON convention -> ``"TgN2ON / yr"``
    - ``"Tg_SO2"``, ``"Tg_C"`` etc. -> just strip the underscore
    - ``"Tg"`` / ``"Mt"`` / ``"Gg"`` with no underscore -> append the
      species name (e.g. ``"Gg"`` for ``HFC125`` -> ``"GgHFC125 / yr"``)
    """
    if cicero_species == "N2O" and cicero_unit_raw == "Tg_N":
        return "TgN2ON / yr"
    if "_" in cicero_unit_raw:
        return cicero_unit_raw.replace("_", "") + " / yr"
    comp_str = cicero_species.replace("-", "").replace("BMB_AEROS_", "")
    return f"{cicero_unit_raw}{comp_str} / yr"


def _build_hybrid_emissions_data(  # noqa: PLR0913
    scenarios,
    scenario_name: str,
    bundle_dir: str,
    gases_ep: str,
    nystart: int,
    nyend: int,
    emstart: int,
):
    """
    Build a CICERO-format emissions DataFrame for a novel scenario.

    Bundle mode normally picks `{scen}_em_{gases_ep}` from the bundle
    directly. When a user passes a ScmRun for a scenario that has no
    such bundle file (e.g. an AR7 IAM output), this helper overlays
    the user's emissions on top of the bundle's ``historical_em``
    instead, mapping openscm-runner variable names to CICERO species
    via :data:`cicero_comp_dict` (the same mapping the v1.1.x
    SCENARIODATAGETTER uses) and converting units through
    openscm-units.

    Returns a DataFrame indexed by year (``nystart`` to ``nyend``)
    with CICERO species as columns, suitable for passing through to
    CICERO via the ``emissions_data`` scendata key. Species the user
    doesn't supply stay at the bundle's historical value (held forward
    past the historical file's extent, since the bundle's
    ``historical_em`` already extends to 2500 with last-value-forward
    constant filling, this is effectively the bundle author's
    decision).
    """
    import pandas as pd
    from openscm_units import unit_registry as ureg

    from ..utils.cicero_utils.make_scenario_common import cicero_comp_dict

    hist_path = os.path.join(bundle_dir, f"historical_em_{gases_ep}")

    # Read the file. Same parsing the v1.1.x _read_ssp245_em uses
    # (4 header rows, tab delim, strip column-name whitespace, rename
    # the duplicate CO2 columns to FFI / AFOLU).
    df = (
        pd.read_csv(
            hist_path, delimiter="\t", index_col=0, skiprows=[1, 2, 3]
        )
        .rename(columns=lambda x: x.strip())
        .astype(float)
    )
    df.index = df.index.astype(int)
    # After strip(), the second CO2 column comes through as
    # "CO2 .1" (internal space + pandas-disambiguating ".1") because
    # the original header is " CO2 \t CO2 \t CH4 ..." - lambda strip
    # only removes leading / trailing whitespace. Match both forms.
    df.columns = [
        "CO2_FF" if c == "CO2"
        else "CO2_AFOLU" if c in ("CO2.1", "CO2 .1")
        else c
        for c in df.columns
    ]

    # Pull per-column units from the file's "Unit" header (row 2).
    with open(hist_path) as fh:
        _ = next(fh)  # Component row (we already have columns)
        unit_line = next(fh)
    unit_tokens = [t.strip() for t in unit_line.rstrip("\n").split("\t")]
    column_units = dict(zip(df.columns, unit_tokens[1:]))

    df = df.loc[nystart:nyend].copy()

    user_filtered = scenarios.filter(scenario=scenario_name)
    if user_filtered.empty:
        return df

    user_ts = user_filtered.timeseries(time_axis="year")
    user_ts.columns = user_ts.columns.astype(int)

    # Map CICERO short names in cicero_comp_dict to the renamed
    # columns in df (CO2 / CO2_lu -> CO2_FF / CO2_AFOLU).
    cicero_to_df_col = {"CO2": "CO2_FF", "CO2_lu": "CO2_AFOLU"}

    overlaid: list[str] = []
    skipped_unmapped: list[str] = []
    for cicero_species, (openscm_suffix, factor) in cicero_comp_dict.items():
        col = cicero_to_df_col.get(cicero_species, cicero_species)
        if col not in df.columns:
            continue
        user_var = f"Emissions|{openscm_suffix}"
        mask = user_ts.index.get_level_values("variable") == user_var
        if not mask.any():
            continue
        user_row = user_ts[mask].iloc[0]
        user_unit = user_ts[mask].index.get_level_values("unit")[0]
        cicero_unit_pint = _cicero_unit_to_pint(
            column_units[col], cicero_species
        )
        # Some species need a unit-conversion context (NOx mass-N vs
        # mass-NO2; NH3 mass-N vs mass-NH3). openscm-units exposes
        # these via ScmRun.convert_unit's `context` kwarg; for raw
        # pint we activate the same registry context manager.
        contexts = {"NOx": "NOx_conversions", "NH3": "NH3_conversions"}
        ctx = contexts.get(cicero_species)
        try:
            if ctx is not None:
                with ureg.context(ctx):
                    convfactor = (
                        (1.0 * ureg(user_unit))
                        .to(cicero_unit_pint)
                        .magnitude
                        * factor
                    )
            else:
                convfactor = (
                    (1.0 * ureg(user_unit)).to(cicero_unit_pint).magnitude
                    * factor
                )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.warning(
                "CICEROSCMPY2 hybrid: skipping species %s (unit "
                "conversion %s -> %s failed: %s)",
                cicero_species, user_unit, cicero_unit_pint, exc,
            )
            skipped_unmapped.append(cicero_species)
            continue
        for year, val in user_row.items():
            if (
                year in df.index
                and year >= emstart
                and not pd.isna(val)
            ):
                df.at[year, col] = val * convfactor
        overlaid.append(cicero_species)

    LOGGER.info(
        "CICEROSCMPY2 hybrid emissions for scenario %r: overlaid "
        "%d species from user ScmRun (%s); %d skipped on unit "
        "errors (%s); others use bundle historical_em.",
        scenario_name, len(overlaid), overlaid,
        len(skipped_unmapped), skipped_unmapped,
    )

    return df


def _auto_conc_run(scenario_name: str) -> bool:
    """
    Auto-detect whether ``scenario_name`` should run concentration-driven.

    Mirrors ``run_full_rcmip_protocol.py``: scenarios starting with
    ``esm-`` or ``methanemip`` are emissions-driven; everything else
    (ssp*, scen7-*, 1pctCO2*, abrupt*, hist-*, historical*, piControl)
    is concentration-driven.

    Legacy name-pattern fallback used by :func:`_resolve_protocol_spec`
    when the input ScmRun lacks the ``protocol_mode`` meta column.
    New code should prefer reading that column directly.
    """
    s = scenario_name.lower()
    return not (s.startswith("esm-") or s.startswith("esm_") or
                s.startswith("methanemip"))


def _is_idealised(scenario_name: str) -> bool:
    """
    True for RCMIP3 idealised experiments that prescribe constant
    pre-industrial natural forcing.

    Covers the ``esm-flat*`` constant-emissions family, the
    ``esm-bell*`` and ``esm-pi-*`` impulse-response experiments, and
    the ``1pctCO2*`` / ``abrupt*`` concentration-driven idealised
    runs.

    Legacy name-pattern fallback used by :func:`_resolve_protocol_spec`
    when the input ScmRun lacks the ``protocol_natural_forcing`` /
    ``protocol_land_use_forcing`` meta columns. New code should prefer
    reading those columns directly.
    """
    s = scenario_name.lower()
    return (
        s.startswith("esm-flat") or s.startswith("esm-bell")
        or s.startswith("esm-pi-") or s.startswith("esm-1pct")
        or s.startswith("1pctco2") or s.startswith("abrupt")
    )


def _resolve_protocol_spec(
    scenario_run, scenario_name: str,
) -> dict[str, str]:
    """Return per-scenario protocol metadata used by the scendata builder.

    Result has three keys:

    * ``mode`` — one of ``"CD"``, ``"ED-CO2-only"``, ``"ED-all-GHG"``.
      Drives ``conc_run`` and the bulk of ``emstart`` selection.
    * ``natural_forcing`` — ``"on"`` or ``"off"``. Drives ``sunvolc``,
      the natemis CH4 / N2O flatten step, and the idealised branch of
      ``emstart`` for ED scenarios.
    * ``land_use_forcing`` — ``"historical"`` or ``"constant_zero"``.
      Drives the LUC albedo fallback chain (``constant_zero`` adds
      ``LUCalbedo_RCMIP_constant_zero_RCMIP3.txt`` to the fallbacks).

    Reads the loader's protocol meta columns when present on
    ``scenario_run``; falls back to the legacy name-pattern helpers
    :func:`_auto_conc_run` and :func:`_is_idealised` for ScmRuns
    constructed outside :func:`openscm_runner.scenarios.load_rcmip3_*`.
    """
    meta = getattr(scenario_run, "meta", None)
    have_meta = (
        meta is not None
        and "protocol_mode" in meta.columns
        and "protocol_natural_forcing" in meta.columns
        and "protocol_land_use_forcing" in meta.columns
    )
    if have_meta:
        sub = meta[meta["scenario"].astype(str) == scenario_name]
        if not sub.empty:
            return {
                "mode": str(sub["protocol_mode"].iloc[0]),
                "natural_forcing": str(sub["protocol_natural_forcing"].iloc[0]),
                "land_use_forcing": str(sub["protocol_land_use_forcing"].iloc[0]),
            }
    # Name-pattern fallback. Note: the legacy helpers tie natural and
    # land-use together; callers handed a metadata-free ScmRun won't
    # benefit from the independent control the meta cols allow.
    s = scenario_name.lower()
    if _auto_conc_run(scenario_name):
        mode = "CD"
    elif s.startswith(("esm-allghg", "esm_allghg")):
        mode = "ED-all-GHG"
    else:
        mode = "ED-CO2-only"
    idealised = _is_idealised(scenario_name)
    return {
        "mode": mode,
        "natural_forcing": "off" if idealised else "on",
        "land_use_forcing": "constant_zero" if idealised else "historical",
    }


def _build_scendata_list_bundle(  # noqa: PLR0912, PLR0915
    scenarios, cfg: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Bundle-mode scendata builder (Marit's RCMIP setup).

    For each scenario in ``scenarios`` (or just "historical" if none
    given), picks ``{scen}_em_{gases_ep}``, ``{scen}_conc_{gases_ep}``,
    and ``solar/VOLC/LUCalbedo_RCMIP_{scen}_RCMIP3.txt`` from the
    bundle; falls back to ``historical_em_…`` / ``historical_conc_…``
    / ``…_RCMIP_historical_RCMIP3.txt`` when scenario-specific files
    don't exist. Natural CH4/N2O are loaded as DataFrames (the upstream
    file reader requires exact row-count matching, which we handle).

    Bypasses the v1.1.x SCENARIODATAGETTER splice entirely; the
    bundle's scenario emissions file is the source of truth.
    """
    bundle_dir = cfg["cicero_bundle_dir"]
    if not os.path.isdir(bundle_dir):
        raise FileNotFoundError(
            f"cicero_bundle_dir does not exist or is not a directory: "
            f"{bundle_dir}"
        )

    gases_ep = cfg.get("cicero_gases_ep", _DEFAULT_GASES_EP)
    gaspam_file = cfg.get("gaspam_file", os.path.join(bundle_dir, gases_ep))
    if not os.path.exists(gaspam_file):
        raise FileNotFoundError(
            f"CICEROSCMPY2 bundle mode: gaspam_file not found at "
            f"{gaspam_file}. Pass cicero_gases_ep or gaspam_file to "
            "override."
        )

    nystart = int(cfg.get("nystart", 1750))
    if scenarios is not None and not scenarios.empty:
        scenario_years = scenarios.time_points.years()
        nyend = int(cfg.get("nyend", max(scenario_years)))
        scenario_names = sorted(set(scenarios["scenario"]))
    else:
        nyend = int(cfg.get("nyend", 2100))
        scenario_names = ["historical"]
    # sunvolc default is "on for non-idealised, off for idealised";
    # explicit cfg value overrides for both. Resolved per-scenario
    # below so a mixed scenario list (e.g. SSP + esm-flat*) gets
    # the right treatment for each.
    sunvolc_cfg = cfg.get("sunvolc")

    # Preload natural emissions DataFrames (avoids the read-time
    # row-count-mismatch error in upstream's default endyear=2500).
    nat_ch4_path = cfg.get(
        "nat_ch4_file", os.path.join(bundle_dir, _DEFAULT_NATEMIS_CH4)
    )
    nat_n2o_path = cfg.get(
        "nat_n2o_file", os.path.join(bundle_dir, _DEFAULT_NATEMIS_N2O)
    )
    nat_ch4_df = _load_natemis_dataframe(nat_ch4_path, "CH4", nystart)
    nat_n2o_df = _load_natemis_dataframe(nat_n2o_path, "N2O", nystart)

    scendata_list: list[dict[str, Any]] = []
    for scenario_name in scenario_names:
        # Per-scenario protocol metadata (loader meta cols or
        # name-pattern fallback). Drives conc_run / emstart / sunvolc /
        # LUC fallback / natemis flatten without further name parsing.
        spec = _resolve_protocol_spec(scenarios, scenario_name)
        natural_off = spec["natural_forcing"] == "off"
        lu_zero = spec["land_use_forcing"] == "constant_zero"

        # Emissions resolution. Order of precedence:
        #   1. Explicit cfg["emissions_file"] override
        #   2. Bundle's own `{scen}_em_{gases_ep}` (canonical RCMIP scenario)
        #   3. User ScmRun for this scenario, spliced onto bundle's
        #      `historical_em` -> "hybrid mode" for novel / IAM-output
        #      scenarios with no bundle file
        #   4. `historical_em` as a last-resort fallback (constant
        #      after the historical end year)
        explicit_conc_run = cfg.get("cicero_conc_run")
        if explicit_conc_run is None:
            conc_run = spec["mode"] == "CD"
        else:
            conc_run = bool(explicit_conc_run)

        # emstart selection: every ED variant runs 1750-1849 conc-driven
        # against the bundle's stripped conc trajectory (near-PI for the
        # CMIP6 SSPs / scen7 markers; constant_zero proxy for the
        # idealised experiments), then the bundle's _em_ file (or the
        # loader's ScmRun via hybrid mode) drives 1850 onwards. CD runs
        # set emstart=nyend so emissions never take over.
        if "emstart" in cfg:
            scen_emstart = int(cfg["emstart"])
        elif conc_run:
            scen_emstart = nyend
        else:
            scen_emstart = 1850

        # Bundle file resolution. The bundle uses bare scenario names,
        # so esm-ssp245 / esm-allGHG-ssp245 / scen7-HC all need
        # prefix/suffix stripping to land on the right ssp245_*,
        # scen7-H_* files. See _bundle_basename_candidates.
        em_override = cfg.get("emissions_file")
        basenames = _bundle_basename_candidates(scenario_name)
        em_candidates = [f"{b}_em_{gases_ep}" for b in basenames]
        em_bundle_match = _find_bundle_file(bundle_dir, em_candidates)

        em_bundle_is_stripped = (
            em_bundle_match is not None
            and os.path.basename(em_bundle_match) != em_candidates[0]
        )

        # Idealised scenarios (natural=off + LU=constant_zero, e.g.
        # 1pctCO2, abrupt-*, piControl) want PI-flat anthropogenic
        # emissions everywhere so CICEROSCM's calc_aerosol_forcing
        # (concentrations_emissions_handler.py:584) — which computes
        # ``q = (emis[yr] - emis[1750]) * ALPHA`` for each aerosol
        # tracer regardless of conc_run mode — produces zero aerosol
        # perturbation. Without this, the default fallback to
        # historical_em_ leaks historical SO2 / BC / OC / NOx / NH3 /
        # NMVOC / CH4 into the idealised runs and breaks the "only CO2
        # varies" protocol invariant. This is the fourth member of the
        # idealised-suppression set: sunvolc=0, natemis flatten,
        # LUC=constant_zero, and now PI-flat emissions.
        #
        # Scenarios that ship a scenario-specific _em_ file (esm-flat*,
        # esm-bell-*, esm-pi-*, esm-piControl) hit the exact-name match
        # above; their files are CO2-only by construction so aerosols
        # are already PI-flat. The fix only affects scenarios that
        # would otherwise fall through to the historical_em_ fallback
        # (1pctCO2*, abrupt-*, piControl, the bundle-only esm-1pct-brch-*).
        idealised = natural_off and lu_zero
        em_fallback_chain = (
            [f"esm-piControl_em_{gases_ep}", f"historical_em_{gases_ep}"]
            if idealised else [f"historical_em_{gases_ep}"]
        )

        # Detect protocol-strict mixed-mode input from the loader: the
        # presence of Atmospheric Concentrations|* rows for this
        # scenario means the loader is supplying ED CO2-only inputs
        # (CO2 from emissions + non-CO2 from concentrations) — see
        # openscm_runner.scenarios.rcmip3._load_mixed_mode_scenario.
        # CICEROSCM v2's conc_run is all-or-nothing per scenario
        # (concentrations_emissions_handler.py guards on a single
        # pamset flag, no per-species toggle), so we cannot honor the
        # protocol-strict mode here. Fall back to the bundle's
        # bare-name _em_ file via stripping, running full all-GHG ED.
        # This matches Marit's published reference (her esm-ssp245
        # and esm-allGHG-ssp245 are bit-identical for the same upstream
        # reason — proper mixed mode awaits a CICEROSCM v2 patch).
        loader_supplied_concentrations = (
            scenarios is not None and not scenarios.empty
            and not scenarios.filter(
                scenario=scenario_name,
                variable="Atmospheric Concentrations|*",
            ).empty
        )
        if loader_supplied_concentrations:
            LOGGER.info(
                "CICEROSCMPY2 bundle mode: scenario %r supplies "
                "Atmospheric Concentrations rows (protocol-strict ED "
                "CO2-only); CICEROSCM v2 cannot run per-species mixed "
                "mode, falling back to bundle's full all-GHG _em_ file "
                "(matches Marit's published reference).",
                scenario_name,
            )

        # ED-CO2-only scenarios share their bundle file with the bare
        # variant (e.g. esm-ssp245 strips to ssp245_em_). For scenarios
        # where the loader supplies mixed-mode inputs we want CICERO to
        # use the bundle's full all-GHG file directly (per the
        # CICEROSCM-v2 fallback above); for everything else we still
        # prefer hybrid mode so the loader's ScmRun drives the run.
        prefer_hybrid_for_co2_only = (
            spec["mode"] == "ED-CO2-only"
            and em_bundle_is_stripped
            and not loader_supplied_concentrations
        )

        # For idealised scenarios, suppress hybrid mode entirely. The
        # loader stub (or any user ScmRun) would splice onto
        # historical_em inside _build_hybrid_emissions_data, exactly
        # the historical-aerosol leak the em_fallback_chain above is
        # designed to avoid. Use the PI-flat fallback chain directly.
        use_hybrid = (
            em_override is None
            and (em_bundle_match is None or prefer_hybrid_for_co2_only)
            and not idealised
            and scenarios is not None
            and not scenarios.empty
            and scenario_name in set(scenarios["scenario"])
        )
        em_path = None
        em_data = None
        if em_override is not None:
            em_path = em_override
        elif use_hybrid:
            em_data = _build_hybrid_emissions_data(
                scenarios=scenarios,
                scenario_name=scenario_name,
                bundle_dir=bundle_dir,
                gases_ep=gases_ep,
                nystart=nystart,
                nyend=nyend,
                emstart=scen_emstart,
            )
            LOGGER.info(
                "CICEROSCMPY2 bundle mode: scenario %r driven via hybrid "
                "emissions DataFrame (loader ScmRun overlaid on "
                "historical_em_%s)%s.",
                scenario_name,
                gases_ep,
                " — preferred over stripped bundle file for ED-CO2-only"
                if prefer_hybrid_for_co2_only else "",
            )
        else:
            em_path = em_bundle_match or _pick_bundle_file(
                bundle_dir, em_fallback_chain,
            )
            if (
                idealised
                and em_bundle_match is None
                and os.path.basename(em_path) != em_fallback_chain[0]
            ):
                LOGGER.warning(
                    "CICEROSCMPY2 bundle mode: idealised scenario %r has "
                    "no scenario-specific _em_ file and the preferred "
                    "PI-flat fallback %s is missing from the bundle; "
                    "using %s instead. Aerosol forcing will track "
                    "historical anthropogenic precursors via "
                    "calc_aerosol_forcing — the 'only CO2 varies' "
                    "protocol invariant is violated.",
                    scenario_name,
                    em_fallback_chain[0],
                    os.path.basename(em_path),
                )
        conc_candidates = (
            [f"{b}_conc_{gases_ep}" for b in basenames]
            + [f"historical_conc_{gases_ep}"]
        )
        conc_path = cfg.get("concentrations_file") or _pick_bundle_file(
            bundle_dir, conc_candidates,
        )
        # Solar / volcanic / LUC files in the bundle have per-scenario
        # variants for the CMIP6 SSPs (ssp245, ...) and the CMIP7 scen7
        # markers (scen7-H, ...), but not for the esm-* / esm-allGHG-*
        # / scen7-*C variants. Apply the same prefix/suffix stripping
        # we use for the _em_ / _conc_ files (step 5b) so e.g.
        # esm-ssp245 picks up solar_RCMIP_ssp245_RCMIP3.txt rather than
        # falling through to solar_RCMIP_historical_RCMIP3.txt — which
        # forward-fills at 2023 and was the root cause of the post-2023
        # +0.2-0.5 K bias against Marit on the esm-ssp* family.
        forcing_basenames = [b for b in basenames]
        sun_path = cfg.get("rf_solar_file") or _pick_bundle_file(
            bundle_dir,
            [f"solar_RCMIP_{b}_RCMIP3.txt" for b in forcing_basenames]
            + ["solar_RCMIP_historical_RCMIP3.txt"],
        )
        volc_path = cfg.get("rf_volc_file") or _pick_bundle_file(
            bundle_dir,
            [f"VOLC_RCMIP_{b}_RCMIP3.txt" for b in forcing_basenames]
            + ["VOLC_RCMIP_historical_RCMIP3.txt"],
        )
        # When protocol_land_use_forcing == "constant_zero" (idealised
        # experiments + piControl variants), prefer the bundle's
        # ``LUCalbedo_RCMIP_constant_zero_RCMIP3.txt``. The historical
        # LUC albedo file accumulates ~-0.2 W/m² of cooling forcing
        # through 2022 then snaps back to 0 at 2023, producing both a
        # +0.2 W/m² warming jump (~15 mK uptick at 2024 in GSAT) and a
        # persistent ~0.12 K bias on the active emissions period.
        luc_scenario_candidates = [
            f"LUCalbedo_RCMIP_{b}_RCMIP3.txt" for b in forcing_basenames
        ]
        if lu_zero:
            luc_fallbacks = (
                luc_scenario_candidates
                + ["LUCalbedo_RCMIP_constant_zero_RCMIP3.txt",
                   "LUCalbedo_RCMIP_historical_RCMIP3.txt"]
            )
        else:
            luc_fallbacks = (
                luc_scenario_candidates
                + ["LUCalbedo_RCMIP_historical_RCMIP3.txt"]
            )
        luc_path = cfg.get("rf_luc_file") or _pick_bundle_file(
            bundle_dir, luc_fallbacks,
        )
        # protocol_natural_forcing == "off" -> hold solar/volcanic at
        # pre-industrial (sunvolc=0) and flatten the natural CH4 / N2O
        # emissions tables to their 1750 PI value (otherwise the
        # historical natemis trajectory + 2023 discontinuity contaminates
        # ZEC and piControl diagnostics). Explicit cfg["sunvolc"]
        # overrides the metadata-driven default for both.
        if sunvolc_cfg is not None:
            scen_sunvolc = int(sunvolc_cfg)
        else:
            scen_sunvolc = 0 if natural_off else 1
        if natural_off:
            scen_nat_ch4 = _flatten_natemis_to_preindustrial(nat_ch4_df)
            scen_nat_n2o = _flatten_natemis_to_preindustrial(nat_n2o_df)
        else:
            scen_nat_ch4 = nat_ch4_df
            scen_nat_n2o = nat_n2o_df
        scendata: dict[str, Any] = {
            "nystart": nystart,
            "nyend": nyend,
            "emstart": scen_emstart,
            "sunvolc": scen_sunvolc,
            "conc_run": conc_run,
            "idtm": 24,
            "scenname": scenario_name,
            "gaspam_file": gaspam_file,
            "concentrations_file": conc_path,
            "rf_solar_file": sun_path,
            "rf_volc_file": volc_path,
            "rf_luc_file": luc_path,
            "nat_ch4_data": scen_nat_ch4.loc[
                : min(nyend, scen_nat_ch4.index.max())
            ],
            "nat_n2o_data": scen_nat_n2o.loc[
                : min(nyend, scen_nat_n2o.index.max())
            ],
        }
        # CICERO's InputHandler accepts either `emissions_file` (path)
        # or `emissions_data` (in-memory DataFrame). Hybrid mode produces
        # the DataFrame directly to avoid writing a temp file.
        if em_data is not None:
            scendata["emissions_data"] = em_data
        else:
            scendata["emissions_file"] = em_path
        LOGGER.debug(
            "CICEROSCMPY2 bundle scendata for scenario=%s years=%d-%d "
            "(emstart=%d, conc_run=%s) em=%s conc=%s",
            scenario_name,
            nystart,
            nyend,
            scen_emstart,
            conc_run,
            "<hybrid-DataFrame>" if em_path is None else os.path.basename(em_path),
            os.path.basename(conc_path),
        )
        scendata_list.append(scendata)

    return scendata_list
