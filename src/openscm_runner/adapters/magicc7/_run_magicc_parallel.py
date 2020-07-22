"""
Module for running MAGICC in parallel
"""
import logging
import multiprocessing
import os.path
from concurrent.futures import ProcessPoolExecutor
from subprocess import CalledProcessError

import f90nml
import pandas as pd
from scmdata import ScmDataFrame

from ...utils import get_env
from ._magicc_instances import _MagiccInstances
from ._parallel_process import _parallel_process

LOGGER = logging.getLogger(__name__)


def _inject_pymagicc_compatible_magcfg_user(magicc):
    """
    Overwrite ``magicc.run_dir / MAGCFG_USER.CFG`` with config that only point to ``MAGTUNE_PYMAGICC.CFG``

    Parameters
    ----------
    magicc : :obj:`pymagicc.MAGICC7`
        Instance of :obj:`pymagicc.MAGICC7` to setup
    """
    LOGGER.info("Writing Pymagicc compatible MAGCFG_USER.CFG in %s", magicc.run_dir)
    with open(os.path.join(magicc.run_dir, "MAGCFG_USER.CFG"), "w") as file_handle:
        f90nml.write({"nml_allcfgs": {"file_tuningmodel_1": "PYMAGICC"}}, file_handle)


def _setup_func(magicc):
    LOGGER.info(
        "Setting up MAGICC worker in %s", magicc.root_dir,
    )

    magicc.set_config()

    _inject_pymagicc_compatible_magcfg_user(magicc)


def _init_magicc_worker(dict_shared_instances):
    LOGGER.debug("Initialising process %s", multiprocessing.current_process())
    LOGGER.debug("Existing instances %s", dict_shared_instances)
    magicc_instances = _MagiccInstances(  # noqa: F841 # pylint:disable=unused-variable
        dict_shared_instances
    )


def _run_func(magicc, cfg):
    try:
        scenario = cfg.pop("scenario")
        model = cfg.pop("model")

        res = magicc.run(**cfg)
        if res.metadata["stderr"]:
            LOGGER.info("magicc run stderr: %s", res.metadata["stderr"])
            LOGGER.info("cfg: %s", cfg)

        res.set_meta(scenario, "scenario")
        res.set_meta(model, "model")
        res.set_meta(cfg["run_id"], "run_id")

        return res
    except CalledProcessError as exc:
        # Swallow the exception, but return None
        LOGGER.debug("magicc run failed: %s", exc.stderr)
        LOGGER.debug("cfg: %s", cfg)

        return None


def _execute_run(cfg, run_func, setup_func, instances):
    magicc = instances.get(
        root_dir=get_env("MAGICC_WORKER_ROOT_DIR"),
        init_callback=setup_func,
        init_callback_kwargs={},
    )

    return run_func(magicc, cfg)


def run_magicc_parallel(
    cfgs, output_vars,
):
    """
    Run MAGICC in parallel using compact out files

    Parameters
    ----------
    cfgs : list[dict]
        List of configurations with which to run MAGICC

    output_vars : list[str]
        Variables to output (may require some fiddling with ``out_x``
        variables in ``cfgs`` to get this right)

    Returns
    -------
    :obj:`ScmDataFrame`
        :obj:`ScmDataFrame` instance with all results.
    """
    LOGGER.info("Entered _parallel_magicc_compact_out")
    shared_manager = multiprocessing.Manager()
    shared_dict = shared_manager.dict()
    instances = _MagiccInstances(existing_instances=shared_dict)

    runs = [
        {
            "cfg": {**cfg, "only": output_vars},
            "run_func": _run_func,
            "setup_func": _setup_func,
            "instances": instances,
        }
        for cfg in cfgs
    ]

    try:
        pool = ProcessPoolExecutor(
            max_workers=int(get_env("MAGICC_WORKER_NUMBER")),
            initializer=_init_magicc_worker,
            initargs=(shared_dict,),
        )

        res = _parallel_process(
            func=_execute_run,
            configuration=runs,
            pool=pool,
            config_are_kwargs=True,
            front_serial=2,
            front_parallel=2,
        )

        LOGGER.info("Appending results into a single ScmRun")
        # not ideal using pandas for appending but ok as short-term hack
        res = ScmDataFrame(pd.concat([r.timeseries() for r in res if r is not None]))

    finally:
        instances.cleanup()
        LOGGER.info("Shutting down parallel pool")
        shared_manager.shutdown()
        pool.shutdown()

    return res
