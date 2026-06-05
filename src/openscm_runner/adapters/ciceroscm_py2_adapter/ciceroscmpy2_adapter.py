"""
Adapter for CICERO-SCM v2.x (DistributionRun mode, scenarios-driven).

Sibling of :class:`openscm_runner.adapters.ciceroscm_py_adapter.CICEROSCMPY`
(which wraps the v1.1.x release with a per-config loop). This adapter
targets the AR7-relevant v2.1.0 release and its native
``DistributionRun`` ensemble API.

**API shape: scenarios DataFrame is authoritative**

The adapter follows the same surface as :class:`FAIR2`: the caller
supplies a scenarios :class:`scmdata.ScmRun` carrying ``Emissions|*``
rows (ED) or ``Atmospheric Concentrations|*`` rows (CD), and the
adapter overlays them on a calibration directory of static defaults
(gaspam, historical_em / historical_conc baselines, default natural
emissions, default solar / volcanic / LUC forcings, parameter
posterior JSON). No per-scenario file lookups happen inside the
adapter; per-scenario inputs come from the scenarios DataFrame.

Reproducing a published reference (e.g. Marit's RCMIP runs) is the
application layer's job: translate the reference scenarios into
openscm-runner format on the application side (the fork's
``scripts/translate_cicero_bundle_to_iamc.py`` does this for the
``cscm-calibrate`` ``rcmip-march2026`` bundle), then drive the
adapter from the translated DataFrame. The adapter stays dumb; the
application repo decides what to feed it.

**Constructing the adapter**

The recommended path is :meth:`CICEROSCMPY2.from_native_distribution`,
which takes a calibration directory laid out like
``cscm-calibrate@ben_rcmip_sandbox`` (gaspam + historical_em +
historical_conc + natemis + default forcings + the parameter
posterior JSON, with canonical filename patterns). It resolves
each canonical file by glob, writes a single cfg with explicit
paths, and instantiates the adapter::

    from openscm_runner import RunMode
    from openscm_runner.adapters import CICEROSCMPY2

    adapter = CICEROSCMPY2.from_native_distribution(
        "/path/to/marit-rcmip-march2026/",
        mode=RunMode.EMISSIONS_DRIVEN,
        member_indices=range(500),
        output_variables=("Surface Air Temperature Change", ...),
    )
    result = adapter.run(scenarios)

Direct cfg construction via ``CICEROSCMPY2(cfgs=[...], mode=...)``
is also supported; the cfg dict must carry the required sidecar
keys listed below.

**Required cfg sidecar keys**

- ``distribution_json`` (path): parameter posterior JSON readable by
  :class:`ciceroscm.parallel.distributionrun.DistributionRun`. Either
  a flat list of cfg dicts or a
  ``{"meta_info": ..., "configurations": [...]}`` envelope.
- ``gaspam_file`` (path): species-properties file
  (``EM_UNIT``, ``CONC_UNIT``, ``BETA``, ``TAU*``, ``NAT_EM``).
  Must match the species set the ``distribution_json`` posterior
  was calibrated against.
- ``historical_em_file`` (path): RCMIP-format historical emissions
  baseline. Provides the species-column coverage and pre-1850 values
  that the user's ``Emissions|*`` overlay extends.
- ``historical_conc_file`` (path): RCMIP-format historical
  concentrations baseline. Same role for the CD path; also provides
  the pre-industrial concentration values CICEROSCM needs to seed
  the concentration solver in ED mode.
- ``nat_ch4_file`` / ``nat_n2o_file`` (paths): natural CH4 / N2O
  emissions trajectories.
- ``rf_sun_file`` / ``rf_volc_file`` / ``rf_luc_file`` (paths):
  default solar / volcanic / LUC albedo forcing files. Note the
  solar key is ``rf_sun_file`` (matching upstream ``ciceroscm`` v2.x's
  ``InputHandler``), not ``rf_solar_file``.

**Optional cfg sidecar keys**

- ``rf_luc_constant_zero_file`` (path): used in place of
  ``rf_luc_file`` for scenarios whose
  ``protocol_land_use_forcing == "constant_zero"`` meta column is
  set. Without this key, idealised scenarios fall back to the
  historical LUC file with a warning.
- ``member_indices`` (sequence of int): zero-based row indices into
  the parameter posterior. Defaults to all members.
- ``max_workers`` (int): forwarded to
  ``DistributionRun.run_over_distribution``. Defaults to
  :func:`openscm_runner.settings.get_worker_count` capped at the
  total number of scheduled jobs (members x scenarios).
- ``nystart`` / ``nyend`` / ``emstart`` (int): time bounds. Defaults:
  ``nystart=1750``, ``nyend=max(scenarios time)``,
  ``emstart=nyend`` in CD mode (so emissions never take over) and
  ``emstart=1850`` in ED mode.
- ``sunvolc`` (int): per-cfg override for the
  ``protocol_natural_forcing`` driven default
  (``0`` for ``off``, ``1`` for ``on``).
- ``idtm`` (int): integration timestep. Default ``24``.

**Protocol metadata (per-scenario)**

When the scenarios ScmRun carries ``protocol_natural_forcing`` and
``protocol_land_use_forcing`` meta columns (the RCMIP3 loader sets
these), per-scenario natural-forcing and LUC handling is driven by
them: ``natural_forcing == "off"`` flattens the natural CH4 / N2O
trajectories to their 1750 value and zeros ``sunvolc``;
``land_use_forcing == "constant_zero"`` substitutes
``rf_luc_constant_zero_file`` for ``rf_luc_file`` (or warns if not
available). When the meta columns are absent, the defaults are
``natural_forcing="on"`` and ``land_use_forcing="historical"`` (no
idealised treatment); idealised users should set those meta columns
on their ScmRun or override at the cfg level.

**Driving mode (per-adapter)**

The adapter-level :class:`~openscm_runner.RunMode` (set via the
``mode=`` constructor argument or ``CICEROSCMPY2.from_native_distribution(
mode=...)``) is authoritative for ``conc_run`` and applies uniformly
to every scenario in the call. The per-cfg ``cicero_conc_run``
internal flag is derived from this; users should not set it
directly.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
from scmdata import ScmRun, run_append

from ..._run_mode import RunMode
from ...settings import config
from ..base import _Adapter
from ._compat import HAS_CICEROSCM_PY2, cscmpy2, require_modern_ciceroscm

try:
    from ...settings import get_worker_count
except ImportError:  # pragma: no cover
    def get_worker_count(override_env_var: str | None = None) -> int:
        """Fallback worker-count lookup (override env var > cpu_count)."""
        if override_env_var and (val := config.get(override_env_var, None)):
            return max(int(val), 1)
        return max(os.cpu_count() or 1, 1)


LOGGER = logging.getLogger(__name__)


# Translate openscm-runner ``Atmospheric Concentrations|{species}``
# names to the CICERO-SCM species labels (mostly identical apart from
# hyphens in halocarbon names). Used by
# :func:`_build_hybrid_concentrations_data` to overlay user-supplied
# concentrations on the bundle's ``historical_conc`` baseline.
_OPENSCM_TO_CICERO_CONC = {
    "CFC11": "CFC-11",
    "CFC12": "CFC-12",
    "CFC113": "CFC-113",
    "CFC114": "CFC-114",
    "CFC115": "CFC-115",
    "HCFC22": "HCFC-22",
    "HCFC141b": "HCFC-141b",
    "HCFC142b": "HCFC-142b",
    "Halon1211": "H-1211",
    "Halon1301": "H-1301",
    "Halon2402": "H-2402",
}


# Canonical filenames inside a CICEROSCM v2.x calibration directory,
# tied to the v2024 WMO-added-new gaspam endpoint. These are the
# defaults :meth:`CICEROSCMPY2.from_native_distribution` looks for;
# every one is overridable via a cfg keyword to the classmethod. The
# defaults match Marit's ``cscm-calibrate@ben_rcmip_sandbox``
# ``rcmip-march2026`` layout; Zenodo-published bundles for AR7 use
# follow the same convention.
_DEFAULT_CANONICAL_FILES: dict[str, str] = {
    "gaspam_file": "gases_vupdate_2024_WMO_added_new.txt",
    # historical_em / historical_conc files anchor the CICERO species
    # column structure + units; the actual scenario time series are
    # overlaid on top from the canonical RCMIP3 bundle merge.
    "historical_em_file": (
        "historical_em_gases_vupdate_2024_WMO_added_new.txt"
    ),
    "historical_conc_file": (
        "historical_conc_gases_vupdate_2024_WMO_added_new.txt"
    ),
    "nat_ch4_file": (
        "natemis_CH4_ode_method_from_March2026_vupdate_2024_WMO_added_new.txt"
    ),
    "nat_n2o_file": (
        "natemis_N2O_ode_method_from_March2026_vupdate_2024_WMO_added_new.txt"
    ),
}
# Idealised LUC handling for CICEROSCM mirrors FaIR's runtime approach
# (see fair2_adapter._fill_natural_forcings): the calibration bundle
# ships ONE LUC file (the historical+projection trajectory), and the
# adapter builds an in-memory zeros DataFrame at run time for any
# scenario whose ``protocol_land_use_forcing`` metadata is
# ``"constant_zero"``. No alternate bundle file is needed.


class CICEROSCMPY2(_Adapter):
    """
    Adapter for CICERO-SCM v2.x with a parameter-distribution JSON.

    Registered under ``model_name = "CICERO-SCM-PY2"`` (distinct from
    the existing ``"CICERO-SCM-PY"`` which wraps v1.1.x).

    See module docstring for the supported cfg sidecar keys and
    construction patterns.
    """

    model_name = "CICERO-SCM-PY2"
    supported_modes = frozenset(
        {RunMode.EMISSIONS_DRIVEN, RunMode.CONCENTRATION_DRIVEN}
    )

    def _init_model(self):
        require_modern_ciceroscm()

    def _run(self, scenarios, cfgs, output_variables, output_config):
        if output_config is not None:
            raise NotImplementedError(
                "`output_config` not implemented for CICEROSCMPY2"
            )

        from ._output_variables import validate_output_variables
        validate_output_variables(output_variables)

        from ._output_variables import (
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

        required = (
            "distribution_json",
            "gaspam_file",
            "historical_em_file",
            "historical_conc_file",
            "nat_ch4_file",
            "nat_n2o_file",
            "rcmip3_bundle_path",
        )
        for cfg_index, cfg in enumerate(cfgs):
            missing = [k for k in required if k not in cfg]
            if missing:
                raise ValueError(
                    f"CICEROSCMPY2 cfg {cfg_index} is missing required "
                    f"sidecar keys: {missing}. The supported construction "
                    "path is CICEROSCMPY2.from_native_distribution("
                    "calibration_dir), which auto-resolves these from "
                    "canonical filenames inside the calibration directory; "
                    "see the module docstring for the file patterns. "
                    "Power users may set each key explicitly."
                )

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
        calibration_dir,
        rcmip3_bundle_path,
        *,
        mode: RunMode = RunMode.EMISSIONS_DRIVEN,
        distribution_json=None,
        member_indices=None,
        output_variables=None,
        output_config=None,
        max_workers: int | None = None,
    ) -> "CICEROSCMPY2":
        """
        Construct from a CICERO-SCM 2.x calibration directory + canonical RCMIP3.

        The two arguments correspond to two distinct data sources that
        used to be conflated:

        * ``calibration_dir`` -- model-specific calibration only.
          Carries the gaspam (species properties), the natural CH4 /
          N2O emissions baselines, and the parameter posterior JSON.
          These have no canonical RCMIP3 equivalent.
        * ``rcmip3_bundle_path`` -- protocol/scenario inputs from the
          canonical RCMIP Phase 3 Zenodo bundle (record 20430630):
          per-scenario emissions, concentrations, solar, volcanic and
          land-use albedo forcings. The adapter loads them via
          :mod:`openscm_runner.io.rcmip3`.

        Per-scenario emissions / concentration files inside
        ``calibration_dir`` (e.g. ``{scen}_em_*``, ``{scen}_conc_*``)
        are NOT read; the scenarios ScmRun passed to :meth:`run`
        overlays on top of the canonical RCMIP3 baseline.

        Parameters
        ----------
        calibration_dir
            Calibration directory root. Must contain the gaspam file,
            both natemis files, and a discoverable parameter posterior
            JSON (see :func:`_resolve_distribution_json`).
        rcmip3_bundle_path
            Directory of the canonical Zenodo 20430630 RCMIP3 bundle.
        mode
            Driving mode. Maps to ``cicero_conc_run`` internally.
        distribution_json
            Optional explicit path to the parameter posterior JSON.
            Defaults to the single ``calibrated_*ensemble*.json``,
            ``*distribution*.json``, or ``draw_samples_*.json`` in
            the calibration directory.
        member_indices
            Optional zero-based row indices into the parameter
            posterior. ``None`` (default) selects all members.
        output_variables, output_config
            Forwarded to the adapter constructor.

        Returns
        -------
        CICEROSCMPY2
            Configured adapter, ready to call ``.run(scenarios)``.
        """
        from pathlib import Path

        cal_dir = Path(calibration_dir)
        if not cal_dir.exists():
            raise FileNotFoundError(
                f"CICERO-SCM calibration directory not found: {cal_dir}"
            )
        if not cal_dir.is_dir():
            raise FileNotFoundError(
                f"CICERO-SCM calibration path is not a directory: {cal_dir}"
            )

        cfg: dict[str, Any] = {
            "rcmip3_bundle_path": str(rcmip3_bundle_path),
        }
        for key, fname in _DEFAULT_CANONICAL_FILES.items():
            candidate = cal_dir / fname
            if not candidate.is_file():
                raise FileNotFoundError(
                    f"CICEROSCMPY2.from_native_distribution: canonical "
                    f"file for {key!r} not found in {cal_dir}: "
                    f"expected {fname!r}. The calibration directory "
                    "must follow the cscm-calibrate rcmip-march2026 "
                    "layout (canonical filenames anchored on the "
                    "v2024 WMO-added-new gaspam endpoint)."
                )
            cfg[key] = str(candidate)

        if distribution_json is None:
            distribution_json = _resolve_distribution_json(cal_dir)
        cfg["distribution_json"] = str(distribution_json)

        if member_indices is not None:
            cfg["member_indices"] = list(member_indices)
        if max_workers is not None:
            cfg["max_workers"] = max_workers

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
            return cscmpy2.__version__


# ---------------------------------------------------------------------------
# Calibration-directory helpers
# ---------------------------------------------------------------------------


def _resolve_distribution_json(cal_dir) -> str:
    """Locate the parameter posterior JSON in ``cal_dir``.

    Patterns matched in order (first uniquely-matching pattern wins):

    * ``calibrated_*ensemble*.json`` -- Marit's canonical Zenodo
      publication (e.g. ``calibrated_ciceroscm_ensemble.json`` in
      `10.5281/zenodo.20506399`).
    * ``*distribution*.json`` -- internal naming used during early
      development.
    * ``draw_samples_*.json`` -- internal naming used in
      ``cscm-calibrate`` dev directories before the Zenodo
      publication convention.
    """
    from pathlib import Path

    patterns = (
        "calibrated_*ensemble*.json",
        "*distribution*.json",
        "draw_samples_*.json",
    )
    for pat in patterns:
        matches = sorted(Path(cal_dir).glob(pat))
        if len(matches) == 1:
            return str(matches[0])
        if len(matches) > 1:
            raise ValueError(
                f"CICEROSCMPY2.from_native_distribution: multiple "
                f"{pat!r} files in {cal_dir}: {[m.name for m in matches]}. "
                "Pass ``distribution_json=...`` explicitly to disambiguate."
            )
    raise FileNotFoundError(
        f"CICEROSCMPY2.from_native_distribution: no parameter posterior "
        f"JSON in {cal_dir} (expected calibrated_*ensemble*.json, "
        "*distribution*.json, or draw_samples_*.json). Pass "
        "``distribution_json=...`` explicitly."
    )


# ---------------------------------------------------------------------------
# Run dispatch
# ---------------------------------------------------------------------------


def _with_mode_applied(cfg: dict[str, Any], mode: RunMode) -> dict[str, Any]:
    """
    Inject the adapter-level ``mode`` into a cfg as the internal
    ``cicero_conc_run`` flag.

    Returns a new dict; the caller's cfg is not mutated.
    """
    new = dict(cfg)
    new["cicero_conc_run"] = mode == RunMode.CONCENTRATION_DRIVEN
    return new


def _run_one_distribution(scenarios, cfg: dict[str, Any], output_variables) -> ScmRun:
    """
    Dispatch one ``DistributionRun`` for the cfg.

    Builds scenariodata dicts from ``scenarios``, applies any
    ``member_indices`` subset to the JSON cfgs, and returns the
    concatenated ScmRun across all scenarios and members. Variables
    in :data:`._output_variables.RCMIP3_BACK_REPORTABLE_VARIABLES`
    (Solar / Volcanic / Land-use albedo ERF) are stripped from the
    upstream request and back-reported from the scendata's
    ``rf_sun_data`` / ``rf_volc_data`` / ``rf_luc_data`` trajectories
    after the model run finishes.
    """
    from ciceroscm.parallel.distributionrun import DistributionRun

    from ._output_variables import RCMIP3_BACK_REPORTABLE_VARIABLES

    distribution_json = cfg["distribution_json"]
    if not os.path.exists(distribution_json):
        raise FileNotFoundError(
            f"CICEROSCMPY2 cfg `distribution_json` not found: "
            f"{distribution_json}"
        )

    member_indices = cfg.get("member_indices")
    if member_indices is not None:
        member_indices = list(member_indices)
        if not member_indices:
            raise ValueError(
                "CICEROSCMPY2 cfg `member_indices` selected zero members; "
                "omit the key (or pass a non-empty sequence) to run the "
                "full distribution."
            )

    output_variables = list(output_variables)
    requested_backreport = [
        v for v in output_variables if v in RCMIP3_BACK_REPORTABLE_VARIABLES
    ]
    upstream_variables = [
        v for v in output_variables if v not in RCMIP3_BACK_REPORTABLE_VARIABLES
    ]

    if requested_backreport and cfg.get("rcmip3_bundle_path") is None:
        LOGGER.warning(
            "CICEROSCMPY2: back-reportable variables %s require the "
            "`rcmip3_bundle_path` cfg key to be set (the canonical "
            "RCMIP3 Zenodo 20430630 path); omitting them from the "
            "output.",
            requested_backreport,
        )
        requested_backreport = []

    if not upstream_variables and not requested_backreport:
        raise ValueError(
            "CICEROSCMPY2: no output variables to produce after filtering."
        )

    scendata_list = _build_scendata_list(scenarios, cfg)

    dist = DistributionRun(distro_config=None, json_file_name=distribution_json)
    if member_indices is not None:
        dist.cfgs = [dist.cfgs[i] for i in member_indices]

    max_workers = cfg.get("max_workers")
    if max_workers is None:
        max_workers = get_worker_count("CICEROSCM_WORKER_NUMBER")
    # Cap at the total job count. Starting more workers than jobs
    # wastes setup cost; on macOS, idle workers also race-condition on
    # stdout capture inside CICEROSCM's Fortran-init path and trip a
    # BrokenProcessPool for small ensembles.
    n_jobs = max(1, len(dist.cfgs) * len(scendata_list))
    max_workers = max(1, min(max_workers, n_jobs))

    LOGGER.info(
        "CICEROSCMPY2 dispatching %d members x %d scenarios with "
        "max_workers=%d",
        len(dist.cfgs),
        len(scendata_list),
        max_workers,
    )

    if upstream_variables:
        result = dist.run_over_distribution(
            scendata_list, upstream_variables, max_workers=max_workers
        )
        result = ScmRun(result) if not isinstance(result, ScmRun) else result
    else:
        # Pure back-report request -- skip the model dispatch.
        result = None

    if requested_backreport:
        backreport = _build_rcmip3_backreport_scmrun(
            scendata_list=scendata_list,
            backreport_variables=requested_backreport,
            dist_cfgs=dist.cfgs,
        )
        if backreport is None:
            LOGGER.info(
                "CICEROSCMPY2: no scendata trajectories matched the "
                "requested back-report variables %s (likely all "
                "idealised scenarios); back-report omitted.",
                requested_backreport,
            )
        elif result is None:
            result = backreport
        else:
            result = run_append([result, backreport])

    if result is None:
        raise ValueError(
            "CICEROSCMPY2: no output produced -- the upstream run was "
            "skipped (only back-report variables requested) and the "
            "back-report had no trajectories to copy. Add at least one "
            "non-back-reportable variable to ``output_variables``."
        )
    return result


# ---------------------------------------------------------------------------
# Scendata builder (scenarios-driven, single mode)
# ---------------------------------------------------------------------------


def _build_scendata_list(
    scenarios, cfg: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Build the per-scenario scendata dicts upstream's
    ``DistributionRun.run_over_distribution`` expects.

    For each scenario name in ``scenarios``, builds a scendata dict
    pointing at the calibration directory's baselines plus an
    in-memory ``emissions_data`` (ED) or ``concentrations_data``
    (CD) DataFrame derived from the user's ``Emissions|*`` or
    ``Atmospheric Concentrations|*`` rows overlaid on the
    corresponding baseline.

    Reads the scenarios ScmRun's ``protocol_natural_forcing`` and
    ``protocol_land_use_forcing`` meta columns (when present) to
    drive per-scenario natural-forcing and LUC handling; otherwise
    defaults to the non-idealised settings.
    """
    nystart = int(cfg.get("nystart", 1750))
    if scenarios is None or scenarios.empty:
        raise ValueError(
            "CICEROSCMPY2 needs a non-empty scenarios ScmRun. "
            "Construct it via openscm_runner.scenarios.load_rcmip3_* "
            "or hand-build with Emissions|* (ED) / "
            "Atmospheric Concentrations|* (CD) rows."
        )

    # Canonical RCMIP3 path: union the canonical
    # ``rcmip_phase3_emissions_v2.0.0.csv`` and
    # ``rcmip_phase3_concentrations_v2.0.0.csv`` rows into the user's
    # scenarios ScmRun so the existing per-scenario overlay logic
    # below picks them up. User rows take precedence per
    # ``(scenario, variable)`` -- canonical rows are dropped when the
    # user supplies the same key. Variable names from the canonical
    # CSV are canonicalised (CO2 sub-sector MAGICC names; flat F-gas/
    # HFC/halocarbon names) so the existing ``cicero_comp_dict``
    # suffix matching works without changes.
    if cfg.get("rcmip3_bundle_path"):
        scenarios = _merge_rcmip3_canonical_into_user(
            scenarios, cfg["rcmip3_bundle_path"],
        )

    scenario_years = scenarios.time_points.years()
    nyend = int(cfg.get("nyend", max(scenario_years)))
    scenario_names = sorted(set(scenarios["scenario"]))

    conc_run_global = bool(cfg.get("cicero_conc_run", False))
    if "emstart" in cfg:
        default_emstart = int(cfg["emstart"])
    elif conc_run_global:
        default_emstart = nyend
    else:
        default_emstart = 1850

    sunvolc_override = cfg.get("sunvolc")

    nat_ch4_df = _load_natemis_dataframe(cfg["nat_ch4_file"], "CH4", nystart)
    nat_n2o_df = _load_natemis_dataframe(cfg["nat_n2o_file"], "N2O", nystart)

    scendata_list: list[dict[str, Any]] = []
    for scenario_name in scenario_names:
        spec = _resolve_protocol_spec(scenarios, scenario_name)
        natural_off = spec["natural_forcing"] == "off"
        lu_zero = spec["land_use_forcing"] == "constant_zero"

        scenarios_have_em = (
            not scenarios.filter(
                scenario=scenario_name,
                variable="Emissions|*",
                log_if_empty=False,
            ).empty
        )
        scenarios_have_conc = (
            not scenarios.filter(
                scenario=scenario_name,
                variable="Atmospheric Concentrations|*",
                log_if_empty=False,
            ).empty
        )

        scen_emstart = default_emstart
        if sunvolc_override is not None:
            scen_sunvolc = int(sunvolc_override)
        else:
            scen_sunvolc = 0 if natural_off else 1

        if natural_off:
            scen_nat_ch4 = _flatten_natemis_to_preindustrial(nat_ch4_df)
            scen_nat_n2o = _flatten_natemis_to_preindustrial(nat_n2o_df)
        else:
            scen_nat_ch4 = nat_ch4_df
            scen_nat_n2o = nat_n2o_df

        idealised = natural_off and lu_zero
        em_data = _build_hybrid_emissions_data(
            scenarios=scenarios,
            scenario_name=scenario_name,
            baseline_em_file=cfg["historical_em_file"],
            nystart=nystart,
            nyend=nyend,
            emstart=scen_emstart,
            zero_unsupplied=idealised,
        )

        conc_data = None
        if conc_run_global and scenarios_have_conc:
            conc_data = _build_hybrid_concentrations_data(
                scenarios=scenarios,
                scenario_name=scenario_name,
                baseline_conc_path=cfg["historical_conc_file"],
                nystart=nystart,
                nyend=nyend,
                hold_unsupplied_at_pi=idealised,
            )

        scendata: dict[str, Any] = {
            "nystart": nystart,
            "nyend": nyend,
            "emstart": scen_emstart,
            "sunvolc": scen_sunvolc,
            "conc_run": conc_run_global,
            "idtm": int(cfg.get("idtm", 24)),
            "scenname": scenario_name,
            "gaspam_file": cfg["gaspam_file"],
            "emissions_data": em_data,
            "nat_ch4_data": scen_nat_ch4.loc[
                : min(nyend, scen_nat_ch4.index.max())
            ],
            "nat_n2o_data": scen_nat_n2o.loc[
                : min(nyend, scen_nat_n2o.index.max())
            ],
        }
        # Solar + Volcanic: per-scenario in-memory DataFrames from
        # the canonical RCMIP3 forcing CSV. The sunvolc=0 suppression
        # for idealised scenarios is handled via the scendata flag
        # above; upstream zeros internally when sunvolc=0.
        nat = _build_natural_data_from_rcmip3(
            scenario_name=scenario_name,
            rcmip3_bundle_path=cfg["rcmip3_bundle_path"],
            nystart=nystart,
            nyend=nyend,
        )
        scendata["rf_sun_data"] = nat["rf_sun_data"]
        scendata["rf_volc_data"] = nat["rf_volc_data"]

        # Land use albedo: in-memory DataFrame. Idealised scenarios
        # (``protocol_land_use_forcing == "constant_zero"``) get zeros;
        # everything else is per-scenario from canonical RCMIP3 keyed
        # by CMIP7 ScenarioMIP category.
        if lu_zero:
            scendata["rf_luc_data"] = pd.DataFrame(
                {0: [0.0] * (nyend - nystart + 1)},
                index=range(nystart, nyend + 1),
            )
        else:
            scendata["rf_luc_data"] = _build_rf_luc_data_from_rcmip3(
                scenario_name=scenario_name,
                rcmip3_bundle_path=cfg["rcmip3_bundle_path"],
                scenario_to_category=cfg.get("scenario_to_category"),
                nystart=nystart,
                nyend=nyend,
            )
        if conc_data is not None:
            scendata["concentrations_data"] = conc_data
        else:
            scendata["concentrations_file"] = cfg["historical_conc_file"]

        LOGGER.debug(
            "CICEROSCMPY2 scendata scenario=%s years=%d-%d emstart=%d "
            "conc_run=%s natural_off=%s lu_zero=%s "
            "em_overlay=%s conc_overlay=%s",
            scenario_name, nystart, nyend, scen_emstart,
            conc_run_global, natural_off, lu_zero,
            scenarios_have_em, conc_data is not None,
        )
        scendata_list.append(scendata)

    return scendata_list


