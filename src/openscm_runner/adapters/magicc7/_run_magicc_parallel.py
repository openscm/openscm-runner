"""
Module for running MAGICC in parallel
"""
import logging
import multiprocessing
import os.path
from concurrent.futures import ProcessPoolExecutor
from subprocess import CalledProcessError  # nosec

import scmdata

from ...settings import config
from ..utils._parallel_process import _parallel_process
from ._compat import f90nml, pymagicc
from ._magicc_instances import _MagiccInstances

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
    with open(
        os.path.join(magicc.run_dir, "MAGCFG_USER.CFG"), "w", encoding="ascii"
    ) as file_handle:
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
        output_config = cfg.pop("output_config")

        res = magicc.run(**cfg)
        if res.metadata["stderr"]:
            LOGGER.info("magicc run stderr: %s", res.metadata["stderr"])
            LOGGER.info("cfg: %s", cfg)

        res["scenario"] = scenario
        res["model"] = model
        res["run_id"] = cfg["run_id"]
        if output_config is not None:
            magicc_out_cfg = res.metadata["parameters"]["allcfgs"]
            for k in output_config:
                res[k] = cfg[k]
                if k in magicc_out_cfg:
                    if magicc_out_cfg[k] != cfg[k]:
                        LOGGER.warning(
                            "Parameter: %s. "
                            "MAGICC input config (via OpenSCM-Runner): %s. "
                            "MAGICC output config: %s.",
                            k,
                            cfg[k],
                            magicc_out_cfg[k],
                        )

        return res
    except CalledProcessError as exc:
        # Swallow the exception, but return None
        LOGGER.debug("magicc run failed: %s", exc.stderr)
        LOGGER.debug("cfg: %s", cfg)

        return None


def _execute_run(cfg, run_func, setup_func, instances):
    magicc = instances.get(
        root_dir=config["MAGICC_WORKER_ROOT_DIR"],
        init_callback=setup_func,
        init_callback_kwargs={},
    )

    return run_func(magicc, cfg)


def run_magicc_parallel(cfgs, output_vars, output_config):
    """
    Run MAGICC in parallel using compact out files

    Parameters
    ----------
    cfgs : list[dict]
        List of configurations with which to run MAGICC

    output_vars : list[str]
        Variables to output

    output_config : tuple[str]
        Configuration to include in the output

    Returns
    -------
    :obj:`ScmRun`
        :obj:`ScmRun` instance with all results.
    """
    LOGGER.info("Entered _parallel_magicc_compact_out")
    shared_manager = multiprocessing.Manager()
    shared_dict = shared_manager.dict()
    instances = _MagiccInstances(existing_instances=shared_dict)

    magicc_internal_vars = [
        f"DAT_{pymagicc.definitions.convert_magicc7_to_openscm_variables(v, inverse=True)}"
        for v in output_vars
    ]

    runs = [
        {
            "cfg": {
                **cfg,
                "only": output_vars,
                "out_dynamic_vars": magicc_internal_vars,
                "output_config": output_config,
            },
            "run_func": _run_func,
            "setup_func": _setup_func,
            "instances": instances,
        }
        for cfg in cfgs
    ]

    try:
        max_workers = int(
            config.get("MAGICC_WORKER_NUMBER", multiprocessing.cpu_count())
        )
        LOGGER.info("Running in parallel with up to %d workers", max_workers)
        pool = ProcessPoolExecutor(  # need to handle shared_manager too
            max_workers=max_workers,
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
        res = scmdata.run_append([r for r in res if r is not None])

    finally:
        instances.cleanup()
        LOGGER.info("Shutting down parallel pool")
        shared_manager.shutdown()
        pool.shutdown()

    return res
