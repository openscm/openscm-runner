"""
CICEROSCM_WRAPPER for parallelisation
"""
import logging
import os
import re
import shutil
import subprocess  # nosec # have to use subprocess
import tempfile
from distutils import dir_util

import pandas as pd
from scmdata import ScmRun, run_append

from ...settings import config
from ._utils import _get_unique_index_values
from .make_scenario_files import SCENARIOFILEWRITER
from .read_results import CSCMREADER
from .write_parameter_files import PARAMETERFILEWRITER

LOGGER = logging.getLogger(__name__)


class CiceroSCMWrapper:  # pylint: disable=too-few-public-methods
    """
    CICEROSCM Wrapper for parallel runs
    """

    def __init__(self, scenariodata):
        """
        Intialise CICEROSCM wrapper
        """
        self.udir = os.path.join(os.path.dirname(__file__), "utils_templates")
        self.sfilewriter = SCENARIOFILEWRITER(self.udir)
        self.pamfilewriter = PARAMETERFILEWRITER(self.udir)
        self._setup_tempdirs()
        self.resultsreader = CSCMREADER(self.rundir)

        self.scen = _get_unique_index_values(scenariodata, "scenario")
        self.model = _get_unique_index_values(scenariodata, "model")
        self._make_dir_structure(re.sub("[^a-zA-Z0-9_-]", "", self.scen))

        self._call_sfilewriter(scenariodata)

    def _call_sfilewriter(self, scenarios):
        """
        Call sfilwriter to write scenariodata file
        """
        self.sfilewriter.write_scenario_data(
            scenarios,
            os.path.join(self.rundir, re.sub("[^a-zA-Z0-9_-]", "", self.scen)),
        )

    def run_over_cfgs(self, cfgs, output_variables):
        """
        Run over each configuration parameter set
        write parameterfiles, run, read results
        and make an ScmRun with results
        """
        runs = []
        for i, pamset in enumerate(cfgs):
            self.pamfilewriter.write_parameterfile(
                pamset,
                os.path.join(self.rundir, re.sub("[^a-zA-Z0-9_-]", "", self.scen)),
            )
            call = "{executable} {pamfile}".format(
                executable=os.path.join(self.rundir, "scm_vCH4fb"),
                pamfile=os.path.join(
                    self.rundir,
                    re.sub("[^a-zA-Z0-9_-]", "", self.scen),
                    "inputfiles",
                    "pam_current.scm",
                ),
            )
            LOGGER.debug("Call, %s", call)
            subprocess.check_call(
                call, cwd=self.rundir, shell=True,  # nosec # have to use subprocess
            )
            for variable in output_variables:
                (
                    years,
                    timeseries,
                    unit,
                ) = self.resultsreader.read_variable_timeseries(
                    self.scen, variable, self.sfilewriter
                )
                if years.empty:  # pragma: no cover
                    continue  # pragma: no cover

                runs.append(
                    ScmRun(
                        pd.Series(timeseries, index=years),
                        columns={
                            "climate_model": "CICERO-SCM",
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

    def _setup_tempdirs(self):
        """
        Set up temporary directories to run and make output in
        """
        root_dir = config.get("CICEROSCM_WORKER_ROOT_DIR", None)
        self.rundir = tempfile.mkdtemp(prefix="ciceroscm-", dir=root_dir)
        LOGGER.info("Creating new CICERO-SCM instance: %s", self.rundir)
        dir_util.copy_tree(
            os.path.join(os.path.dirname(__file__), "utils_templates", "run_dir"),
            self.rundir,
        )

    def cleanup_tempdirs(self):
        """
        Remove tempdirs after run
        """
        LOGGER.info("Removing CICERO-SCM instance: %s", self.rundir)
        shutil.rmtree(self.rundir)

    def _make_dir_structure(self, scenario):
        """
        Make directory structure for a scenario in which to put input and
        outputfiles for the run
        """
        os.makedirs(self.rundir, exist_ok=True)
        os.makedirs(os.path.join(self.rundir, scenario), exist_ok=True)
        os.makedirs(os.path.join(self.rundir, scenario, "inputfiles"), exist_ok=True)
        os.makedirs(os.path.join(self.rundir, scenario, "outputfiles"), exist_ok=True)
