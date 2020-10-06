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

    def run(self, scenarios, cfgs, output_variables, output_config):
        """
        Parameters
        ----------
        scenarios : :obj:`pyam.IamDataFrame`
            Scenarios to run

        cfgs : list[dict]
            The config with which to run the model

        output_variables : list[str]
            Variables to include in the output

        output_config : tuple[str]
            Configuration to include in the output

        Returns
        -------
        :obj:`ScmRun`
            Model output
        """
        return self._run(scenarios, cfgs, output_variables, output_config)

    @abstractmethod
    def _run(self, scenarios, cfgs, output_variables, output_config):
        """
        Run the model.

        This method is the internal implementation of the :meth:`run` interface
        """
