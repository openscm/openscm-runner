"""
Progress bar wrapper
"""

from tqdm.autonotebook import tqdm

# TODO: handle configuration in a consistent manner
_default_tqdm_params = {
    "mininterval": 5,
    "unit": "it",
    "unit_scale": True,
}


def progress(*args, **kwargs):
    """
    Progress bar

    Uses ``tqdm.autonotebook`` to automatically use a native Jupyter widget
    when executing within a Jupyer Notebook.

    Parameters
    ----------
    *args
        Passed to the tqdm

    **kwargs
        Passed to the tqdm

    Returns
    -------
    tqdm.auto_notebook.tqdm
        tqdm instance with consistent configuration
    """
    kwargs = {**_default_tqdm_params, **kwargs}
    return tqdm(*args, **kwargs)
