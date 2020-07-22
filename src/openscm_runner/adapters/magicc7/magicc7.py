"""
MAGICC7 adapter
"""
import logging
import os
from subprocess import check_output

import pymagicc
from scmdata import ScmDataFrame
from tqdm.autonotebook import tqdm

from ...utils import get_env
from ..base import _Adapter
from ._run_magicc_parallel import run_magicc_parallel

LOGGER = logging.getLogger(__name__)


class MAGICC7(_Adapter):
    """
    Adapter for running MAGICC7
    """

    def __init__(self):
        """
        Initialise the MAGICC7 adapter
        """
        super().__init__()
        self.magicc_scenario_setup = {
            "file_emisscen": "WMO_MHALO.SCEN7",
            "file_emisscen_2": "Velders_HFC_Kigali.SCEN7",
            "file_emisscen_3": "SSP2_45_HFC_C2F6_CF4_SF6_MISSGAS_Ext2250.SCEN7",
            "file_emisscen_4": "SSP2_45_HFC_C2F6_CF4_SF6_Ext2250.SCEN7",
            "file_emisscen_5": "SSP2_45_RCPPLUSBUNKERS_Ext2250.SCEN7",
            "file_emisscen_6": "SSP245_AEROSOLS_NMVOC.SCEN7",
        }
        """dict: MAGICC base scenario setup"""

    def _init_model(self):  # pylint:disable=arguments-differ
        pass

    def _run(self, scenarios, cfgs, output_variables):
        # TODO: add use of historical data properly  # pylint:disable=fixme
        LOGGER.warning("Historical data has not been checked")

        magicc_df = scenarios.timeseries().reset_index()
        magicc_df["variable"] = magicc_df["variable"].apply(
            lambda x: x.replace("Sulfur", "SOx")
            .replace("HFC4310mee", "HFC4310")
            .replace("VOC", "NMVOC")
        )

        magicc_scmdf = pymagicc.io.MAGICCData(magicc_df)
        emms_units = pymagicc.definitions.MAGICC7_EMISSIONS_UNITS
        emms_units["openscm_variable"] = emms_units["magicc_variable"].apply(
            lambda x: pymagicc.definitions.convert_magicc7_to_openscm_variables(
                "{}_EMIS".format(x)
            )
        )
        emms_units = emms_units.set_index("openscm_variable")
        for variable in magicc_scmdf["variable"].unique():
            magicc_unit = emms_units.loc[variable, "emissions_unit"]
            magicc_scmdf = magicc_scmdf.convert_unit(
                magicc_unit, variable=variable, context="NOx_conversions"
            )

        full_cfgs = self._write_scen_files_and_make_full_cfgs(magicc_scmdf, cfgs)

        res = run_magicc_parallel(full_cfgs, output_variables).timeseries()
        LOGGER.debug("Dropping todo metadata")
        res.index = res.index.droplevel("todo")
        res = ScmDataFrame(res)

        return res

    def _write_scen_files_and_make_full_cfgs(self, scenarios, cfgs):
        full_cfgs = []
        run_id_block = 0

        for (scenario, model), smdf in tqdm(
            scenarios.timeseries().groupby(["scenario", "model"]),
            desc="Writing SCEN7 files",
        ):

            writer = pymagicc.io.MAGICCData(smdf)
            writer.set_meta("SET", "todo")
            writer.metadata = {
                "header": "SCEN7 file written by openscm_runner for the {} scenario".format(
                    scenario
                )
            }
            scen_file_name = (
                "{}_{}.SCEN7".format(scenario, model)
                .upper()
                .replace("/", "-")
                .replace("\\", "-")
            )
            writer.write(
                os.path.join(self._run_dir(), scen_file_name),
                magicc_version=self.get_version()[1],
            )

            scenario_cfg = [
                {
                    "scenario": scenario,
                    "model": model,
                    "file_emisscen_8": scen_file_name,
                    "run_id": i + run_id_block,
                    **self.magicc_scenario_setup,
                    **cfg,
                }
                for i, cfg in enumerate(cfgs)
            ]
            run_id_block += len(scenario_cfg)

            full_cfgs += scenario_cfg

        assert len(full_cfgs) == scenarios[
            ["scenario", "model"]
        ].drop_duplicates().shape[0] * len(cfgs)

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
        return check_output([cls._executable(), "--version"]).decode("utf-8").strip()

    @classmethod
    def _executable(cls):
        return get_env("MAGICC_EXECUTABLE_7")

    @classmethod
    def _run_dir(cls):
        return os.path.join(os.path.dirname(cls._executable()), "..", "run")
