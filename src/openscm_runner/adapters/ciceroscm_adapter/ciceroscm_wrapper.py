"""
CICEROSCM_WRAPPER for parallelisation
"""
import os
import shutil
import subprocess  # nosec # have to use subprocess
import tempfile
from distutils import dir_util

import pandas as pd
from scmdata import ScmRun, run_append

# from disutils import dir_util
from .make_scenario_files import SCENARIOFILEWRITER
from .read_results import CSCMREADER
from .write_parameter_files import PARAMETERFILEWRITER


def _ensure_dir_exists(path):
    """
    Ensure directory exists, and if it doesn't make it
    """
    if not os.path.exists(path):
        os.mkdir(path)


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
        # self.rundir = None
        self._setup_tempdirs()
        self.resultsreader = CSCMREADER(self.rundir)
        self.scen = scenariodata[2015].keys()[0][1]
        self.model = scenariodata[2015].keys()[0][0]
        self._make_dir_structure(self.scen)
        self._call_sfilewriter(scenariodata)

    def _call_sfilewriter(self, scenarios):
        """
        Call sfilwriter to write scenariodata file
        """
        self.sfilewriter.write_scenario_data(
            scenarios, os.path.join(self.rundir, self.scen),
        )

    def run_over_cfgs(self, cfgs, output_variables):
        """
        Run over each configuration parameter set
        write parameterfiles, run, read results
        and make an ScmRun with results
        """
        runs = []
        for pamset in cfgs:
            self.pamfilewriter.write_parameterfile(
                pamset, os.path.join(self.rundir, self.scen)
            )
            subprocess.check_call(
                "{executable} {pamfile}".format(
                    executable=os.path.join(self.rundir, "scm_vCH4fb"),
                    pamfile=os.path.join(
                        self.rundir, self.scen, "inputfiles", "pam_current.scm"
                    ),
                ),
                cwd=self.rundir,
                shell=True,  # nosec # have to use subprocess
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
                            "climate_model": "Cicero-SCM",
                            "model": self.model,
                            "run_id": pamset["Index"],
                            "scenario": self.scen,
                            "region": ["World"],
                            "variable": [variable],
                            "unit": [unit],
                        },
                    )
                )

        self._cleanup_tempdirs()
        return run_append(runs)

    def _setup_tempdirs(self):
        """
        Set up temporary directories to run and make output in
        """
        self.rundir = tempfile.mkdtemp(prefix="ciceroscm-test-rundir-")
        dir_util.copy_tree(
            os.path.join(os.path.dirname(__file__), "utils_templates", "run-dir"),
            self.rundir,
        )

    def _cleanup_tempdirs(self):
        """
        Remove tempdirs after run
        """
        shutil.rmtree(self.rundir)

    def _make_dir_structure(self, scenario):
        """
        Make directory structure for a scenario in which to put input and
        outputfiles for the run
        """
        print(scenario)
        _ensure_dir_exists(self.rundir)
        _ensure_dir_exists(os.path.join(self.rundir, scenario))
        _ensure_dir_exists(os.path.join(self.rundir, scenario, "inputfiles"))
        _ensure_dir_exists(os.path.join(self.rundir, scenario, "outputfiles"))
