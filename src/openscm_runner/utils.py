"""
Utility functions
"""
import scmdata


def calculate_quantiles(
    scmdf,
    quantiles,
    process_over_columns=("run_id", "ensemble_member", "climate_model"),
):
    """
    Calculate quantiles of an :obj:`ScmRun`

    Parameters
    ----------
    scmdf : :obj:`ScmRun`
        :obj:`ScmRun` containing the data from which to calculate the
        quantiles

    quantiles : list of float
        quantiles to calculate (must be in [0, 1])

    process_over_columns : list of str
        Columns to process over. All other columns in ``scmdf.meta`` will be
        included in the output.

    Returns
    -------
    :obj:`ScmRun`
        :obj:`ScmRun` containing the quantiles of interest, processed
        over ``process_over_columns``
    """
    out = []
    for quant in quantiles:
        quantile_df = scmdf.process_over(process_over_columns, "quantile", q=quant)
        quantile_df["quantile"] = quant

        out.append(quantile_df)

    out = scmdata.run_append([scmdata.ScmRun(o) for o in out])

    return out