# ---------------------------------------------------------------------------
# Hybrid baseline + overlay helpers
# ---------------------------------------------------------------------------


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
    """
    Hold natural emissions constant at the pre-industrial value.

    For RCMIP3 idealised scenarios (esm-flat*, esm-bell*, esm-pi-*,
    esm-1pct-*, 1pctCO2*, abrupt-*) the protocol prescribes constant
    pre-industrial non-CO2 forcing. The bundled natemis_CH4 / N2O
    files carry a historical trajectory through 2022 then jump
    discontinuously to a flat 2024+ value (252 -> 280.65 Tg/yr for
    CH4); both the historical drift and the jump pollute the
    idealised diagnostics. This helper returns a copy with every row
    replaced by the ``anchor_year`` (1750) value.
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
    v1.1.x adapter's helper).

    - ``"Pg_C"``  -> ``"PgC / yr"``  (CO2 / CO2_lu)
    - ``"Tg_N"`` for N2O is the AR convention -> ``"TgN2ON / yr"``
    - ``"Tg_SO2"``, ``"Tg_C"`` etc. -> strip the underscore
    - ``"Tg"`` / ``"Mt"`` / ``"Gg"`` with no underscore -> append the
      species name
    """
    if cicero_species == "N2O" and cicero_unit_raw == "Tg_N":
        return "TgN2ON / yr"
    if "_" in cicero_unit_raw:
        return cicero_unit_raw.replace("_", "") + " / yr"
    comp_str = cicero_species.replace("-", "").replace("BMB_AEROS_", "")
    return f"{cicero_unit_raw}{comp_str} / yr"


