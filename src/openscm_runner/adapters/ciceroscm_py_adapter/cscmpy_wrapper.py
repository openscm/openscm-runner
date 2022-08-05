"""
CICEROSCM_WRAPPER for parallelisation
"""
import logging
import os

import pandas as pd
from scmdata import ScmRun, run_append

from ..utils.cicero_utils._utils import _get_unique_index_values
from ._compat import cscmpy
from .make_scenario_data import SCENARIODATAGETTER
from .read_results import CSCMREADER

LOGGER = logging.getLogger(__name__)


class CSCMPYWrapper:  # pylint: disable=too-few-public-methods
    """
    CICEROSCM Wrapper for parallel runs
    """

    def __init__(self, scenariodata):
        """
        Intialise CICEROSCM wrapper
        """
        self.udir = os.path.join(
            os.path.dirname(__file__), "..", "ciceroscm_adapter", "utils_templates"
        )
        self.sdatagetter = SCENARIODATAGETTER(self.udir)
        nystart = 1750  # TODO: get rid of hardcoding for these
        nyend = 2100  # TODO: get rid of hardcoding for these
        emstart = 1850  # TODO: get rid of hardcoding for these
        self.resultsreader = CSCMREADER(nystart, nyend)
        self.cscm = cscmpy.CICEROSCM(
            {
                "gaspam_file": os.path.join(
                    os.path.dirname(__file__), "gases_vupdate_2022_AR6.txt"
                ),  # TODO set from cfgs
                "nyend": nyend,  # TODO set from cfgs or scenariodata
                "nystart": nystart,
                "emstart": emstart,
                "concentrations_file": os.path.join(
                    self.udir, "run_dir", "ssp245_conc_RCMIP.txt"
                ),
                "emissions_data": self.sdatagetter.get_scenario_data(scenariodata),
                "nat_ch4_file": os.path.join(
                    self.udir, "run_dir", "input_OTHER", "NATEMIS", "natemis_ch4.txt"
                ),  # TODO set from cfgs
                "nat_n2o_file": os.path.join(
                    self.udir, "run_dir", "input_OTHER", "NATEMIS", "natemis_n2o.txt"
                ),  # TODO set from cfgs
            }
        )
        self.scen = _get_unique_index_values(scenariodata, "scenario")
        self.model = _get_unique_index_values(scenariodata, "model")

    def run_over_cfgs(self, cfgs, output_variables):
        """
        Run over each configuration parameter set
        write parameterfiles, run, read results
        and make an ScmRun with results
        """
        runs = []
        for i, pamset in enumerate(cfgs):
            self.cscm._run(  # pylint: disable=protected-access
                {"results_as_dict": True},
                pamset_udm=pamset["pamset_udm"],
                pamset_emiconc=pamset["pamset_emiconc"],
            )
            for variable in output_variables:
                (years, timeseries, unit,) = self.resultsreader.get_variable_timeseries(
                    self.cscm.results, variable, self.sdatagetter
                )
                if isinstance(years, pd.DataFrame) and years.empty:  # pragma: no cover
                    continue  # pragma: no cover
                runs.append(
                    ScmRun(
                        pd.Series(timeseries, index=years),
                        columns={
                            "climate_model": "CICERO-SCM-PY",
                            "model": self.model,
                            "run_id": pamset.get("Index", i),
                            "scenario": self.scen,
                            "region": ["World"],
                            "variable": [variable],
                            "unit": [unit],
                        },
                    )
                )

        return run_append(runs)
