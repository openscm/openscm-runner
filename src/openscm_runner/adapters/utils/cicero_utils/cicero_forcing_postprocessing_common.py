"""
Module with common values and methods
for postprocessing output
from both CICERO-SCM implementations
particularly making forcing sums
to avoid code duplication
"""
import numpy as np

openscm_to_cscm_dict = {
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


def get_data_from_forc_common(df_temp, variable, v_dict, volc=0, sun=0):
    """
    Get or calculate forcing when dataframe with forcers
    variable and variable dictionary
    If calculating with volcanic and solar forcing
    methods to obtain these need to be supplied
    """
    years = df_temp.Year[:]
    if variable in forc_sums:
        timeseries = np.zeros(len(years))
        for comp, value in v_dict.items():
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
        timeseries = timeseries + volc
        timeseries = timeseries + sun
    else:
        timeseries = df_temp[variable].to_numpy()
    return years, timeseries
