"""
Base class for adapters
"""
from abc import ABC, abstractmethod


class _Adapter(ABC):  # pylint: disable=too-few-public-methods
    """
    Base class for adapters
    """

    def __init__(self, *args, **kwargs):
        """
        Initialise the adapter

        Parameters
        ----------
        *args
            Passed to the adapter's ``_init_model`` method

        **kwargs
            Passed to the adapter's ``_init_model`` method
        """
        self._init_model(*args, **kwargs)

    @abstractmethod
    def _init_model(self, *args, **kwargs):
        """
        Initialise the model

        Parameters
        ----------
        *args
            Arguments used to initialise the model

        **kwargs
            Keyword arguments used to initialise the model
        """
