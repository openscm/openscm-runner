"""
Module with functionality to make emission input files
"""

# TODO: optimise to speed up reading and writing

import logging
import os

import numpy as np
import pandas as pd

from ..utils.cicero_utils.make_scenario_common import COMMONSFILEWRITER

LOGGER = logging.getLogger(__name__)


def _read_ssp245_em(ssp245_em_file):
    """
    Get default data from ssp245_RCMIP
    """
    ssp245df = (
        pd.read_csv(ssp245_em_file, delimiter="\t", index_col=0)
        .rename(columns=lambda x: x.strip())
        .rename(index=lambda x: x.strip())
        .rename(columns={"CO2 .1": "CO2_lu"})
    )

    return ssp245df


class SCENARIOFILEWRITER(COMMONSFILEWRITER):
    """
    Class to write scenariofiles:
    """

    def __init__(self, udir):
        """
        Intialise scenario file writer
        """
        super().__init__(udir)
        self.ssp245data = _read_ssp245_em(os.path.join(udir, "ssp245_em_RCMIP.txt"))

    def get_top_of_file(self, ssp245_em_file):
        """
        Get the top of the emission file which will be equal for all scenarios
        """
        with open(ssp245_em_file, encoding="ascii") as semfile:
            filedata = semfile.read()
            top_of_file = filedata.split(f"\n{self.years[0]}")[0]

        return top_of_file

    def write_scenario_data(self, scenarioframe, odir, scenario):
        """
        Take a scenariodataframe
        and writing out necessary emissions files
        """
        fname = os.path.join(
            odir,
            "inputfiles",
            f"{scenario}_em.txt",
        )
        printout_frame = self.make_printoutframe(
            scenarioframe, self.ssp245data
        ).reset_index()
        printout_frame_fmt = ["%d"] + ["%.8f"] * (printout_frame.shape[1] - 1)

        with open(fname, "w", encoding="ascii") as sfile:
            sfile.write(
                self.get_top_of_file(os.path.join(self.udir, "ssp245_em_RCMIP.txt"))
            )
            sfile.write("\n")
            np.savetxt(sfile, printout_frame, fmt=printout_frame_fmt, delimiter=" \t ")
