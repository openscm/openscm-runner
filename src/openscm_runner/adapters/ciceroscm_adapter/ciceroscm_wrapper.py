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

import numpy as np
import pandas as pd
from scmdata import ScmRun, run_append

from ...settings import config
from ..utils.cicero_utils._utils import _get_unique_index_values
from ._utils import _get_executable
from .make_scenario_files import SCENARIOFILEWRITER
from .read_results import CSCMREADER
from .write_parameter_files import PARAMETERFILEWRITER

LOGGER = logging.getLogger(__name__)


def get_endyear(scenariodata):
    """
    Get end year from scenariodata
    """
    scenarioframe = scenariodata.reset_index(
        ("model", "region", "scenario", "unit"), drop=True
    )
    years = scenarioframe.columns
    if isinstance(years[0], pd.Timestamp):
        endyear = int(years[-1].year)
    else:
        endyear = int(years[-1])
    return endyear


class CiceroSCMWrapper:  # pylint: disable=too-few-public-methods
    """
    CICEROSCM Wrapper for parallel runs
    """

    def __init__(self, scenariodata):
        """
        Intialise CICEROSCM wrapper
        """
        udir = os.path.join(os.path.dirname(__file__), "utils_templates")
        self.sfilewriter = SCENARIOFILEWRITER(udir)
        self.pamfilewriter = PARAMETERFILEWRITER(udir)
        self._setup_tempdirs()
        self.resultsreader = CSCMREADER(self.rundir, get_endyear(scenariodata))

        self.scen = _get_unique_index_values(scenariodata, "scenario")
        self.model = _get_unique_index_values(scenariodata, "model")
        self.local_scenarioname = self.get_usable_scenario_name()
        self._make_dir_structure(self.local_scenarioname)
        self._call_sfilewriter(scenariodata)

    def get_usable_scenario_name(self):
        """
        Cut the scenario name and get rid of special characters so run can work
        """
        pam_min = os.path.join(self.rundir, "1", "inputfiles", "pam_current.scm")
        executable = _get_executable(self.rundir)
        call_string = f"{executable} {pam_min}"
        max_length_1 = 255 - len(call_string) - 60
        max_length_2 = int(
            np.floor(
                (127 - len(os.path.join("./", "12345", "inputfiles", "12345_conc.txt")))
                / 2.0
            )
        )
        max_length = int(np.amin([max_length_1, max_length_2]))
        if max_length < 0:
            max_length = 1
        return re.sub("[^a-zA-Z0-9_-]", "", self.scen)[:max_length]

    def _call_sfilewriter(self, scenarios):
        """
        Call sfilwriter to write scenariodata file
        """
        self.sfilewriter.write_scenario_data(
            scenarios,
            os.path.join(self.rundir, self.local_scenarioname),
            self.local_scenarioname,
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
                os.path.join(self.rundir, self.local_scenarioname),
            )
            executable = _get_executable(self.rundir)
            pamfile = os.path.join(
                self.rundir,
                self.local_scenarioname,
                "inputfiles",
                "pam_current.scm",
            )
            call = f"{executable} {pamfile}"

            LOGGER.debug("Call, %s", call)
            subprocess.check_call(
                call,
                cwd=self.rundir,
                shell=True,  # nosec # have to use subprocess
            )
            for variable in output_variables:
                (
                    years,
                    timeseries,
                    unit,
                ) = self.resultsreader.read_variable_timeseries(
                    self.local_scenarioname,
                    variable,
                    self.sfilewriter,
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
