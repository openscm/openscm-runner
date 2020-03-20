"""
Utility functions
"""
import os


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
