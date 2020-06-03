"""
FAIR adapter
"""
import os

import numpy as np
import pyam
import fair
from fair.tools.scmdf import scmdf_to_emissions
from fair.ancil import natural, cmip6_volcanic, cmip6_solar
from tqdm.autonotebook import tqdm

from ..base import _Adapter
from ._run_fair import run_fair


class FAIR(_Adapter):
    """
    Adapter for running FAIR
    """

    def __init__(self):
        """
        Initialise the FAIR adapter
        """

    def _init_model(self):
        pass

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
            FAIR output
        """

        fair_df = pyam.IamDataFrame(scenarios.timeseries().reset_index())
        full_cfgs = self._make_full_cfgs(fair_df, cfgs)

        res = run_fair(full_cfgs, output_variables).timeseries()
        res = pyam.IamDataFrame(res)

        return res


    def _make_full_cfgs(self, scenarios, cfgs):
        full_cfgs = []

        for (scenario, model), smdf in tqdm(
            scenarios.timeseries().groupby(["scenario", "model"]),
            desc="Creating FaIR emissions files"
        ):

            emissions = scmdf_to_emissions(smdf)

            scenario_cfg = [
                {
                    "scenario"   : scenario,
                    "model"      : model,
                    "emissions"  : emissions,
                    'natural'    : natural.Emissions.emissions[:336,:],
                    'F_volcanic' : cmip6_volcanic.Forcing.volcanic[:336],
                    'F_solar'    : cmip6_solar.Forcing.solar[:336],
                    'efficacy'   : np.ones(41),
                    'diagnostics': 'AR6',
                    'gir_carbon_cycle': True,
                    'temperature_function':'Geoffroy',
                    **cfg,
                }
                for i, cfg in enumerate(cfgs)
            ]

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
