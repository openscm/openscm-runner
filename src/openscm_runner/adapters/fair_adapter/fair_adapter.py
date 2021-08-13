"""
FAIR adapter
"""
import functools
import os

import numpy as np
import pandas as pd
from scmdata import ScmRun

from ...progress import progress
from ..base import _Adapter
from ._compat import fair
from ._run_fair import run_fair
from ._scmdf_to_emissions import scmdf_to_emissions


@functools.lru_cache()
def _get_natural_emissions_and_forcing(startyear, nt):
    # TODO: somebody who knows what they are doing to use scmdata
    natural_df = pd.read_csv(
        os.path.join(os.path.dirname(__file__), "natural-emissions-and-forcing.csv",),
    )
    ndf_values = natural_df.values

    n_index_columns = 7
    start_index = startyear - 1750 + n_index_columns
    ch4_n2o = ndf_values[0:2, start_index : start_index + nt].T
    solar_forcing = ndf_values[2, start_index : start_index + nt].T
    volcanic_forcing = ndf_values[3, start_index : start_index + nt].T

    return {
        "ch4_n2o": ch4_n2o,
        "solar_forcing": solar_forcing,
        "volcanic_forcing": volcanic_forcing,
    }


class FAIR(_Adapter):
    """
    Adapter for running FAIR
    """

    def _init_model(self, *args, **kwargs):
        if fair is None:
            raise ImportError("fair is not installed. Run 'pip install fair'")

    def _run(self, scenarios, cfgs, output_variables, output_config):
        if output_config is not None:
            raise NotImplementedError("`output_config` not implemented for FaIR")

        fair_df = ScmRun(scenarios.timeseries())
        full_cfgs = self._make_full_cfgs(fair_df, cfgs)

        res = run_fair(full_cfgs, output_variables)
        res["climate_model"] = "FaIRv{}".format(self.get_version())

        return res

    def _make_full_cfgs(self, scenarios, cfgs):  # pylint: disable=R0201,R0914
        full_cfgs = []
        run_id_block = 0
        startyear = _check_startyear(cfgs)

        for (scenario, model), smdf in progress(
            scenarios.timeseries().groupby(["scenario", "model"]),
            desc="Creating FaIR emissions inputs",
        ):
            smdf_in = ScmRun(smdf)
            scen_startyear = smdf_in.time_points.years()[0]
            endyear = smdf_in.time_points.years()[-1]

            if startyear < 1750:
                raise ValueError(
                    "startyear must be 1750 or later (%d specified)" % startyear
                )
            if endyear > 2500:
                raise ValueError(
                    "endyear must be 2500 or earlier (%d implied by scenario data)"
                    % endyear
                )
            emissions = scmdf_to_emissions(
                smdf_in,
                startyear=startyear,
                scen_startyear=scen_startyear,
                endyear=endyear,
            )
            nt = emissions.shape[0]

            natural_components = _get_natural_emissions_and_forcing(startyear, nt)
            ch4_n2o = natural_components["ch4_n2o"]
            solar_forcing = natural_components["solar_forcing"]
            volcanic_forcing = natural_components["volcanic_forcing"]

            scenario_cfg = [
                {
                    "scenario": scenario,
                    "model": model,
                    "run_id": run_id_block + i,
                    "emissions": emissions,
                    "natural": ch4_n2o,
                    "F_volcanic": volcanic_forcing,
                    "F_solar": solar_forcing,
                    "efficacy": np.ones(45),
                    "diagnostics": "AR6",
                    "gir_carbon_cycle": True,
                    "temperature_function": "Geoffroy",
                    "aerosol_forcing": "aerocom+ghan2",
                    "fixPre1850RCP": False,
                    "b_tro3": np.array(
                        [1.77871043e-04, 5.80173377e-05, 1.94458719e-04, 2.09151270e-03]
                    ),
                    "tropO3_forcing": "cmip6",
                    "aCO2land": 0.0006394631886297174,
                    "b_aero": np.array([-0.00503, 0.0, 0.0, 0.0, 0.0385, -0.0104, 0.0]),
                    "ghan_params": np.array([1.232, 73.9, 63.0]),
                    "gmst_factor": 1 / 1.04,
                    "ohu_factor": 0.92,
                    "startyear": startyear,
                    **cfg,
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


def _check_startyear(cfgs):
    """
    Check to see that at most one startyear is defined in the config
    Returns
    -------
    int
        startyear

    Raises
    ------
    ValueError
        if more that one startyear is defined
    """
    first_startyear = cfgs[0].pop("startyear", 1750)
    if len(cfgs) > 1:
        for cfg in cfgs[1:]:
            this_startyear = cfg.pop("startyear", 1750)
            if this_startyear != first_startyear:
                raise ValueError("Can only handle one startyear per scenario ensemble")

    return first_startyear
