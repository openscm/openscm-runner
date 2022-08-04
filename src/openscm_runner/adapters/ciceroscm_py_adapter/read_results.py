"""
Module that reads in CICERO-SCM results
and returns data to append to SCMRun
"""
import numpy as np
import pandas as pd

from ..utils._common_cicero_utils import (
    fgas_list,
    forc_sums,
    ghg_not_fgas,
    openscm_to_cscm_dict,
)


def get_data_from_conc(results, variable):
    """
    Get data from concentration files
    """
    df_temp = results["concentrations"]
    years = df_temp.Year[:]
    timeseries = df_temp[variable].to_numpy()  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_em(results, variable):
    """
    Get data from emissions files
    """
    df_temp = results["emissions"]
    years = df_temp.Year[:]
    timeseries = df_temp[variable].to_numpy()  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_temp_or_rib(results, variable):
    """
    Get data for temperature or rib variables
    """
    return results[variable]


def get_data_from_ohc(results, variable):
    """
    Get data from ocean heat content files
    """
    df_temp = results[variable]
    # Units are 10^22J and output should be 10^21J = ZJ
    conv_factor = 10.0
    timeseries = df_temp * conv_factor  # pylint:disable=unsubscriptable-object
    return timeseries


def convert_cicero_unit(cicero_unit):
    """
    Convert cicero unit convention for pint
    """
    return f"{cicero_unit.replace('_', '')} / yr"


class CSCMREADER:
    """
    Class to read CICERO-SCM output data
    """

    def __init__(self, nystart, nyend):
        self.variable_dict = openscm_to_cscm_dict
        self.variable_dict[
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx"
        ] = "SO4_DIR"
        self.temp_list = (
            "dT_glob",
            "dT_glob_air",
            "dT_glob_sea",
            "dSL(m)",
            "dSL_thermal(m)",
            "dSL_ice(m)",
            "RIB_glob",
        )
        self.ohc_list = "OHCTOT"
        self.indices = np.arange(nystart, nyend + 1)

    def get_variable_timeseries(self, results, variable, sfilewriter):
        """
        Get variable timeseries
        Connecting up to correct data dictionary to get data
        """
        if variable not in self.variable_dict:
            return (
                pd.Series([], dtype="float64"),
                pd.Series([], dtype="float64"),
                "NoUnit",
            )
        if "Concentration" in variable:
            years, timeseries = get_data_from_conc(
                results, self.variable_dict[variable]
            )
            unit = sfilewriter.concunits[
                sfilewriter.components.index(self.variable_dict[variable])
            ]
        elif "Emissions" in variable:
            years, timeseries = get_data_from_em(results, self.variable_dict[variable])
            unit = sfilewriter.units[
                sfilewriter.components.index(self.variable_dict[variable])
            ]
        elif "Forcing" in variable:
            years, timeseries = self.get_data_from_forc(
                results, self.variable_dict[variable]
            )
            unit = "W/m^2"
        elif self.variable_dict[variable] in self.temp_list:
            timeseries = get_data_from_temp_or_rib(
                results, self.variable_dict[variable]
            )
            years = self.indices
            if self.variable_dict[variable] == "RIB_glob":
                unit = "W/m^2"
            else:
                unit = "K"

        elif self.variable_dict[variable] in self.ohc_list:
            timeseries = get_data_from_ohc(results, self.variable_dict[variable])
            years = self.indices
            unit = "ZJ"

        return years, timeseries, unit

    def get_volc_forcing(self, results):
        """
        Return volcanic forcing time series from startyear up to and including endyear
        """
        volc_series = pd.Series(
            (results["Volcanic_forcing_NH"] + results["Volcanic_forcing_SH"]) / 2
        )
        volc_series.index = self.indices  # TODO get correct time rang
        return volc_series

    def get_sun_forcing(self, results):
        """
        Return volcanic forcing time series from startyear up to and including endyear
        """
        sun_series = pd.Series(results["Solar_forcing"])
        sun_series.index = self.indices
        return sun_series

    def get_data_from_forc(self, results, variable):
        """
        Get data from forcing files
        """
        df_temp = results["forcing"]
        years = df_temp.Year[:]
        if variable in forc_sums:
            timeseries = np.zeros(len(years))
            for comp, value in self.variable_dict.items():
                if variable in comp and value not in forc_sums:
                    timeseries = timeseries + df_temp[value].to_numpy()
        elif variable in ("Fgas", "GHG"):
            timeseries = np.zeros(len(years))
            for comp in fgas_list:
                timeseries = timeseries + df_temp[comp].to_numpy()
            if variable == "GHG":
                for comp in ghg_not_fgas:
                    timeseries = timeseries + df_temp[comp].to_numpy()
        elif variable == "Total_forcing+sunvolc":
            timeseries = df_temp["Total_forcing"].to_numpy()
            timeseries = timeseries + self.get_volc_forcing(results)
            timeseries = timeseries + self.get_sun_forcing(results)
        else:
            timeseries = df_temp[variable].to_numpy()
        return years, timeseries
