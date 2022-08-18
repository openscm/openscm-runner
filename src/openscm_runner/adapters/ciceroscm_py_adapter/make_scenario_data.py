"""
Module with functionality to make emission input files
"""

# TODO: optimise to speed up reading and writing

import logging
import os

import pandas as pd

from ..utils.cicero_utils.make_scenario_common import COMMONSFILEWRITER

LOGGER = logging.getLogger(__name__)


def _read_ssp245_em(ssp245_em_file):
    """
    Get default data from ssp245_RCMIP
    """
    ssp245df = (
        pd.read_csv(ssp245_em_file, delimiter="\t", index_col=0, skiprows=[1, 2, 3])
        .rename(columns=lambda x: x.strip())
        .rename(columns={"CO2 .1": "CO2_AFOLU"})
        .rename(columns={"CO2": "CO2_FF"})
        .astype(float)
    )

    return ssp245df


class SCENARIODATAGETTER(COMMONSFILEWRITER):
    """
    Class to write scenariofiles:
    """

    def __init__(self, udir, syear=2015, eyear=2100):
        """
        Intialise scenario data getter
        """
        super().__init__(udir, syear, eyear)
        self.ssp245data = _read_ssp245_em(os.path.join(udir, "ssp245_em_RCMIP.txt"))

    def get_scenario_data(self, scenarioframe, nystart):
        """
        Get printoutframe, and adding ssp245 data to
        get a frame for running
        """
        printout_frame = self.make_printoutframe(scenarioframe, self.ssp245data)
        printout_frame.rename(
            columns={"CO2_lu": "CO2_AFOLU", "CO2": "CO2_FF"}, inplace=True
        )
        final_frame = pd.concat(
            [
                self.ssp245data.iloc[nystart - 1750 : (self.years[0] - 1750)]
                .astype(float)
                .rename(columns={"Component": "Index"}),
                printout_frame,
            ]
        )
        return final_frame
