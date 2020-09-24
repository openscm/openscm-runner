"""
Configuration

Environment variables are

"""


import os

from dotenv import dotenv_values


class ConfigLoader(object):
    """Store the configuration for the application

    Attempts to load a dotenv file.



    Configuration values are stored on disk as YAML. An example of a configuration file is provided in root of the project.

    >>> config = ConfigLoader()
    >>> config['value']
    """

    def __init__(self):
        self._config = {}
        self.is_loaded = False

    def load_config(self):
        # Load dotenv file
        dotenv_cfg = dotenv_values(verbose=True)
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
            Default value returned if no configuration for `key` is present.

        Returns
        -------
        Value with key `item`. If not value is present `default` is returned.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key):
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
        conf = {k.upper(): v for k, v in conf.items()}
        self._config.update(conf)


config = ConfigLoader()
