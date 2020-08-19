"""
FAIR adapter
"""
import fair
import numpy as np
from fair.ancil import cmip6_solar, cmip6_volcanic, natural
from fair.tools.scmdf import scmdf_to_emissions
from scmdata import ScmDataFrame
from tqdm.autonotebook import tqdm

from ..base import _Adapter
from ._run_fair import run_fair


class FAIR(_Adapter):
    """
    Adapter for running FAIR
    """

    def _init_model(self, *args, **kwargs):
        pass

    def _run(self, scenarios, cfgs, output_variables):
        fair_df = ScmDataFrame(scenarios.timeseries())
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
            smdf_in = ScmDataFrame(smdf)

            emissions = scmdf_to_emissions(smdf_in)

            emissions_pi = np.zeros(40)
            emissions_pi[5] = 1.2212429848636561
            emissions_pi[6] = 348.5273588
            emissions_pi[7] = 60.02182622
            emissions_pi[8] = 3.8773253867471933
            emissions_pi[9] = 2.097770755
            emissions_pi[10] = 15.44766815

            scenario_cfg = [
                {
                    "scenario": scenario,
                    "model": model,
                    "run_id": run_id_block + i,
                    "emissions": emissions,
                    "natural": natural.Emissions.emissions[:336, :],
                    "F_volcanic": cmip6_volcanic.Forcing.volcanic[:336],
                    "F_solar": cmip6_solar.Forcing.solar[:336],
                    "efficacy": np.ones(41),
                    "diagnostics": "AR6",
                    "gir_carbon_cycle": True,
                    "temperature_function": "Geoffroy",
                    "aerosol_forcing": "aerocom+ghan2",
                    "fixPre1850RCP": False,
                    "E_pi": emissions_pi,
                    "b_tro3": np.array(
                        [1.77871043e-04, 5.80173377e-05, 1.94458719e-04, 2.09151270e-03]
                    ),
                    "tropO3_forcing": "cmip6",
                    "aCO2land": 0.0006394631886297174,
                    "b_aero": np.array([-0.00503, 0.0, 0.0, 0.0, 0.0385, -0.0104, 0.0]),
                    "ghan_params": np.array([1.232, 73.9, 63.0]),
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
