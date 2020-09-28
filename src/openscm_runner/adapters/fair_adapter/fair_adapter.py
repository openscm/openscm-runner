"""
FAIR adapter
"""
import fair
import numpy as np
from scmdata import ScmRun
from tqdm.autonotebook import tqdm

from ..base import _Adapter
from ._run_fair import run_fair
from ._scmdf_to_emissions import scmdf_to_emissions


class FAIR(_Adapter):
    """
    Adapter for running FAIR
    """

    def _init_model(self, *args, **kwargs):
        pass

    def _run(self, scenarios, cfgs, output_variables, output_config):
        if output_config is not None:
            raise NotImplementedError("`output_config` not implemented for FaIR")

        fair_df = ScmRun(scenarios.timeseries())
        full_cfgs = self._make_full_cfgs(fair_df, cfgs)

        res = run_fair(full_cfgs, output_variables)
        res["climate_model"] = "FaIRv{}".format(self.get_version())

        return res

    def _make_full_cfgs(self, scenarios, cfgs):  # pylint: disable=R0201
        full_cfgs = []
        run_id_block = 0

        for (scenario, model), smdf in tqdm(
            scenarios.timeseries().groupby(["scenario", "model"]),
            desc="Creating FaIR emissions inputs",
        ):
            smdf_in = ScmRun(smdf)
            scen_startyear = smdf_in.time_points.years()[0]
            endyear = smdf_in.time_points.years()[-1]
            emissions = scmdf_to_emissions(
                smdf_in, startyear=1750, scen_startyear=scen_startyear, endyear=endyear
            )
            nt = emissions.shape[0]

            scenario_cfg = [
                {
                    "scenario": scenario,
                    "model": model,
                    "run_id": run_id_block + i,
                    "emissions": emissions,
                    "natural": np.zeros(
                        (nt, 2)
                    ),  # any sensible scenario should override: provide in the config
                    "F_volcanic": np.zeros(nt),  # likewise
                    "F_solar": np.zeros(nt),  # likewise
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
                    "startyear": 1750,
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
