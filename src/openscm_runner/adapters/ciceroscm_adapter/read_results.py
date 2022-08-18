"""
Module that reads in CICERO-SCM results
and returns data to append to SCMRun
"""
import os

import pandas as pd

from ..utils.cicero_utils.cicero_forcing_postprocessing_common import (
    get_data_from_forc_common,
    openscm_to_cscm_dict,
)


def get_data_from_conc_file(folder, variable, endyear):
    """
    Get data from concentration files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_conc.txt"), delimiter=r"\s+")
    years = df_temp.Year[: endyear - df_temp.Year[0] + 1]
    timeseries = df_temp[variable].to_numpy()[
        : len(years)
    ]  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_em_file(folder, variable, endyear):
    """
    Get data from emissions files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_em.txt"), delimiter=r"\s+")
    years = df_temp.Year[: endyear - df_temp.Year[0] + 1]
    timeseries = df_temp[variable].to_numpy()[
        : len(years)
    ]  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_temp_file(folder, variable, endyear):
    """
    Get data from temperature files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_temp.txt"), delimiter=r"\s+")
    years = df_temp.Year[: endyear - df_temp.Year[0] + 1]
    timeseries = df_temp[variable].to_numpy()[
        : len(years)
    ]  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_ohc_file(folder, variable, endyear):
    """
    Get data from ocean heat content files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_ohc.txt"), delimiter=r"\s+")
    years = df_temp.Year[: endyear - df_temp.Year[0] + 1]
    # Units are 10^22J and output should be 10^21J = ZJ
    conv_factor = 10.0
    timeseries = (
        df_temp[variable].to_numpy()[
            : len(years)
        ]  # pylint:disable=unsubscriptable-object
        * conv_factor
    )
    return years, timeseries


def get_data_from_rib_file(folder, variable, endyear):
    """
    Get data from rib files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_rib.txt"), delimiter=r"\s+")
    years = df_temp.Year[: endyear - df_temp.Year[0] + 1]
    timeseries = df_temp[variable].to_numpy()[
        : len(years)
    ]  # pylint:disable=unsubscriptable-object
    return years, timeseries


def convert_cicero_unit(cicero_unit):
    """
    Convert cicero unit convention for pint
    """
    return f"{cicero_unit.replace('_', '')} / yr"


class CSCMREADER:
    """
    Class to read CICERO-SCM output data
    """

    def __init__(self, odir, endyear):
        self.odir = odir
        self.variable_dict = openscm_to_cscm_dict
        self.temp_list = (
            "dT_glob",
            "dT_glob_air",
            "dT_glob_sea",
            "dSL(m)",
            "dSL_thermal(m)",
            "dSL_ice(m)",
        )
        self.ohc_list = "OHCTOT"
        self.volc_series = self.read_volc_series()
        self.sun_series = self.read_sun_series()
        self.endyear = endyear

    def read_volc_series(self):
        """
        Read volcanic forcing timeseries from input
        """
        vfile = os.path.join(self.odir, "input_RF", "RFVOLC", "meanVOLCmnd_ipcc_NH.txt")
        volc_series = pd.read_csv(
            vfile, sep="\t", usecols=[0], index_col=False, header=None
        )
        volc_series.index = range(1750, 2501)
        return volc_series

    def read_sun_series(self):
        """
        Read solar forcing timeseries from input
        """
        sfile = os.path.join(self.odir, "input_RF", "RFSUN", "solar_IPCC.txt")
        sun_series = pd.read_csv(sfile, sep="\t", index_col=False, header=None)
        sun_series.index = range(1750, 2501)
        return sun_series

    def read_variable_timeseries(self, scenario, variable, sfilewriter):
        """
        Read variable timeseries
        Connecting up to correct file type to get the data
        """
        folder = os.path.join(self.odir, scenario, "outputfiles")
        if variable not in self.variable_dict:
            return (
                pd.Series([], dtype="float64"),
                pd.Series([], dtype="float64"),
                "NoUnit",
            )
        if "Concentration" in variable:
            years, timeseries = get_data_from_conc_file(
                folder, self.variable_dict[variable], self.endyear
            )
            unit = sfilewriter.concunits[
                sfilewriter.components.index(self.variable_dict[variable])
            ]
        elif "Emissions" in variable:
            years, timeseries = get_data_from_em_file(
                folder, self.variable_dict[variable], self.endyear
            )
            unit = sfilewriter.units[
                sfilewriter.components.index(self.variable_dict[variable])
            ]
        elif "Forcing" in variable:
            years, timeseries = self.get_data_from_forc_file(
                folder, self.variable_dict[variable]
            )
            unit = "W/m^2"
        elif self.variable_dict[variable] in self.temp_list:
            years, timeseries = get_data_from_temp_file(
                folder, self.variable_dict[variable], self.endyear
            )
            unit = "K"
        elif self.variable_dict[variable] == "RIB_glob":
            years, timeseries = get_data_from_rib_file(
                folder, self.variable_dict[variable], self.endyear
            )
            unit = "W/m^2"

        elif self.variable_dict[variable] in self.ohc_list:
            years, timeseries = get_data_from_ohc_file(
                folder, self.variable_dict[variable], self.endyear
            )
            unit = "ZJ"
        return years, timeseries, unit

    def get_volc_forcing(self, startyear, endyear):
        """
        Return volcanic forcing time series from startyear up to and including endyear
        """
        return self.volc_series.iloc[
            startyear - 1750 : endyear - 1750 + 1
        ].values.flatten()

    def get_sun_forcing(self, startyear, endyear):
        """
        Return volcanic forcing time series from startyear up to and including endyear
        """
        return self.sun_series.iloc[
            startyear - 1750 : endyear - 1750 + 1
        ].values.flatten()

    def get_data_from_forc_file(self, folder, variable):
        """
        Get data from forcing files
        """
        df_temp = pd.read_csv(os.path.join(folder, "temp_forc.txt"), delimiter=r"\s+")
        years = df_temp.Year[: self.endyear - df_temp.Year[0] + 1]
        if variable == "Total_forcing+sunvolc":
            volc = self.get_volc_forcing(years.to_numpy()[0], years.to_numpy()[-1])
            sun = self.get_sun_forcing(years.to_numpy()[0], years.to_numpy()[-1])
            return get_data_from_forc_common(
                df_temp[: self.endyear - df_temp.Year[0] + 1],
                variable,
                self.variable_dict,
                volc,
                sun,
            )
        years, timeseries = get_data_from_forc_common(
            df_temp[: self.endyear - df_temp.Year[0] + 1], variable, self.variable_dict
        )
        return years, timeseries