def _build_hybrid_emissions_data(
    scenarios,
    scenario_name: str,
    baseline_em_file: str,
    nystart: int,
    nyend: int,
    emstart: int,
    zero_unsupplied: bool = False,
):
    """
    Build an RCMIP-format emissions DataFrame for one scenario.

    Reads ``baseline_em_file`` as the species-coverage and
    historical-trajectory source, then overlays the user's
    ``Emissions|*`` rows for ``scenario_name`` from year ``emstart``
    onwards, mapping openscm-runner variable names to CICERO species
    via the v1.1.x ``cicero_comp_dict`` and converting units through
    openscm-units. Returns a DataFrame indexed by year (nystart to
    nyend) with CICERO species as columns, ready to hand to upstream
    via the ``emissions_data`` scendata key.

    Species the user doesn't supply stay at the baseline's value
    (held forward past the baseline's extent — the canonical
    ``historical_em_*`` from cscm-calibrate already extends to 2500
    with last-value-forward constant filling).

    Parameters
    ----------
    zero_unsupplied
        When ``True``, every species column the user does NOT supply
        is overwritten with ``0.0`` across the whole ``[nystart, nyend]``
        window. This is the RCMIP3-idealised semantic (esm-flat*,
        esm-bell*, esm-pi-*, 1pctCO2*, abrupt-*) for the
        *anthropogenic* emissions surface: only CO2 varies, every other
        anthropogenic species sees no flux. Matches Marit's bundle
        files (``esm-flat10_em_*`` holds non-CO2 at 0, not at the
        1750 anthropogenic value) and mirrors FaIR's
        ``co2_only_scenarios`` runtime mask. Natural CH4 / N2O
        emissions are handled separately via the natemis flatten, so
        the combined per-scenario emissions reaching CICEROSCM are
        ``zero anthropogenic + PI-flat natural`` (= effective
        pre-industrial total). Default ``False`` (non-idealised
        scenarios pick up the baseline's historical trajectory for
        non-overridden species).
    """
    import pandas as pd
    from openscm_units import unit_registry as ureg

    from ..utils.cicero_utils.make_scenario_common import cicero_comp_dict

    df = (
        pd.read_csv(
            baseline_em_file, delimiter="\t", index_col=0, skiprows=[1, 2, 3]
        )
        .rename(columns=lambda x: x.strip())
        .astype(float)
    )
    df.index = df.index.astype(int)
    df.columns = [
        "CO2_FF" if c == "CO2"
        else "CO2_AFOLU" if c in ("CO2.1", "CO2 .1")
        else c
        for c in df.columns
    ]

    with open(baseline_em_file) as fh:
        _ = next(fh)
        unit_line = next(fh)
    unit_tokens = [t.strip() for t in unit_line.rstrip("\n").split("\t")]
    column_units = dict(zip(df.columns, unit_tokens[1:]))

    df = df.loc[nystart:nyend].copy()

    user_filtered = scenarios.filter(
        scenario=scenario_name, log_if_empty=False,
    )
    if user_filtered.empty:
        return df

    user_ts = user_filtered.timeseries(time_axis="year")
    user_ts.columns = user_ts.columns.astype(int)
    cicero_to_df_col = {"CO2": "CO2_FF", "CO2_lu": "CO2_AFOLU"}

    overlaid: list[str] = []
    overlaid_df_cols: set[str] = set()
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
        contexts = {"NOx": "NOx_conversions", "NH3": "NH3_conversions"}
        ctx = contexts.get(cicero_species)
        try:
            if ctx is not None:
                with ureg.context(ctx):
                    convfactor = (
                        (1.0 * ureg(user_unit))
                        .to(cicero_unit_pint).magnitude
                        * factor
                    )
            else:
                convfactor = (
                    (1.0 * ureg(user_unit)).to(cicero_unit_pint).magnitude
                    * factor
                )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.warning(
                "CICEROSCMPY2 hybrid emissions: skipping species %s "
                "(unit conversion %s -> %s failed: %s)",
                cicero_species, user_unit, cicero_unit_pint, exc,
            )
            skipped_unmapped.append(cicero_species)
            continue
        for year, val in user_row.items():
            if year in df.index and year >= emstart and not pd.isna(val):
                df.at[year, col] = val * convfactor
        overlaid.append(cicero_species)
        overlaid_df_cols.add(col)

    if zero_unsupplied:
        # Idealised scenarios: zero every non-user-supplied
        # anthropogenic species across all years. Matches Marit's
        # bundle files (``esm-flat10_em_*`` carries 0 for non-CO2
        # everywhere) and mirrors FaIR's runtime ``co2_only_scenarios``
        # mask. The natemis flatten handles natural CH4 / N2O
        # separately.
        zeroed: list[str] = []
        for col in df.columns:
            if col in overlaid_df_cols:
                continue
            df[col] = 0.0
            zeroed.append(col)
        LOGGER.info(
            "CICEROSCMPY2 hybrid emissions (idealised): zeroed %d "
            "non-overlaid anthropogenic species (%s).",
            len(zeroed), zeroed,
        )

    LOGGER.info(
        "CICEROSCMPY2 hybrid emissions for scenario %r: overlaid %d "
        "species from user ScmRun (%s); %d skipped on unit errors "
        "(%s); others use baseline %s.",
        scenario_name, len(overlaid), overlaid,
        len(skipped_unmapped), skipped_unmapped,
        os.path.basename(baseline_em_file),
    )

    return df


