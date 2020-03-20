"""
High-level run function
"""
from dotenv import load_dotenv, find_dotenv
from tqdm.autonotebook import tqdm

from .adapters import MAGICC7


# is this the right place to put this...
load_dotenv(find_dotenv(), verbose=True)


def run(climate_models_cfgs, scenarios, full_config=False):
    """
    Run a number of climate models over a number of scenarios

    Parameters
    ----------
    climate_models_cfgs : dict
        Dictionary where each key is a model and each value is the configs
        with which to run the model.

    scenarios : :obj:`pyam.IamDataFrame`
        Scenarios to run

    full_config : bool
        Include the configuration used to run each model in the output's
        metadata

    Returns
    -------
    :obj:`pyam.IamDataFrame`
        Model output plus the input timeseries
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

        model_res = runner.run(scenarios, cfgs)
        res.append(model_res)

    raise NotImplementedError("Fancy business to make sure pyam doesn't drop columns")
