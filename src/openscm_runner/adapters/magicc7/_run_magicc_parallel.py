"""
Module for running MAGICC in parallel
"""
import logging
import multiprocessing
import os.path
import tempfile
import typing
from concurrent.futures import ProcessPoolExecutor
from subprocess import CalledProcessError  # nosec

import scmdata

from ...settings import config
from ..utils._parallel_process import _parallel_process
from ._compat import f90nml, pymagicc
from ._magicc_instances import _MagiccInstances

LOGGER = logging.getLogger(__name__)


class TemporaryDirectoryIfNeeded:
    """
    A temporary directory context manager which works like
    tempfile.TemporaryDirectory but supports existing directories.

    If instantiated without a directory, behaves exactly like
    tempfile.TemporaryDirectory. If instantiated with an explicit directory
    name, will use this directory instead and will *not* delete the directory
    when exiting the context.
    """

    def __init__(self, tempdir: typing.Union[None, str] = None, **kwargs):
        if tempdir is None:
            # pylint: disable-next=consider-using-with
            self._td = tempfile.TemporaryDirectory(**kwargs)
        else:
            self._td = None
            self._tempdir = tempdir

    def __enter__(self) -> str:
        """Create temporary directory if needed."""
        if self._td is None:
            return self._tempdir
        return self._td.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Delete directory if temporary directory was created."""
        if self._td is not None:
            self._td.__exit__(exc_type, exc_val, exc_tb)

    def __repr__(self):
        """Human-readable representation."""
        if self._td is None:
            return f"<TemporaryDirectoryIfNeeded {self._tempdir}>"
        return repr(self._td)

    def cleanup(self):
        """
        Delete the temporary directory if it was created.

        Does not delete the directory if an existing directory was used.
        """
        if self._td is not None:
            self._td.cleanup()


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
        "Setting up MAGICC worker in %s",
        magicc.root_dir,
    )

    magicc.set_config()

    _inject_pymagicc_compatible_magcfg_user(magicc)


def _init_magicc_worker(dict_shared_instances):
    LOGGER.debug("Initialising process %s", multiprocessing.current_process())
    LOGGER.debug("Existing instances %s", dict_shared_instances)
    magicc_instances = _MagiccInstances(  # noqa: F841 # pylint:disable=unused-variable
        dict_shared_instances
    )


def _run_func(
    magicc: "pymagicc.MAGICC7", cfg: typing.Dict[str, typing.Any]
) -> typing.Union[None, typing.Dict[str, typing.Any]]:
    try:
        scenario = cfg.pop("scenario")
        model = cfg.pop("model")
        output_config = cfg.pop("output_config")

        res = magicc.run(**cfg)
        if res.metadata["stderr"]:
            LOGGER.warning("magicc run stderr: %s", res.metadata["stderr"])
            LOGGER.info("cfg: %s", cfg)

        res["scenario"] = scenario
        res["model"] = model
        res["run_id"] = cfg["run_id"]
        if output_config is not None:
            magicc_out_cfg = res.metadata["parameters"]["allcfgs"]
            for k in output_config:
                res[k] = cfg[k]
                if k in magicc_out_cfg and magicc_out_cfg[k] != cfg[k]:
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
        LOGGER.error("magicc run failed: %s", exc.stderr)
        LOGGER.debug("cfg: %s", cfg)

        return None


def _execute_run(
    cfg: typing.Dict[str, typing.Any],
    run_func: typing.Callable[
        ["pymagicc.MAGICC7", typing.Dict[str, typing.Any]],
        typing.Union[None, typing.Dict[str, typing.Any]],
    ],
    setup_func: typing.Callable,
    instances: _MagiccInstances,
    root_dir: str,
):
    magicc = instances.get(
        root_dir=root_dir,
        init_callback=setup_func,
        init_callback_kwargs={},
    )

    return run_func(magicc, cfg)


def run_magicc_parallel(
    cfgs: typing.Iterable[typing.Dict[str, typing.Any]],
    output_vars: typing.Iterable[str],
    output_config: typing.Iterable[str],
):
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

    with TemporaryDirectoryIfNeeded(
        tempdir=config.get("MAGICC_WORKER_ROOT_DIR", None)
    ) as root_dir:
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
                "root_dir": root_dir,
            }
            for cfg in cfgs
        ]

        max_workers = int(
            config.get("MAGICC_WORKER_NUMBER", multiprocessing.cpu_count())
        )
        LOGGER.info("Running in parallel with up to %d workers", max_workers)
        pool = ProcessPoolExecutor(  # need to handle shared_manager too
            max_workers=max_workers,
            initializer=_init_magicc_worker,
            initargs=(shared_dict,),
        )
        try:
            res = _parallel_process(
                func=_execute_run,
                configuration=runs,
                pool=pool,
                config_are_kwargs=True,
                front_serial=2,
                front_parallel=2,
            )

            LOGGER.info("Appending results into a single ScmRun")
            return scmdata.run_append([r for r in res if r is not None])

        finally:
            instances.cleanup()
            LOGGER.info("Shutting down parallel pool")
            shared_manager.shutdown()
            pool.shutdown()
