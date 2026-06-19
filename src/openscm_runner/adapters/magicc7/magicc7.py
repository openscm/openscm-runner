"""
MAGICC7 adapter
"""
import logging
import os
from subprocess import check_output  # nosec

from scmdata import ScmRun, run_append

from ..._run_mode import RunMode
from ...progress import progress
from ...settings import config
from ..base import _Adapter
from ._compat import pymagicc
from ._concentrations_translator import (
    build_concentrations_overlay,
    cfg_keys_for_species,
    write_conc_in_file,
)
from ._run_magicc_parallel import run_magicc_parallel

LOGGER = logging.getLogger(__name__)


_VARIABLE_MAP = {
    "Surface Air Temperature Change": "Surface Temperature",
    "Atmospheric Concentrations|HFC4310mee": "Atmospheric Concentrations|HFC4310",
    "Radiative Forcing|HFC4310mee": "Radiative Forcing|HFC4310",
    "Effective Radiative Forcing|HFC4310mee": "Effective Radiative Forcing|HFC4310",
}
"""
dict[str: str] : Mapping from openscm_runner names to pymagicc names

Should only be used as an emergency escape, if changes are needed
they should really be made in pymagicc.
"""


def _convert_to_pymagicc_var(in_var):
    """
    Convert an OpenSCM-Runner name to a Pymagicc name
    """
    if in_var in _VARIABLE_MAP:
        return _VARIABLE_MAP[in_var]

    out = pymagicc.definitions.convert_magicc7_to_openscm_variables(in_var)

    return out


def _with_mode_applied(cfg, mode):
    """
    Inject the adapter-level ``mode`` into a cfg as the internal
    ``magicc_conc_driven`` flag.

    Returns a new dict; the caller's cfg is not mutated.
    """
    new = dict(cfg)
    new["magicc_conc_driven"] = mode == RunMode.CONCENTRATION_DRIVEN
    return new