def _build_hybrid_concentrations_data(
    scenarios,
    scenario_name: str,
    baseline_conc_path: str,
    nystart: int,
    nyend: int,
    hold_unsupplied_at_pi: bool = False,
):
    """
    Build an RCMIP-format concentrations DataFrame for one CD scenario.

    Reads ``baseline_conc_path`` as the species-coverage and
    historical-trajectory source, forward-fills the last available
    row out to ``nyend``, then overlays the user's
    ``Atmospheric Concentrations|*`` rows for ``scenario_name`` on
    top via :data:`_OPENSCM_TO_CICERO_CONC`.

    The full gaspam-species column coverage matters: CICEROSCM's
    ``_precalculate_concentrations_vanilla_gases`` requires every
    gaspam-vanilla species to have a column in ``self.conc_in``.
    Returning the DataFrame for use via the ``concentrations_data``
    scendata key skips the ``concentrations_file`` reader and its
    unit check (which we don't need; the DataFrame was built from a
    gaspam-compatible baseline).

    Parameters
    ----------
    hold_unsupplied_at_pi
        When ``True``, every species column the user does NOT supply
        is overwritten with the baseline's 1750 (PI) value across the
        whole ``[nystart, nyend]`` window. This is the RCMIP3-idealised
        semantic for the *concentrations* surface (1pctCO2*, abrupt-*,
        piControl): non-CO2 atmospheric content is held at pre-
        industrial regardless of what the historical baseline says.
        Matches Marit's bundle files (``1pctCO2_conc_*`` holds CH4 at
        798.8 ppb, N2O at 271.57 ppb, CFCs at 0 across all years).
        Asymmetric with the emissions case (which zeros, not PI-holds)
        because emissions are fluxes and concentrations are state:
        zero emissions = no anthropogenic flux into the atmosphere;
        PI-held concentrations = preserve the natural atmospheric
        content. Default ``False`` (non-idealised concentrations
        inherit the baseline trajectory).
    """
    import pandas as pd

    df = (
        pd.read_csv(
            baseline_conc_path, delimiter=r"\s+", index_col=0,
            skiprows=[1, 2, 3],
        )
        .rename(columns=lambda x: x.strip())
        .astype(float)
    )
    df.index = df.index.astype(int)

    if nyend > df.index.max():
        last = df.iloc[-1]
        extension = pd.DataFrame(
            {col: [last[col]] * (nyend - df.index.max())
             for col in df.columns},
            index=range(df.index.max() + 1, nyend + 1),
        )
        df = pd.concat([df, extension])

    user_filtered = scenarios.filter(
        scenario=scenario_name,
        variable="Atmospheric Concentrations|*",
        log_if_empty=False,
    )
    if user_filtered.empty:
        return df

    user_ts = user_filtered.timeseries(time_axis="year")
    user_ts.columns = user_ts.columns.astype(int)

    overlaid: list[str] = []
    overlaid_cols: set[str] = set()
    for index_tuple, values in user_ts.iterrows():
        meta = dict(zip(user_ts.index.names, index_tuple))
        species_short = meta["variable"].split("|", 1)[1]
        cicero_name = _OPENSCM_TO_CICERO_CONC.get(
            species_short, species_short
        )
        if cicero_name not in df.columns:
            LOGGER.debug(
                "CICEROSCMPY2 hybrid concs: species %r (CICERO name "
                "%r) absent from baseline conc file %s; ignored.",
                species_short, cicero_name,
                os.path.basename(baseline_conc_path),
            )
            continue
        for year, val in values.items():
            if year in df.index and not pd.isna(val):
                df.at[year, cicero_name] = float(val)
        overlaid.append(cicero_name)
        overlaid_cols.add(cicero_name)

    if hold_unsupplied_at_pi:
        pi_year = 1750 if 1750 in df.index else int(df.index.min())
        pi_row = df.loc[pi_year]
        held: list[str] = []
        for col in df.columns:
            if col in overlaid_cols:
                continue
            df[col] = float(pi_row[col])
            held.append(col)
        LOGGER.info(
            "CICEROSCMPY2 hybrid concentrations (idealised): held "
            "%d non-overlaid species at PI value (year %d) (%s).",
            len(held), pi_year, held,
        )

    LOGGER.info(
        "CICEROSCMPY2 hybrid concentrations for scenario %r: "
        "overlaid %d species from user ScmRun (%s); others use "
        "baseline %s.",
        scenario_name, len(overlaid), overlaid,
        os.path.basename(baseline_conc_path),
    )

    return df


