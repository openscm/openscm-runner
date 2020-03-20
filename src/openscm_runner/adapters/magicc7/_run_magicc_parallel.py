import logging
import multiprocessing
import os.path
from concurrent.futures import ProcessPoolExecutor
from subprocess import CalledProcessError

import f90nml
from scmdata import df_append

from ...utils import get_env
from ._magicc_instances import _MagiccInstances
from ._parallel_process import _parallel_process


logger = logging.getLogger(__name__)


def _inject_pymagicc_compatible_magcfg_user(magicc):
    """
    Overwrite ``magicc.run_dir / MAGCFG_USER.CFG`` with config that only point to ``MAGTUNE_PYMAGICC.CFG``

    Parameters
    ----------
    magicc : :obj:`pymagicc.MAGICC7`
        Instance of :obj:`pymagicc.MAGICC7` to setup

    Returns
    -------
    None
    """
    logger.info("Writing Pymagicc compatible MAGCFG_USER.CFG in %s", magicc.run_dir)
    with open(os.path.join(magicc.run_dir, "MAGCFG_USER.CFG"), "w") as fp:
        f90nml.write({"nml_allcfgs": {"file_tuningmodel_1": "PYMAGICC"}}, fp)


def _setup_func(magicc):
    logger.info(
        "Setting up MAGICC worker in %s", magicc.root_dir,
    )

    magicc.set_config()

    _inject_pymagicc_compatible_magcfg_user(magicc)


def _init_magicc_worker(dict_shared_instances):
    logger.debug("Initialising process %s", multiprocessing.current_process())
    logger.debug("Existing instances %s", dict_shared_instances)
    magicc_instances = _MagiccInstances(dict_shared_instances)


def _run_func(magicc, cfg):
    try:
        scenario = cfg.pop("scenario")
        model = cfg.pop("model")
        res = magicc.run(**cfg)
        res.set_meta(scenario, "scenario")
        res.set_meta(model, "model")
        res.set_meta(cfg["run_id"], "run_id")

        return res
    except CalledProcessError as e:
        # Swallow the exception, but return None
        logger.debug("magicc run failed: %s", e.stderr)
        logger.debug("cfg: %s", cfg)

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
    logger.info("Entered _parallel_magicc_compact_out")
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

        res = df_append([r for r in res if r is not None])

    finally:
        instances.cleanup()
        shared_manager.shutdown()
        pool.shutdown()

    return res
