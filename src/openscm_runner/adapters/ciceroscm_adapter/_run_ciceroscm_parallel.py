"""
Module for running CICEROSCM in parallel
"""
import logging
import os
from concurrent.futures import ProcessPoolExecutor

import scmdata

from ...settings import config
from ..utils._parallel_process import _parallel_process
from .ciceroscm_wrapper import CiceroSCMWrapper

LOGGER = logging.getLogger(__name__)


def _execute_run(cfgs, output_variables, scenariodata):
    cscm = CiceroSCMWrapper(scenariodata)

    return cscm.run_over_cfgs(cfgs, output_variables)


def run_ciceroscm_parallel(scenarios, cfgs, output_vars):
    """
    Run CICEROSCM in parallel

    Parameters
    ----------
    scenarios : IamDataFrame
        Scenariodata with which to run

    cfgs : list[dict]
        List of configurations with which to run CICEROSCM

    output_vars : list[str]
        Variables to output (may require some fiddling with ``out_x``
        variables in ``cfgs`` to get this right)

    Returns
    -------
    :obj:`ScmRun`
        :obj:`ScmRun` instance with all results.
    """
    LOGGER.info("Entered _parallel_ciceroscm")
    print(config.get("CICEROSCM_WORKER_NUMBER", os.cpu_count()))
    runs = [
        {
            "cfgs": cfgs,
            "output_variables": output_vars,
            "scenariodata": smdf,  # IamDataFrame(smdf),
        }
        for (scen, model), smdf in scenarios.timeseries().groupby(["scenario", "model"])
    ]

    try:
        pool = ProcessPoolExecutor(
            max_workers=4,  # int(config.get("CICEROSCM_WORKER_NUMBER", os.cpu_count())),
            # initializer=_init_ciceroscm_worker,
            # initargs=(shared_dict,),
        )

        result = _parallel_process(
            func=_execute_run,
            configuration=runs,
            pool=pool,
            config_are_kwargs=True,
            front_serial=2,
            front_parallel=2,
        )

        LOGGER.info("Appending Cicero-SCM results into a single ScmRun")
        result = scmdata.run_append([r for r in result if r is not None])

    finally:
        LOGGER.info("Shutting down parallel pool")
        pool.shutdown()

    return result