def _resolve_protocol_spec(
    scenario_run, scenario_name: str,
) -> dict[str, str]:
    """
    Return per-scenario protocol metadata for the scendata builder.

    Result has two keys:

    * ``natural_forcing`` — ``"on"`` or ``"off"``. ``"off"`` zeros
      ``sunvolc`` and flattens the natural CH4 / N2O trajectories to
      their 1750 value.
    * ``land_use_forcing`` — ``"historical"`` or ``"constant_zero"``.
      ``"constant_zero"`` substitutes ``rf_luc_constant_zero_file``
      for ``rf_luc_file`` (or warns if not available).

    Reads the scenarios ScmRun's ``protocol_natural_forcing`` and
    ``protocol_land_use_forcing`` meta columns (the RCMIP3 loader
    sets these). When absent, defaults to the non-idealised
    ``("on", "historical")`` pair; idealised users should set the
    meta columns on their ScmRun or override at the cfg level.
    """
    meta = getattr(scenario_run, "meta", None)
    have_meta = (
        meta is not None
        and "protocol_natural_forcing" in meta.columns
        and "protocol_land_use_forcing" in meta.columns
    )
    if have_meta:
        sub = meta[meta["scenario"].astype(str) == scenario_name]
        if not sub.empty:
            return {
                "natural_forcing": str(sub["protocol_natural_forcing"].iloc[0]),
                "land_use_forcing": str(sub["protocol_land_use_forcing"].iloc[0]),
            }
    return {"natural_forcing": "on", "land_use_forcing": "historical"}


