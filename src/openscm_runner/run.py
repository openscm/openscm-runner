"""
High-level run function
"""
import logging

import scmdata

from .adapters import CICEROSCM, FAIR, MAGICC7
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


def run(
    climate_models_cfgs,
    scenarios,
    output_variables=("Surface Temperature",),
    out_config=None,
):  # pylint: disable=W9006
    """
    Run a number of climate models over a number of scenarios

    Parameters
    ----------
    climate_models_cfgs : dict[str: list]
        Dictionary where each key is a model and each value is the configs
        with which to run the model. The configs are passed to the model
        adapter.

    scenarios : :obj:`pyam.IamDataFrame`
        Scenarios to run

    output_variables : list[str]
        Variables to include in the output

    out_config : dict[str: tuple of str]
        Dictionary where each key is a model and each value is a tuple of
        configuration values to include in the output's metadata.

    Returns
    -------
    :obj:`scmdata.ScmRun`
        Model output

    Raises
    ------
    KeyError
        ``out_config`` has keys which are not in ``climate_models_cfgs``

    TypeError
        A value in ``out_config`` is not a :obj:`tuple`
    """
    _check_out_config(out_config, climate_models_cfgs)

    res = []
    for climate_model, cfgs in progress(
        climate_models_cfgs.items(), desc="Climate models"
    ):
        if climate_model == "MAGICC7":
            runner = MAGICC7()
        elif climate_model.upper() == "FAIR":  # allow various capitalisations
            runner = FAIR()
        elif climate_model.upper() == "CICEROSCM":  # allow various capitalisations
            runner = CICEROSCM()
        else:
            raise NotImplementedError(f"No adapter available for {climate_model}")

        if out_config is not None and climate_model in out_config:
            output_config_cm = out_config[climate_model]
            LOGGER.debug(
                "Using output config: %s for %s", output_config_cm, climate_model
            )
        else:
            LOGGER.debug("No output config for %s", climate_model)
            output_config_cm = None

        model_res = runner.run(
            scenarios,
            cfgs,
            output_variables=output_variables,
            output_config=output_config_cm,
        )
        res.append(model_res)

    for i, model_res in enumerate(res):
        if i < 1:
            key_meta = set(model_res.meta.columns.tolist())

        model_meta = set(model_res.meta.columns.tolist())
        climate_model = model_res.get_unique_meta("climate_model")
        if model_meta != key_meta:  # noqa
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
