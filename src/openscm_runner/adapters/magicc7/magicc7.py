"""
MAGICC7 adapter
"""
import logging
import os
from subprocess import check_output

import pymagicc
from tqdm.autonotebook import tqdm

from ...utils import get_env
from ..base import _Adapter
from ._run_magicc_parallel import run_magicc_parallel

logger = logging.getLogger(__name__)

class MAGICC7(_Adapter):
    """
    Adapter for running MAGICC7
    """
    def __init__(self):
        """
        Initialise the MAGICC7 adapter
        """
        # self.magicc = pymagicc.MAGICC7(strict=False)
        # """:obj:`pymagicc.MAGICC7`: Pymagicc class instance used to run MAGICC"""
        self.magicc_scenario_setup = {
            "file_emisscen": "WMO_MHALO.SCEN7",
            "file_emisscen_2": "Velders_HFC_Kigali.SCEN7",
            "file_emisscen_3": "SSP2_45_HFC_C2F6_CF4_SF6_MISSGAS_Ext2250.SCEN7",
            "file_emisscen_4": "SSP2_45_HFC_C2F6_CF4_SF6_Ext2250.SCEN7",
            "file_emisscen_5": "SSP2_45_RCPPLUSBUNKERS_Ext2250.SCEN7",
            "file_emisscen_6": "SSP245_AEROSOLS_NMVOC.SCEN7",
        }
        """dict: MAGICC base scenario setup"""

    def run(self, scenarios, cfgs, output_variables):
        """
        Parameters
        ----------
        scenarios : :obj:`pyam.IamDataFrame`
            Scenarios to run

        cfgs : list[dict]
            The config with which to run the model

        output_variables : list[str]
            Variables to include in the output

        Returns
        -------
        :obj:`pyam.IamDataFrame`
            MAGICC7 output
        """
        # TODO: add use of historical data properly
        logger.warning("Historical data has not been checked")
        full_cfgs = []
        run_id_block = 0
        for scenario, df in tqdm(scenarios.timeseries().groupby("scenario"), desc="Writing SCEN7 files"):
            writer = pymagicc.io.MAGICCData(df)
            writer.set_meta("SET", "todo")
            writer.metadata = {
                "header": "SCEN7 file written by openscm_runner for the {} scenario".format(scenario)
            }
            scen_file_name = "{}.SCEN7".format(scenario).upper()
            writer.write(
                os.path.join(self._run_dir(), scen_file_name),
                magicc_version=self.get_version()[1],
            )

            scenario_cfg =[{**self.magicc_scenario_setup, **cfg, "scenario": scenario, "file_emisscen_8": scen_file_name, "only": output_variables, "run_id": i + run_id_block} for i, cfg in enumerate(cfgs)]
            run_id_block += len(scenario_cfg)

            full_cfgs += scenario_cfg

        assert len(full_cfgs) == len(scenarios.scenarios()) * len(cfgs)

        res = run_magicc_parallel(full_cfgs)

        import pdb
        pdb.set_trace()


    @classmethod
    def get_version(cls):
        """
        Get the MAGICC7 version being used by this adapter

        Returns
        -------
        str
            The MAGICC7 version id
        """
        return check_output([cls._executable(), '--version']).decode("utf-8").strip()

    @classmethod
    def _executable(cls):
        return get_env("MAGICC_EXECUTABLE_7")

    @classmethod
    def _run_dir(cls):
        return os.path.join(os.path.dirname(cls._executable()), "..", "run")
