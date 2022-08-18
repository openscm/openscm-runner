"""
CICEROSCMPY adapter
"""
import logging

from ..base import _Adapter
from ..utils.cicero_utils._run_ciceroscm_parallel import run_ciceroscm_parallel
from ._compat import cscmpy
from .cscmpy_wrapper import CSCMPYWrapper

LOGGER = logging.getLogger(__name__)


def _execute_run(cfgs, output_variables, scenariodata):
    cscm = CSCMPYWrapper(scenariodata)
    try:
        out = cscm.run_over_cfgs(cfgs, output_variables)
    finally:
        LOGGER.info("Finished run")
    return out


class CICEROSCMPY(_Adapter):  # pylint: disable=too-few-public-methods
    """
    Adapter for CICEROSCM python version
    """

    model_name = "CiceroSCMPY"

    def __init__(self):  # pylint: disable=useless-super-delegation
        """
        Initialise the CICEROSCM adapter

        """
        super().__init__()

    def _init_model(self):  # pylint: disable=arguments-differ
        pass

    def _run(self, scenarios, cfgs, output_variables, output_config):
        """
        Run the model.

        This method is the internal implementation of the :meth:`run` interface

        cfgs is a list of indices to run
        """
        if output_config is not None:
            raise NotImplementedError("`output_config` not implemented for CICERO-SCM")

        runs = run_ciceroscm_parallel(scenarios, cfgs, output_variables, _execute_run)
        return runs

    @classmethod
    def get_version(cls):
        """
        Get the CICEROSCM version being used by this adapter

        Returns
        -------
        str
            The CICEROSCM version id
        """
        return cscmpy.__version__
