import os
from subprocess import check_output

import pymagicc

from .base import _Adapter


class MAGICC7(_Adapter):
    """
    Adapter for running MAGICC7
    """

    def __init__(self):
        """
        Initialise the MAGICC7 adapter
        """
        self.magicc = pymagicc.MAGICC7()
        """:obj:`pymagicc.MAGICC7`: Pymagicc class instance used to run MAGICC"""
        import pdb

        pdb.set_trace()

    @classmethod
    def get_version(cls):
        """
        Get the MAGICC7 version being used by this adapter

        Returns
        -------
        str
            The MAGICC7 version id
        """
        return check_output([cls._executable(), "--version"]).decode("utf-8").strip()

    @classmethod
    def _executable(cls):
        exe = os.getenv("MAGICC_EXECUTABLE_7")
        if exe is None:
            raise ValueError("environment variable MAGICC_EXECUTABLE_7 is not set")

        return exe
