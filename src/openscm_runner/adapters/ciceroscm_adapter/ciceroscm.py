"""
CICEROSCM adapter
"""
import logging
import os.path
from subprocess import check_output  # nosec

from ..base import _Adapter
from ._run_ciceroscm_parallel import run_ciceroscm_parallel

LOGGER = logging.getLogger(__name__)


class CICEROSCM(_Adapter):  # pylint: disable=too-few-public-methods
    """
    Adapter for CICEROSCM
    """

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

        runs = run_ciceroscm_parallel(scenarios, cfgs, output_variables)
        return runs

    @classmethod
    def get_version(cls):
        """
        Get the CICEROSCM version being used by this adapter

        Returns
        -------
        str
            The CICEROSCM version id

        Raises
        ------
        OSError
            The CICERO-SCM binary cannot be run on the operating system
        """
        exec_call = os.path.join(
            os.path.dirname(__file__), "utils_templates", "run_dir", "scm_vCH4fb"
        )
        try:
            check_output(exec_call)
        except OSError as orig_exc:
            raise OSError(
                "CICERO-SCM is not available on your operating system"
            ) from orig_exc

        return "v2019vCH4"
