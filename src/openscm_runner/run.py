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
from .progress import progress

LOGGER = logging.getLogger(__name__)


def _check_out_config(out_config, known_models):
    if out_config is not None:
        unknown_models = set(out_config.keys()) - set(known_models)
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


def _looks_like_adapter(value):
    """Duck-type test: pre-constructed adapter vs. a cfg list."""
    return callable(getattr(value, "run", None))


def _normalise_entries(climate_models_cfgs):
    """Coerce dict or iterable input into ``[(name, value), ...]`` pairs."""
    if isinstance(climate_models_cfgs, Mapping):
        return list(climate_models_cfgs.items())
    entries = []
    for item in climate_models_cfgs:
        if _looks_like_adapter(item):
            name = getattr(item, "model_name", None)
            if name is None:
                raise TypeError(
                    "Adapter instance is missing a `model_name` attribute: "
                    f"{type(item).__name__}."
                )
            entries.append((name, item))
        else:
            name, value = item  # expect a (name, cfgs) tuple
            entries.append((name, value))
    return entries


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
    climate_models_cfgs : dict or iterable
        Per-model run requests. Two equivalent shapes, freely
        mixable within a single call:

        * ``dict[str, list[dict] | adapter]``: each key is a model
          name. Values that are a cfg list are looked up in the
          registry and constructed with the dict-level ``mode`` /
          ``output_variables`` / ``out_config[key]``. Values that
          are a pre-constructed adapter instance are run on the
          scenarios directly (cfgs and mode read off the adapter).
        * Iterable of entries, each either a pre-constructed
          adapter instance or a ``(model_name, cfgs_list)`` tuple.
          Same semantics as the dict shape, applied per entry.

    scenarios : :obj:`pyam.IamDataFrame`
        Scenarios to run.

    output_variables : list[str]
        Variables to include in the output. Used only for entries
        whose value is a cfg list; ignored for entries whose value
        is a pre-constructed adapter.

    out_config : dict[str: tuple of str]
        Dictionary where each key is a model and each value is a
        tuple of configuration values to include in the output's
        metadata. Only meaningful for entries whose value is a cfg
        list.

    parallel_models : bool
        If ``True`` (default), dispatch the requested climate models
        to a top-level :class:`concurrent.futures.ProcessPoolExecutor`
        so they run concurrently. If ``False``, run them serially in
        the calling process; useful for debugging.

    max_model_workers : int
        Cap on the number of top-level worker processes used when
        ``parallel_models=True``.

    mode : :class:`RunMode`
        Driving mode applied to every adapter constructed from a cfg
        list. Defaults to :attr:`RunMode.EMISSIONS_DRIVEN`. Ignored
        for pre-constructed adapter entries (each carries its own
        mode).

    Returns
    -------
    :obj:`scmdata.ScmRun`
        Model output.

    Raises
    ------
    KeyError
        ``out_config`` has keys which are not in ``climate_models_cfgs``.

    TypeError
        A value in ``out_config`` is not a :obj:`tuple`.

    ValueError
        ``scenarios`` is ``None``, or carries an emissions variable
        name that is not in
        :data:`openscm_runner.KNOWN_EMISSIONS_VARIABLES`.
    """
    # Validation order: cfg-shape -> scenarios -> adapter construction.
    # User-input errors fire before package-import errors so callers
    # get the most specific error for the way their call is wrong.
    entries = _normalise_entries(climate_models_cfgs)
    _check_out_config(out_config, {name for name, _ in entries})

    if scenarios is None:
        raise ValueError("`scenarios` is required; got None.")
    check_variables_are_as_expected(scenarios.get_unique_meta("variable"))

    model_tasks = []
    for climate_model, value in entries:
        if _looks_like_adapter(value):
            model_tasks.append((climate_model, value, scenarios))
            continue
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
            cfgs=value,
            mode=mode,
            output_variables=output_variables,
            output_config=output_config_cm,
        )
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
