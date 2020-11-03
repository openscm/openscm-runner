"""
FAIR adapter
"""
import fair
import numpy as np
import pandas as pd

from scmdata import ScmRun
from tqdm.autonotebook import tqdm

from ..base import _Adapter
from ._run_fair import run_fair

from __future__ import division

class FAIR2(_Adapter):
    """
    Adapter for running FAIR
    """

    def _init_model(self, *args, **kwargs):
        pass

    def _run(self, scenarios, cfgs, output_variables, output_config):
        if output_config is not None:
            raise NotImplementedError("`output_config` not implemented for FaIR")

        full_cfgs = self._make_full_cfgs(scenarios, cfgs)

        res = run_fair(full_cfgs, output_variables)
        res["climate_model"] = "FaIRv{}".format(self.get_version())

        return res

    def _make_full_cfgs(self, scenarios, cfgs):  # pylint: disable=R0201
        full_cfgs = []
        run_id_block = 0

        for (scenario, model), smdf in tqdm(
            scenarios.groupby(["scenario", "model"]),
            desc="Creating FaIR emissions inputs",
        ):
            scenario_cfg = [
                {
                    "scenario": scenario,
                    "model": model,
                    "run_id": run_id_block + i,
                    "inp_df": smdf,
                    "cfg" : cfg,
                    "gmst_factor": 1 / 1.04,
                    "ohu_factor": 0.92
                }
                for i, cfg in enumerate(cfgs)
            ]
            run_id_block += len(scenario_cfg)

            full_cfgs += scenario_cfg

        return full_cfgs
    
    @staticmethod
    def get_version():
        """
        Get the FAIR version being used by this adapter
        Returns
        -------
        str
            The FAIR version id
        """
        return fair.__version__