def _build_natural_data_from_rcmip3(
    *,
    scenario_name: str,
    rcmip3_bundle_path,
    nystart: int,
    nyend: int,
):
    """
    Build per-scenario Solar + Volcanic DataFrames from the canonical
    RCMIP3 Zenodo 20430630 bundle.

    Returns a dict with two keys:

    * ``rf_sun_data``: year-indexed single-column DataFrame of the
      ``Effective Radiative Forcing|Natural|Solar`` trajectory for
      ``scenario_name``, sliced to ``[nystart, nyend]``.
    * ``rf_volc_data``: same shape, from
      ``Effective Radiative Forcing|Natural|Volcanic``. Upstream
      :class:`ciceroscm.input_handler.InputHandler` propagates this
      to ``rf_volc_n_data`` and ``rf_volc_s_data`` automatically (see
      ``set_sun_volc_luc_defaults``), and the input handler's data
      coercion (``arr[:, None]`` for the volcanic single-column case,
      ``reshape(-1)`` for solar) handles the shape adjustment for
      both natural-forcing axes.

    Annual values are passed through unchanged; upstream's per-year
    integration treats the single column as the year's mean forcing.

    Scenarios with no canonical row (e.g. native CMIP7
    ``scen7-{cat}`` names) fall back to zeros with a warning.
    """
    import pandas as pd

    from ...io.rcmip3 import load_rcmip3_forcings

    years = pd.RangeIndex(nystart, nyend + 1, name="year")
    zeros = pd.DataFrame({0: [0.0] * len(years)}, index=years)

    out: dict[str, pd.DataFrame] = {}
    for label, variable in (
        ("rf_sun_data", "Effective Radiative Forcing|Natural|Solar"),
        ("rf_volc_data", "Effective Radiative Forcing|Natural|Volcanic"),
    ):
        df = load_rcmip3_forcings(
            rcmip3_bundle_path,
            scenarios=[scenario_name],
            variables=[variable],
        )
        if df.empty:
            LOGGER.warning(
                "CICEROSCMPY2 RCMIP3 natural-forcing path: scenario "
                "%r has no %r row in the canonical forcing CSV. "
                "Falling back to zero %s forcing.",
                scenario_name, variable,
                label.replace("rf_", "").replace("_data", ""),
            )
            out[label] = zeros.copy()
            continue
        year_cols = [c for c in df.columns if c.isdigit()]
        series = (
            df[year_cols].iloc[0]
            .rename(lambda y: int(y))
            .astype(float)
            .reindex(years).fillna(0.0)
        )
        out[label] = pd.DataFrame({0: series.values}, index=years)
    return out


