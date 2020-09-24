"""
Rather than hard-coding constants, configuration can be source from 2 different
sources:

* Environment variables
* dotenv files

Environment variables are always used in preference to the values in dotenv
files.
"""


import os

from dotenv import dotenv_values, find_dotenv


class ConfigLoader:
    """
    Configuration container

    Loads a local dotenv file containing configuration. An example of a
    configuration file is provided in root of the project.

    A combination of environment variables and dotenv files can be used as
    configuration with an existing environment variables overriding a value
    specified in a dotenv file.

    All configuration is case-insensitive.

    .. code:: python

        >>> config = ConfigLoader()
        >>> config['VALUE']
        >>> config.get("VALUE", None)
    """

    def __init__(self):
        self._config = {}
        self.is_loaded = False

    def load_config(self):
        """
        Load configuration from disk

        A dotenv file is attempted to be loaded. The first file named .env
        in the current directory or any of its parents will read in.

        If no dotenv files are found, then
        """
        dotenv_cfg = dotenv_values(find_dotenv(usecwd=True), verbose=True)
        self.update(dotenv_cfg)

        # Add any extra files here

        self.is_loaded = True

    def get(self, key, default=None):
        """
        Get value for a given key, falling back to a default value if not present.

        Parameters
        ----------
        key : str
            Key

        default: Any
            Default value returned if no configuration for ``key`` is present.

        Returns
        -------
        Any
            Value with key ``item``. If not value is present ``default``
            is returned.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key):
        """
        Get a config value for a given key

        Parameters
        ----------
        key: str
            Key

        Returns
        -------
        Any
            Value with key ``item``

        Raises
        ------
        KeyError
            No configuration values for the key were found
        """
        if not self.is_loaded:
            # Lazy loaded
            self.load_config()
        key = key.upper()

        # Always preference environment variable
        if key in os.environ:
            return os.environ[key]

        # Fall back to loaded config
        # Preference determined by load order
        if key in self._config:
            return self._config[key]

        # Raise KeyError if not found
        raise KeyError(key)

    def update(self, conf):
        """
        Update the configuration

        If configuration with duplicate keys already exists, then these values
        will overwrite the existing values.

        Parameters
        ----------
        conf: dict
        """
        conf = {k.upper(): v for k, v in conf.items()}
        self._config.update(conf)


config = ConfigLoader()