class MAGICC7(_Adapter):
    """
    Adapter for running MAGICC7

    The adapter overwrites all of MAGICC7's emissions flags so that only
    emissions passed from the user are used.
    """

    model_name = "MAGICC7"
    supported_modes = frozenset(
        {RunMode.EMISSIONS_DRIVEN, RunMode.CONCENTRATION_DRIVEN}
    )

    def _init_model(self):  # pylint:disable=arguments-differ
        if pymagicc is None:
            raise ImportError(
                "pymagicc is not installed. Run 'conda install pymagicc' or 'pip install pymagicc'"
            )
        self.magicc_scenario_setup = {
            "file_emisscen_2": "NONE",
            "file_emisscen_3": "NONE",
            "file_emisscen_4": "NONE",
            "file_emisscen_5": "NONE",
            "file_emisscen_6": "NONE",
            "file_emisscen_7": "NONE",
            "file_emisscen_8": "NONE",
        }

    @staticmethod
    def _convert_to_magicc_units(scenarios):
        magicc_scmdf = pymagicc.io.MAGICCData(scenarios)
        emms_units = pymagicc.definitions.MAGICC7_EMISSIONS_UNITS
        emms_units["openscm_variable"] = emms_units["magicc_variable"].apply(
            lambda x: pymagicc.definitions.convert_magicc7_to_openscm_variables(
                f"{x}_EMIS"
            )
        )
        emms_units = emms_units.set_index("openscm_variable")
        for variable in magicc_scmdf["variable"].unique():
            magicc_unit = emms_units.loc[variable, "emissions_unit"]
            if "NOx" in variable:
                context = "NOx_conversions"
            elif "NH3" in variable:
                context = "NH3_conversions"
            else:
                context = None
            magicc_scmdf = magicc_scmdf.convert_unit(
                magicc_unit,
                variable=variable,
                context=context,
            )

        return magicc_scmdf

    def _run(self, scenarios, cfgs, output_variables, output_config):
        # TODO: add use of historical data properly  # pylint:disable=fixme
        LOGGER.warning("Historical data has not been checked")

        cfgs = [_with_mode_applied(cfg, self.mode) for cfg in cfgs]

        emissions_df = scenarios.timeseries().reset_index()
        # Filter to emissions before the variable rename: the rename's
        # ``HFC4310mee`` -> ``HFC4310`` substring substitution would
        # otherwise mangle ``Atmospheric Concentrations|HFC4310mee``
        # rows too. Concentration rows are handled separately below
        # via the conc-driven path.
        emissions_df = emissions_df[
            emissions_df["variable"].str.startswith("Emissions|")
        ].copy()
        emissions_df["variable"] = emissions_df["variable"].apply(
            lambda x: x.replace("Sulfur", "SOx")
            .replace("HFC4310mee", "HFC4310")
            .replace("VOC", "NMVOC")
        )

        magicc_scmdf = self._convert_to_magicc_units(emissions_df)
        full_cfgs = self._write_scen_files_and_make_full_cfgs(magicc_scmdf, cfgs)

        if self.mode == RunMode.CONCENTRATION_DRIVEN:
            conc_patches = self._write_conc_in_files_and_cfg_updates(
                scenarios=scenarios, cfgs=cfgs,
            )
            full_cfgs = [
                self._merge_conc_patch(cfg, conc_patches)
                for cfg in full_cfgs
            ]

        pymagicc_vars = [_convert_to_pymagicc_var(v) for v in output_variables]
        res = run_magicc_parallel(full_cfgs, pymagicc_vars, output_config)

        LOGGER.debug("Dropping todo metadata")
        res = res.drop_meta("todo")
        res["climate_model"] = f"MAGICC{self.get_version()}"

        res = self._fix_pint_incompatible_units(res)
        LOGGER.debug("Mapping variables to OpenSCM conventions")
        inverse_map = {v: k for k, v in _VARIABLE_MAP.items()}
        res["variable"] = res["variable"].apply(
            lambda x: inverse_map[x] if x in inverse_map else x
        )

        res = ScmRun(res)

        return res

    @staticmethod
    def _fix_pint_incompatible_units(inp):
        out = inp

        conversions = (("10^22 J", 10, "ZJ"),)
        for odd_unit, conv_factor, new_unit in conversions:
            if odd_unit in inp.get_unique_meta("unit"):
                LOGGER.debug(
                    "Converting %s to %s with a conversion factor of %f",
                    odd_unit,
                    new_unit,
                    conv_factor,
                )
                rest_ts = inp.filter(unit=odd_unit, keep=False)
                odd_unit_ts = inp.filter(unit=odd_unit)
                odd_unit_ts *= conv_factor
                odd_unit_ts["unit"] = new_unit
                out = run_append([rest_ts, odd_unit_ts])

        return out

    @staticmethod
    def _merge_conc_patch(cfg, conc_patches):
        """
        Layer the auto-generated conc cfg patch under the caller cfg.

        Caller-supplied ``*_switchfromconc2emis_year`` keys win over
        the auto-generated default of 9999, mirroring the precedence
        rule used elsewhere in the adapter (caller cfgs > built-in
        scenario setup).
        """
        patch = conc_patches.get((cfg["scenario"], cfg["model"]), {})
        if not patch:
            return cfg
        overrides = {
            k: v for k, v in cfg.items()
            if k.endswith("_switchfromconc2emis_year")
        }
        return {**cfg, **patch, **overrides}

    def _write_conc_in_files_and_cfg_updates(
        self, scenarios, cfgs, out_directory=None,
    ):
        """
        Write per-(scenario, gas) concentration ``.IN`` files and
        return per-(scenario, model) cfg patches that point MAGICC at
        them.

        Gases the user wants conc-driven must appear in every scenario
        in the batch (per-gas mixed-mode detection lives inside
        :func:`build_concentrations_overlay`); gases that don't qualify
        produce no patch and remain emissions-driven via the existing
        SCEN7 path. The switch year defaults to 9999 (concentration-
        driven for the whole run); callers can override per-cfg with
        their own ``*_switchfromconc2emis_year`` value (see
        :meth:`_merge_conc_patch`).
        """
        rcmip3_bundle_path = self._resolve_rcmip3_bundle_path(cfgs)

        if out_directory is None:
            out_directory = os.path.join(self._run_dir(), "openscm-runner")
            os.makedirs(out_directory, exist_ok=True)

        scenario_model_pairs = list(
            scenarios.meta[["scenario", "model"]]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        )
        scenario_names = sorted({s for s, _ in scenario_model_pairs})
        overlay = build_concentrations_overlay(
            scenarios, rcmip3_bundle_path, scenario_names,
        )
        if overlay.empty:
            return {}

        magicc_version = self.get_version()[1]
        patches: dict = {}
        for scenario, model in scenario_model_pairs:
            scen_overlay = overlay[overlay["scenario"] == scenario]
            if scen_overlay.empty:
                continue
            cfg_patch: dict = {}
            for _, row in scen_overlay.iterrows():
                species = row["magicc_species"]
                file_key, switch_key = cfg_keys_for_species(species)
                file_name = (
                    f"{scenario}_{model}_{species}_CONC.IN".upper()
                    .replace("/", "-")
                    .replace("\\", "-")
                    .replace(" ", "-")
                )
                out_path = os.path.join(out_directory, file_name)
                write_conc_in_file(
                    out_path=out_path,
                    scenario=scenario,
                    species=species,
                    unit=row["unit"],
                    series=row["series"],
                    magicc_version=magicc_version,
                )
                cfg_patch[file_key] = out_path
                cfg_patch[switch_key] = 9999
            patches[(scenario, model)] = cfg_patch
        return patches

    @staticmethod
    def _resolve_rcmip3_bundle_path(cfgs):
        """
        Pull the (required) ``rcmip3_bundle_path`` cfg key from the
        first cfg; raise a clear error if no cfg supplies it.

        Mirrors the FaIRv2 / CICEROSCMPY2 adapter convention so
        conc-driven runs are reproducible across machines (the
        baseline does not depend on the binary's bundled
        historical data).
        """
        for cfg in cfgs:
            if cfg.get("rcmip3_bundle_path"):
                return cfg["rcmip3_bundle_path"]
        raise ValueError(
            "MAGICC7 concentration-driven mode requires the "
            "``rcmip3_bundle_path`` cfg key. Pass the path to a local "
            "copy of the RCMIP Phase 3 Zenodo bundle "
            "(https://zenodo.org/records/20430630) or the bundle root "
            "directory."
        )

    def _write_scen_files_and_make_full_cfgs(self, scenarios, cfgs, out_directory=None):
        full_cfgs = []
        run_id_block = 0

        if out_directory is None:
            # Defaults to writing to the run/openscm-runner directory
            out_directory = os.path.join(self._run_dir(), "openscm-runner")
            os.makedirs(out_directory, exist_ok=True)

        for (scenario, model), smdf in progress(
            scenarios.timeseries().groupby(["scenario", "model"]),
            desc="Writing SCEN7 files",
        ):
            writer = pymagicc.io.MAGICCData(smdf)
            writer["todo"] = "SET"
            writer.metadata = {
                "header": f"SCEN7 file written by openscm_runner for the {scenario} scenario"
            }
            scen_file_name = (
                f"{scenario}_{model}.SCEN7".upper()
                .replace("/", "-")
                .replace("\\", "-")
                .replace(" ", "-")
            )
            scen_file_name = os.path.join(out_directory, scen_file_name)
            writer.write(
                scen_file_name,
                magicc_version=self.get_version()[1],
            )

            scenario_cfg = [
                {
                    "scenario": scenario,
                    "model": model,
                    "file_emisscen": scen_file_name,
                    "run_id": i + run_id_block,
                    **cfg,
                    **self.magicc_scenario_setup,
                }
                for i, cfg in enumerate(cfgs)
            ]
            run_id_block += len(scenario_cfg)

            full_cfgs += scenario_cfg

        exp_shape = scenarios.meta[["scenario", "model"]].drop_duplicates().shape[
            0
        ] * len(cfgs)
        if len(full_cfgs) != exp_shape:
            raise AssertionError(f"Expected {exp_shape} configs got {len(full_cfgs)}")
        return full_cfgs

    @classmethod
    def get_version(cls):
        """
        Get the MAGICC7 version being used by this adapter

        Returns
        -------
        str
            The MAGICC7 version id
        """
        return (
            check_output([cls._executable(), "--version"])  # nosec
            .decode("utf-8")
            .strip()
        )

    @classmethod
    def _executable(cls):
        return config["MAGICC_EXECUTABLE_7"]

    @classmethod
    def _run_dir(cls):
        return os.path.abspath(
            os.path.join(os.path.dirname(cls._executable()), "..", "run")
        )