def _build_rf_luc_data_from_rcmip3(
    *,
    scenario_name: str,
    rcmip3_bundle_path,
    scenario_to_category: dict[str, str] | None,
    nystart: int,
    nyend: int,
):
    """
    Build a per-scenario LUC albedo DataFrame from the canonical
    RCMIP3 Zenodo 20430630 bundle.

    Returns a year-indexed DataFrame with a single unnamed column
    (column key ``0``) covering ``[nystart, nyend]``, ready for the
    CICEROSCM ``rf_luc_data`` scendata slot — same shape as the
    in-memory zeros DataFrame used for the idealised
    ``protocol_land_use_forcing == "constant_zero"`` path. Values
    are pulled from the bundle's
    ``input_datafiles_generation/data/Forcing_AFOLU_CO2.csv``,
    keyed by the CMIP7 ScenarioMIP category the scenario resolves
    to (default mapping + per-cfg override applied via
    :func:`openscm_runner.io.rcmip3.resolve_scenario_category`).

    For ``historical`` / ``historical-cmip6`` the per-component
    ``Effective Radiative Forcing|Anthropogenic|Albedo Change|Land Use``
    row from the canonical forcing CSV is used instead.

    CICEROSCMPY2 has no irrigation channel, so the Irrigation
    component is dropped — only the Land Use trajectory is written
    into ``rf_luc_data``. (FaIR fills Irrigation as a separate
    species; CICERO does not.)
    """
    import pandas as pd

    from ...io.rcmip3 import (
        load_rcmip3_albedo_categories,
        load_rcmip3_forcings,
        resolve_scenario_category,
    )

    years = pd.RangeIndex(nystart, nyend + 1, name="year")
    try:
        category = resolve_scenario_category(
            scenario_name, overrides=scenario_to_category,
        )
    except KeyError as exc:
        LOGGER.warning(
            "CICEROSCMPY2 RCMIP3 land-use path: scenario %r has no "
            "CMIP7 category mapping (%s). Falling back to zero "
            "Land use forcing.",
            scenario_name, exc,
        )
        return pd.DataFrame({0: [0.0] * len(years)}, index=years)

    if category is None:
        df = load_rcmip3_forcings(
            rcmip3_bundle_path,
            scenarios=[scenario_name],
            variables=[
                "Effective Radiative Forcing|Anthropogenic|"
                "Albedo Change|Land Use"
            ],
        )
        if df.empty:
            LOGGER.warning(
                "CICEROSCMPY2 RCMIP3 land-use path: scenario %r has "
                "no Albedo Change|Land Use row in the canonical "
                "forcing CSV. Falling back to zero.",
                scenario_name,
            )
            return pd.DataFrame({0: [0.0] * len(years)}, index=years)
        year_cols = [c for c in df.columns if c.isdigit()]
        series = (
            df[year_cols].iloc[0]
            .rename(lambda y: int(y))
            .astype(float)
            .reindex(years).fillna(0.0)
        )
        return pd.DataFrame({0: series.values}, index=years)

    albedo = load_rcmip3_albedo_categories(
        rcmip3_bundle_path, category=category,
    )
    series = albedo["Land Use"].reindex(years).fillna(0.0)
    return pd.DataFrame({0: series.values}, index=years)


