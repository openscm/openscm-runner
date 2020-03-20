import logging
import time
from concurrent.futures import as_completed

from tqdm.autonotebook import tqdm

logger = logging.getLogger(__name__)


def _run_serial(func, configs, config_are_kwargs, notebook, desc):
    logger.debug("Entering _run_serial")

    if config_are_kwargs:
        logger.debug("Treating config as kwargs")
        res = [func(**a) for a in tqdm(configs, desc="Front serial")]
    else:
        logger.debug("Treating config as args")
        res = [func(a) for a in tqdm(configs, desc="Front serial")]

    logger.debug("Exiting _run_serial")
    return res


def _run_parallel(
    pool, timeout, func, configs, config_are_kwargs, notebook, desc, bar_start
):
    logger.debug("Entering _run_parallel")

    if config_are_kwargs:
        logger.debug("Treating config as kwargs")
        futures = [pool.submit(func, **a) for a in configs]
    else:
        logger.debug("Treating config as args")
        futures = [pool.submit(func, a) for a in configs]

    kwargs_tqdm = {
        "total": len(futures),
        "unit": "it",
        "unit_scale": True,
        "desc": desc,
    }

    logger.debug("Waiting for jobs to complete")
    for i, future in tqdm(
        enumerate(as_completed(futures, timeout=timeout)), **kwargs_tqdm
    ):
        if future.exception() is not None:
            time.sleep(2)  # let buffer flush out
            print(
                "One of the processes failed, see error below (was something "
                "unable to be pickled?)"
            )
            raise future.exception()

        logger.debug("Job %s completed", i + bar_start)

    res = []

    logger.debug("Collecting results")
    for i, future in enumerate(futures):
        try:
            res.append(future.result())
            logger.debug("Retrived result %s", i + bar_start)
        except Exception as e:
            logger.debug("Retrieving result %s failed", i + bar_start)
            res.append(e)

    logger.debug("Exiting _run_parallel")
    return res


def _parallel_process(
    func,
    configuration,
    pool=None,
    config_are_kwargs=False,
    front_serial=3,
    front_parallel=2,
    notebook=True,
    timeout=None,
):
    """
    A parallel version of the map function with a progress bar.

    Adapted from http://danshiebler.com/2016-09-14-parallel-progress-bar/

    Parameters
    ----------
    func : function
        A function to apply to each set of arguments in ``configuration``

    configuration : sequence
        An array of configuration with which to run ``func``.

    pool : :obj:`concurrent.futures.ProcessPoolExecutor`
        Pool in which to execute the jobs. If ``None``, the jobs will be executed
        serially in a single process (useful for debugging and benchmarking).

    config_are_kwargs : bool
        Are the elements of ``configuration`` intended to be used as keyword arguments
        when calling ``func``.

    front_serial : int
        The number of iterations to run serially before kicking off the parallel job.
        Useful for debugging.

    front_parallel : int
        The number of initial iterations to run parallel before kicking off the rest
        of the parallel jobs. Useful for debugging (especially if pickling is
        possible).

    notebook : bool
        Are we running in a notebook (required to make progress bars appear nicely)?

    timeout : float, int
        How long to wait for processes to complete before timing out. If ``None``, there is no timeout limit.

    Returns
    -------
    sequence
        Results of calling ``func`` with each configuration in ``configuration``
    """
    front_serial_res = []
    if front_serial > 0:
        logger.debug("Running front serial jobs")
        front_serial_res = _run_serial(
            func=func,
            configs=configuration[:front_serial],
            config_are_kwargs=config_are_kwargs,
            notebook=notebook,
            desc="Front serial",
        )

    if pool is None:
        logger.info("No pool provided, running rest of the jobs serially and returning")
        rest = _run_serial(
            func=func,
            configs=configuration[front_serial:],
            config_are_kwargs=config_are_kwargs,
            notebook=notebook,
            desc="Serial runs",
        )

        return rest + front_serial_res

    front_parallel_res = []
    if front_parallel > 0:
        logger.debug("Running front parallel jobs")
        front_parallel_res = _run_parallel(
            pool=pool,
            timeout=timeout,
            func=func,
            configs=configuration[front_serial : front_serial + front_parallel],
            config_are_kwargs=config_are_kwargs,
            notebook=notebook,
            desc="Front parallel",
            bar_start=front_serial,
        )

    logger.debug("Running rest of parallel jobs")
    rest = _run_parallel(
        pool=pool,
        timeout=timeout,
        func=func,
        configs=configuration[front_serial + front_parallel :],
        config_are_kwargs=config_are_kwargs,
        notebook=notebook,
        desc="Parallel runs",
        bar_start=front_serial + front_parallel,
    )

    return front_serial_res + front_parallel_res + rest
