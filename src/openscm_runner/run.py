"""
High-level run function
"""
import pyam
import scmdata
from dotenv import find_dotenv, load_dotenv
from tqdm.autonotebook import tqdm

from .adapters import MAGICC7

# is this the right place to put this...
load_dotenv(find_dotenv(), verbose=True)


def run(
    climate_models_cfgs,
    scenarios,
    output_variables=("Surface Temperature",),
    full_config=False,
):
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

    full_config : bool
        Include the configuration used to run each model in the output's
        metadata

    Returns
    -------
    :obj:`pyam.IamDataFrame`
        Model output

    Raises
    ------
    NotImplementedError
        ``full_config`` is ``True``, we haven't worked out how this should
        behave yet.
    """
    if full_config:
        raise NotImplementedError("Returning full config is not yet implemented")

    res = []
    for climate_model, cfgs in tqdm(climate_models_cfgs.items(), desc="Climate models"):
        if climate_model == "MAGICC7":
            runner = MAGICC7()
        else:
            raise NotImplementedError(
                "No adapter available for {}".format(climate_model)
            )

        model_res = runner.run(scenarios, cfgs, output_variables=output_variables)
        res.append(model_res)

    for i, model_res in enumerate(res):
        if i < 1:
            key_meta = model_res.meta.columns.tolist()

        assert model_res.meta.columns.tolist() == key_meta

    scmdf = scmdata.df_append(res)
    assert (
        not scmdf.meta.isna().any().any()
    ), "something will be dropped when casting to IamDataFrame"

    return pyam.IamDataFrame(
        pyam.IamDataFrame(scmdf.timeseries()).swap_time_for_year().data
    )