# ---------------------------------------------------------------------------
# RCMIP3 back-report
# ---------------------------------------------------------------------------


# Variable name -> scendata key holding the per-scenario trajectory. The
# scendata keys are populated by ``_build_scendata_list`` whenever the
# ``rcmip3_bundle_path`` cfg is set (Solar / Volcanic via
# ``_build_natural_data_from_rcmip3``; Land use via
# ``_build_rf_luc_data_from_rcmip3``).
_BACKREPORT_VAR_TO_SCENDATA_KEY: dict[str, str] = {
    "Effective Radiative Forcing|Natural|Solar": "rf_sun_data",
    "Effective Radiative Forcing|Natural|Volcanic": "rf_volc_data",
    "Effective Radiative Forcing|Anthropogenic|Albedo Change|Land use": "rf_luc_data",
}


def _build_rcmip3_backreport_scmrun(
    *,
    scendata_list: list[dict[str, Any]],
    backreport_variables: list[str],
    dist_cfgs: list[dict[str, Any]],
) -> ScmRun | None:
    """
    Build an :class:`scmdata.ScmRun` of back-reported forcing inputs.

    For each ``(scenario, run_id, variable)`` combination, copies the
    scendata's per-scenario trajectory (``rf_sun_data`` /
    ``rf_volc_data`` / ``rf_luc_data``) into an ScmRun row with the
    metadata schema upstream's
    :class:`ciceroscm.parallel.cscmparwrapper.CSCMParWrapper`
    uses for its diagnostic output -- ``climate_model``, ``model``,
    ``run_id``, ``scenario``, ``region``, ``variable``, ``unit``,
    then one column per year.

    The trajectory is per-scenario; every ensemble member sees the
    same forcing input, so we replicate the same series across each
    ``dist_cfgs`` entry's ``Index`` (run_id). The adapter post-
    processing (:func:`CICEROSCMPY2._run`) overwrites the
    ``climate_model`` column with the model's version string after
    :func:`run_append` merges this with the upstream-produced result.
    """
    rows: list[dict[str, Any]] = []
    for scendata in scendata_list:
        scenario_name = scendata["scenname"]
        for variable in backreport_variables:
            data_key = _BACKREPORT_VAR_TO_SCENDATA_KEY[variable]
            data = scendata.get(data_key)
            if data is None:
                # Scendata builder didn't populate this trajectory
                # (e.g. lu_zero idealised scenario for Land use). Skip
                # for this scenario so the back-report mirrors the
                # actual model input.
                continue
            series = data.iloc[:, 0] if hasattr(data, "iloc") else data
            year_pairs = [
                (str(int(year)), float(val))
                for year, val in zip(series.index, series.values)
            ]
            for cfg_dict in dist_cfgs:
                row: dict[str, Any] = {
                    "climate_model": "CICERO-SCM-PY",
                    "model": scenario_name,
                    "run_id": cfg_dict["Index"],
                    "scenario": scenario_name,
                    "region": "World",
                    "variable": variable,
                    "unit": "W/m^2",
                }
                row.update(year_pairs)
                rows.append(row)

    if not rows:
        # No rows produced (e.g. every requested back-report skipped
        # because the requested variable has no scendata entry --
        # idealised scenarios that zero LUC, etc). Caller treats None
        # as "no back-report to append".
        return None

    return ScmRun(pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# RCMIP3 canonical emissions + concentrations merge
# ---------------------------------------------------------------------------


def _merge_rcmip3_canonical_into_user(scenarios, rcmip3_bundle_path):
    """
    Union canonical RCMIP3 emissions + concentrations into the user ScmRun.

    Reads ``rcmip_phase3_emissions_v2.0.0.csv`` and
    ``rcmip_phase3_concentrations_v2.0.0.csv`` from the bundle,
    filters to the scenarios already present in ``scenarios``,
    canonicalises variable names (CO2 sub-sectors get the MAGICC
    suffix; F-gas/HFC/halocarbon intermediate IAMC categories are
    stripped) and appends the canonical rows to the user ScmRun.

    Deduplication is per ``(scenario, variable)``: canonical rows
    that overlap a user-supplied key are dropped so the user's
    values win. Variables the user doesn't supply for a given
    scenario are filled from canonical.

    The returned ScmRun is what the rest of
    :func:`_build_scendata_list` operates on; the existing per-
    scenario emissions / concentrations builders see the merged
    object and run unchanged.
    """
    import pandas as pd

    from ...io.rcmip3 import (
        canonicalise_rcmip3_variable,
        load_rcmip3_concentrations,
        load_rcmip3_emissions,
    )

    scenario_names = sorted(set(scenarios["scenario"]))

    user_keys: set[tuple[str, str]] = set()
    user_meta = scenarios.meta
    for scen, var in zip(user_meta["scenario"], user_meta["variable"]):
        user_keys.add((str(scen), str(var)))

    canon_rows: list[dict] = []
    for kind, loader in (
        ("emissions", load_rcmip3_emissions),
        ("concentrations", load_rcmip3_concentrations),
    ):
        df = loader(rcmip3_bundle_path, scenarios=scenario_names)
        if df.empty:
            continue
        year_cols = [
            c for c in df.columns if isinstance(c, str) and c.isdigit()
        ]
        for _, csv_row in df.iterrows():
            scen = str(csv_row["Scenario"])
            variable = canonicalise_rcmip3_variable(csv_row["Variable"])
            if (scen, variable) in user_keys:
                continue
            row: dict = {
                "scenario": scen,
                "variable": variable,
                "region": csv_row.get("Region", "World"),
                "unit": csv_row["Unit"],
                "model": "RCMIP3-canonical",
            }
            for y in year_cols:
                row[y] = float(csv_row[y])
            canon_rows.append(row)

    if not canon_rows:
        return scenarios

    canon_scmrun = ScmRun(pd.DataFrame(canon_rows))
    LOGGER.info(
        "CICEROSCMPY2 RCMIP3 canonical path: merged %d additional rows "
        "from canonical CSVs into user ScmRun (user rows kept their "
        "precedence per (scenario, variable)).",
        len(canon_rows),
    )
    return run_append([scenarios, canon_scmrun])
