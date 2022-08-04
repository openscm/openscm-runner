"""
Utility functions for CICERO-SCM adapter
"""
import os
import platform


def _get_unique_index_values(idf, index_col, assert_all_same=True):
    """
    Get unique values in index column from a dataframe

    Parameters
    ----------
    idf : :obj:`pd.DataFrame`
        Dataframe to get index values from

    index_col : str
        Column in index to get the values for

    assert_all_same : bool
        Should we assert that all the values are the same before
        returning? If True, only a single value is returned. If
        False, a list is returned.

    Returns
    -------
    str, list
        Values found, either a string or a list depending on
        ``assert_all_same``.

    Raises
    ------
    AssertionError
        ``assert_all_same`` is True and there's more than one
        unique value.
    """
    out = idf.index.get_level_values(index_col).unique().tolist()
    if assert_all_same:
        if len(out) > 1:
            raise AssertionError(out)

        return out[0]

    return out


def _get_executable(rundir):
    """
    Get the right executable for the operating system
    """
    if platform.system() == "Windows":
        executable = os.path.join(rundir, "scm_vCH4fb_bfx.exe")
    else:
        executable = os.path.join(rundir, "scm_vCH4fb_bfx")
    return executable
