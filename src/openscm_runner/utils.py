"""
Utility functions
"""
import os

from scmdata import df_append


def get_env(env_var):
    """
    Get environment variable, if it is not set, raise an error

    Parameters
    ----------
    env_var : str
        Environment variable to get

    Returns
    -------
    Any
        Value of the environment variable

    Raises
    ------
    ValueError
        The environment variable is not set i.e. the output of
        ``os.getenv(env_var) is None``
    """
    if env_var not in os.environ:
        raise ValueError("{} is not set".format(env_var))

    return os.getenv(env_var)


def calculate_quantiles(
    scmdf,
    quantiles,
    process_over_columns=("run_id", "ensemble_member", "climate_model"),
):
    """
    Calculate quantiles of an :obj:`ScmDataFrame`

    Parameters
    ----------
    scmdf : :obj:`ScmDataFrame`
        :obj:`ScmDataFrame` containing the data from which to calculate the
        quantiles

    quantiles : list of float
        quantiles to calculate (must be in [0, 1])

    process_over_columns : list of str
        Columns to process over. All other columns in ``scmdf.meta`` will be
        included in the output.

    Returns
    -------
    :obj:`ScmDataFrame`
        :obj:`ScmDataFrame` containing the quantiles of interest, processed
        over ``process_over_columns``
    """
    out = []
    for quant in quantiles:
        quantile_df = scmdf.process_over(process_over_columns, "quantile", q=quant)
        quantile_df["quantile"] = quant

        out.append(quantile_df)

    out = df_append(out)

    return out
