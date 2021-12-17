"""
Module that reads in CICERO-SCM results
and returns data to append to SCMRun
"""
import os
import re

import numpy as np
import pandas as pd


def get_data_from_conc_file(folder, variable):
    """
    Get data from concentration files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_conc.txt"), delimiter=r"\s+")
    years = df_temp.Year[:]
    timeseries = df_temp[variable].to_numpy()  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_em_file(folder, variable):
    """
    Get data from emissions files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_em.txt"), delimiter=r"\s+")
    years = df_temp.Year[:]
    timeseries = df_temp[variable].to_numpy()  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_temp_file(folder, variable):
    """
    Get data from temperature files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_temp.txt"), delimiter=r"\s+")
    years = df_temp.Year[:]
    timeseries = df_temp[variable].to_numpy()  # pylint:disable=unsubscriptable-object
    return years, timeseries


def get_data_from_ohc_file(folder, variable):
    """
    Get data from ocean heat content files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_ohc.txt"), delimiter=r"\s+")
    years = df_temp.Year[:]
    # Units are 10^22J and output should be 10^21J = ZJ
    conv_factor = 10.0
    timeseries = (
        df_temp[variable].to_numpy()  # pylint:disable=unsubscriptable-object
        * conv_factor
    )
    return years, timeseries


def get_data_from_rib_file(folder, variable):
    """
    Get data from rib files
    """
    df_temp = pd.read_csv(os.path.join(folder, "temp_rib.txt"), delimiter=r"\s+")
    years = df_temp.Year[:]
    timeseries = df_temp[variable].to_numpy()  # pylint:disable=unsubscriptable-object
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

    def __init__(self, odir):
        self.odir = odir
        self.variable_dict = {
            "Surface Air Temperature Change": "dT_glob_air",
            # GMST
            "Surface Air Ocean Blended Temperature Change": "dT_glob",
            # ERFs
            "Effective Radiative Forcing": "Total_forcing+sunvolc",
            "Effective Radiative Forcing|Anthropogenic": "Total_forcing",
            "Effective Radiative Forcing|Aerosols": "Aerosols",
            "Effective Radiative Forcing|Aerosols|Direct Effect": "Aerosols|Direct Effect",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC": "BC",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC": "OC",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx": "SO2",
            "Effective Radiative Forcing|Aerosols|Indirect Effect": "SO4_IND",
            "Effective Radiative Forcing|Greenhouse Gases": "GHG",
            "Effective Radiative Forcing|F-Gases": "Fgas",
            "Effective Radiative Forcing|HFC125": "HFC125",
            "Effective Radiative Forcing|HFC134a": "HFC134a",
            "Effective Radiative Forcing|HFC143a": "HFC143a",
            "Effective Radiative Forcing|HFC227ea": "HFC227ea",
            "Effective Radiative Forcing|HFC23": "HFC23",
            "Effective Radiative Forcing|HFC245fa": "HFC245fa",
            "Effective Radiative Forcing|HFC32": "HFC32",
            "Effective Radiative Forcing|HFC4310mee": "HFC4310mee",
            "Effective Radiative Forcing|CF4": "CF4",
            "Effective Radiative Forcing|C6F14": "C6F14",
            "Effective Radiative Forcing|C2F6": "C2F6",
            "Effective Radiative Forcing|SF6": "SF6",
            "Effective Radiative Forcing|CO2": "CO2",
            "Effective Radiative Forcing|CH4": "CH4",
            "Effective Radiative Forcing|N2O": "N2O",
            "Emissions|CO2": "CO2",
            "Emissions|CH4": "CH4",
            "Emissions|N2O": "N2O",
            # Heat uptake
            "Heat Uptake": "RIB_glob",
            "Heat Content|Ocean": "OHCTOT",
            # concentrations
            "Atmospheric Concentrations|CO2": "CO2",
            "Atmospheric Concentrations|CH4": "CH4",
            "Atmospheric Concentrations|N2O": "N2O",
        }
        self.rib_list = "RIB_glob"
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
        folder = os.path.join(
            self.odir, re.sub("[^a-zA-Z0-9_-]", "", scenario)[:50], "outputfiles"
        )
        if variable not in self.variable_dict:
            return (
                pd.Series([], dtype="float64"),
                pd.Series([], dtype="float64"),
                "NoUnit",
            )
        if "Concentration" in variable:
            years, timeseries = get_data_from_conc_file(
                folder, self.variable_dict[variable]
            )
            unit = sfilewriter.concunits[
                sfilewriter.components.index(self.variable_dict[variable])
            ]
        elif "Emissions" in variable:
            years, timeseries = get_data_from_em_file(
                folder, self.variable_dict[variable]
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
                folder, self.variable_dict[variable]
            )
            unit = "K"
        elif self.variable_dict[variable] in self.rib_list:
            years, timeseries = get_data_from_rib_file(
                folder, self.variable_dict[variable]
            )
            unit = "W/m^2"

        elif self.variable_dict[variable] in self.ohc_list:
            years, timeseries = get_data_from_ohc_file(
                folder, self.variable_dict[variable]
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
        forc_sums = ["Aerosols", "Aerosols|Direct Effect"]
        fgas_list = [
            "CFC-11",
            "CFC-12",
            "CFC-113",
            "CFC-114",
            "CFC-115",
            "CH3Br",
            "CCl4",
            "CH3CCl3",
            "HCFC-22",
            "HCFC-141b",
            "HCFC-123",
            "HCFC-142b",
            "H-1211",
            "H-1301",
            "H-2402",
            "HFC125",
            "HFC134a",
            "HFC143a",
            "HFC227ea",
            "HFC23",
            "HFC245fa",
            "HFC32",
            "HFC4310mee",
            "C2F6",
            "C6F14",
            "CF4",
            "SF6",
        ]
        ghg_not_fgas = ["CO2", "CH4", "N2O", "TROP_O3", "STRAT_O3", "STRAT_H2O"]

        df_temp = pd.read_csv(os.path.join(folder, "temp_forc.txt"), delimiter=r"\s+")
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
            timeseries = timeseries + self.get_volc_forcing(
                years.to_numpy()[0], years.to_numpy()[-1]
            )
            timeseries = timeseries + self.get_sun_forcing(
                years.to_numpy()[0], years.to_numpy()[-1]
            )
        else:
            timeseries = df_temp[variable].to_numpy()
        return years, timeseries
