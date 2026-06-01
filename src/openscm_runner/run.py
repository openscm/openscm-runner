"""
High-level run function.
"""
import logging
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor

import scmdata

from ._run_mode import RunMode
from ._variables import check_variables_are_as_expected
from .adapters import get_adapter
from .adapters._protocol import AdapterLike
from .progress import progress

LOGGER = logging.getLogger(__name__)


def _check_out_config(out_config, climate_models_cfgs):
    if out_config is not None:
        unknown_models = set(out_config.keys()) - set(climate_models_cfgs.keys())
        if unknown_models:
            LOGGER.warning(
                "Found model(s) in `out_config` which are not in "
                "`climate_models_cfgs`: %s",
                unknown_models,
            )

        for key, value in out_config.items():
            if not isinstance(value, tuple):
                raise TypeError(
                    f"`out_config` values must be tuples, this isn't the case for "
                    f"climate_model: '{key}'"
                )


def _run_one_adapter(climate_model, adapter, scenarios):
    """
    Run a single pre-configured adapter.

    Defined at module level so it can be pickled and dispatched to a
    :class:`concurrent.futures.ProcessPoolExecutor` worker when
    ``parallel_models=True`` is set on :func:`run`. ``climate_model``
    is carried alongside the adapter so worker results can be
    labelled.
    """
    return adapter.run(scenarios)


def run(
    climate_models_cfgs,
    scenarios,
    output_variables=("Surface Temperature",),
    out_config=None,
    parallel_models=True,
    max_model_workers=8,
    mode=RunMode.EMISSIONS_DRIVEN,
):  # pylint: disable=W9006,too-many-arguments,too-many-branches,too-many-locals
    """
    Run a number of climate models over a number of scenarios.

    Parameters
    ----------
    climate_models_cfgs : dict[str: list[dict]] or list[AdapterLike]
        Either:

        * The legacy dict form: each key is a model name and each
          value is a list of cfg dicts. The wrapper looks the model
          up in the adapter registry and constructs it with the
          cfgs, ``mode``, ``output_variables`` and ``out_config``
          entry for that model.
        * A list of pre-constructed :class:`AdapterLike` instances.
          Each adapter is run on the scenarios directly; cfgs and
          mode are read from the adapter's own state. Useful when
          the adapter needs configuration that doesn't fit the dict
          form, e.g. ``FAIR2.from_native_distribution(...)``.

    scenarios : :obj:`pyam.IamDataFrame`
        Scenarios to run.

    output_variables : list[str]
        Variables to include in the output. Ignored when
        ``climate_models_cfgs`` is a list (each adapter carries its
        own output_variables in that case).

    out_config : dict[str: tuple of str]
        Dictionary where each key is a model and each value is a
        tuple of configuration values to include in the output's
        metadata. Only supported with the dict form.

    parallel_models : bool
        If ``True`` (default), dispatch the requested climate models
        to a top-level :class:`concurrent.futures.ProcessPoolExecutor`
        so they run concurrently. If ``False``, run them serially in
        the calling process; useful for debugging.

    max_model_workers : int
        Cap on the number of top-level worker processes used when
        ``parallel_models=True``.

    mode : :class:`RunMode`
        Driving mode applied to every adapter constructed from the
        dict form. Defaults to :attr:`RunMode.EMISSIONS_DRIVEN`.
        Ignored when ``climate_models_cfgs`` is a list (each
        pre-constructed adapter carries its own mode).

    Returns
    -------
    :obj:`scmdata.ScmRun`
        Model output.

    Raises
    ------
    KeyError
        ``out_config`` has keys which are not in ``climate_models_cfgs``.

    TypeError
        A value in ``out_config`` is not a :obj:`tuple`, or
        ``climate_models_cfgs`` is neither a mapping nor an iterable
        of adapter instances.

    ValueError
        ``scenarios`` carries an emissions variable name that is not
        in :data:`openscm_runner.KNOWN_EMISSIONS_VARIABLES`.
    """
    if scenarios is not None:
        try:
            scenarios_variables = scenarios.get_unique_meta("variable")
        except AttributeError:
            scenarios_variables = list(getattr(scenarios, "variable", []))
        check_variables_are_as_expected(scenarios_variables)

    if isinstance(climate_models_cfgs, Mapping):
        _check_out_config(out_config, climate_models_cfgs)
        model_tasks = []
        for climate_model, cfgs in climate_models_cfgs.items():
            if out_config is not None and climate_model in out_config:
                output_config_cm = out_config[climate_model]
                LOGGER.debug(
                    "Using output config: %s for %s",
                    output_config_cm,
                    climate_model,
                )
            else:
                LOGGER.debug("No output config for %s", climate_model)
                output_config_cm = None
            adapter = get_adapter(
                climate_model,
                cfgs=cfgs,
                mode=mode,
                output_variables=output_variables,
                output_config=output_config_cm,
            )
            model_tasks.append((climate_model, adapter, scenarios))
    else:
        if out_config is not None:
            raise ValueError(
                "`out_config` is only supported with the dict form of "
                "`climate_models_cfgs`. When passing pre-constructed "
                "adapter instances, set ``output_config`` on each "
                "adapter at construction time instead."
            )
        try:
            adapter_iter = iter(climate_models_cfgs)
        except TypeError as exc:
            raise TypeError(
                "`climate_models_cfgs` must be either a dict "
                "(model name to cfg list) or an iterable of "
                f"AdapterLike instances; got {type(climate_models_cfgs).__name__}."
            ) from exc
        model_tasks = []
        for adapter in adapter_iter:
            if not isinstance(adapter, AdapterLike):
                raise TypeError(
                    "`climate_models_cfgs` entry does not match the "
                    "AdapterLike protocol (no `.run(scenarios)` method): "
                    f"{type(adapter).__name__}"
                )
            climate_model = getattr(adapter, "model_name", None) or type(
                adapter
            ).__name__
            model_tasks.append((climate_model, adapter, scenarios))

    if parallel_models and len(model_tasks) > 1:
        n_workers = min(len(model_tasks), max_model_workers)
        LOGGER.info(
            "Running %d climate models in parallel with %d top-level workers",
            len(model_tasks),
            n_workers,
        )
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(_run_one_adapter, *task) for task in model_tasks]
            res = [f.result() for f in futures]
    else:
        if parallel_models:
            LOGGER.debug("Only one climate model requested, dispatching serially")
        else:
            LOGGER.info(
                "Running %d climate models serially (parallel_models=False)",
                len(model_tasks),
            )
        res = [
            _run_one_adapter(*task)
            for task in progress(model_tasks, desc="Climate models")
        ]

    for i, model_res in enumerate(res):
        if i < 1:
            key_meta = set(model_res.meta.columns.tolist())

        model_meta = set(model_res.meta.columns.tolist())
        climate_model = model_res.get_unique_meta("climate_model")
        if model_meta != key_meta:
            raise AssertionError(
                f"{climate_model} meta: {model_meta}, expected meta: {key_meta}"
            )

    if len(res) == 1:
        LOGGER.info("Only one model run, returning its results")
        scmdf = res[0]
    else:
        LOGGER.info("Appending model results")
        scmdf = scmdata.run_append(res)

    return scmdf
