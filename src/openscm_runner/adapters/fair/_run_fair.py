"""
Module for running FaIR
"""
import numpy as np
from fair.forward import fair_scm
from scmdata import ScmDataFrame, df_append


def run_fair(cfgs, output_vars):
    """
    Run FaIR
    Parameters
    ----------
    cfgs : list[dict]
        List of configurations with which to run FaIR
    output_vars : list[str]
        Variables to output
    Returns
    -------
    :obj:`ScmDataFrame`
        :obj:`ScmDataFrame` instance with all results.
    """
    res = []

    for cfg in cfgs:
        scenario = cfg.pop("scenario")
        model = cfg.pop("model")
        data, unit = _process_output(fair_scm(**cfg), output_vars)

        tempres = ScmDataFrame(
            data,
            columns={
                "scenario": scenario,
                "model": model,
                "region": ["unspecified"],
                "variable": list(data.keys()),
                "unit": list(unit.values()),
            },
        )
        tempres.__setitem__("time", np.arange(1765, 2101))

        res.append(tempres)

    res = df_append(res)

    return res


def _process_output(fair_output, output_vars):
    """
    Make sense of FaIR1.6 output
    Parameters
    ----------
    fair_output:
        7-tuple of C, F, T, lambda_eff, ohc, heatflux, airborne_emissions:
            C : np.ndarray
                (nt, 31) array of greenhouse gas concentrations
            F : np.ndarray
                (nt, 41) array of effective radiative forcings
            T : np.ndarray
                (nt,) array of temperature
            lambda_eff: np.ndarray
                effective climate feedback
            ohc : np.ndarray
                total ocean heat uptake
            heatflux:
                heat transfer into the ocean
            airborne_emissions:
                atmospheric carbon content
    output_vars:
        List of output variables
    Returns
    -------
    data:
        dict of climate model output
    unit:
        dict of units corresponding to data
    """
    C, F, T, lambda_eff, ohc, heatflux, airborne_emissions = fair_output

    data = {}
    unit = {}

    data["Atmospheric Concentrations|CO2"] = C[:, 0]
    data["Atmospheric Concentrations|CH4"] = C[:, 1]
    data["Atmospheric Concentrations|N2O"] = C[:, 2]
    data["Atmospheric Concentrations|F-Gases|PFC|CF4"] = C[:, 3]
    data["Atmospheric Concentrations|F-Gases|PFC|C2F6"] = C[:, 4]
    data["Atmospheric Concentrations|F-Gases|PFC|C6F14"] = C[:, 5]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC23"] = C[:, 6]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC32"] = C[:, 7]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC125"] = C[:, 8]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC134a"] = C[:, 9]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC143a"] = C[:, 10]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC227ea"] = C[:, 11]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC245fa"] = C[:, 12]
    data["Atmospheric Concentrations|F-Gases|HFC|HFC4310mee"] = C[:, 13]
    data["Atmospheric Concentrations|F-Gases|SF6"] = C[:, 14]
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC11"] = C[:, 15]
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC12"] = C[:, 16]
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC113"] = C[:, 17]
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC114"] = C[:, 18]
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC115"] = C[:, 19]
    data["Atmospheric Concentrations|Montreal Gases|CCl4"] = C[:, 20]
    data["Atmospheric Concentrations|Montreal Gases|CH3CCl3"] = C[:, 21]
    data["Atmospheric Concentrations|Montreal Gases|HCFC22"] = C[:, 22]
    data["Atmospheric Concentrations|Montreal Gases|HCFC141b"] = C[:, 23]
    data["Atmospheric Concentrations|Montreal Gases|HCFC142b"] = C[:, 24]
    data["Atmospheric Concentrations|Montreal Gases|Halon1211"] = C[:, 25]
    data["Atmospheric Concentrations|Montreal Gases|Halon1202"] = C[:, 26]
    data["Atmospheric Concentrations|Montreal Gases|Halon1301"] = C[:, 27]
    data["Atmospheric Concentrations|Montreal Gases|Halon2402"] = C[:, 28]
    data["Atmospheric Concentrations|Montreal Gases|CH3Br"] = C[:, 29]
    data["Atmospheric Concentrations|Montreal Gases|CH3Cl"] = C[:, 30]
    data["Effective Radiative Forcing|CO2"] = F[:, 0]
    data["Effective Radiative Forcing|CH4"] = F[:, 1]
    data["Effective Radiative Forcing|N2O"] = F[:, 2]
    data["Effective Radiative Forcing|CF4"] = F[:, 3]
    data["Effective Radiative Forcing|C2F6"] = F[:, 4]
    data["Effective Radiative Forcing|C6F14"] = F[:, 5]
    data["Effective Radiative Forcing|HFC23"] = F[:, 6]
    data["Effective Radiative Forcing|HFC32"] = F[:, 7]
    data["Effective Radiative Forcing|HFC125"] = F[:, 8]
    data["Effective Radiative Forcing|HFC134a"] = F[:, 9]
    data["Effective Radiative Forcing|HFC143a"] = F[:, 10]
    data["Effective Radiative Forcing|HFC227ea"] = F[:, 11]
    data["Effective Radiative Forcing|HFC245fa"] = F[:, 12]
    data["Effective Radiative Forcing|HFC4310mee"] = F[:, 13]
    data["Effective Radiative Forcing|F-Gases|SF6"] = F[:, 14]
    data["Effective Radiative Forcing|CFC11"] = F[:, 15]
    data["Effective Radiative Forcing|CFC12"] = F[:, 16]
    data["Effective Radiative Forcing|CFC113"] = F[:, 17]
    data["Effective Radiative Forcing|CFC114"] = F[:, 18]
    data["Effective Radiative Forcing|CFC115"] = F[:, 19]
    data["Effective Radiative Forcing|CCl4"] = F[:, 20]
    data["Effective Radiative Forcing|CH3CCl3"] = F[:, 21]
    data["Effective Radiative Forcing|HCFC22"] = F[:, 22]
    data["Effective Radiative Forcing|HCFC141b"] = F[:, 23]
    data["Effective Radiative Forcing|HCFC142b"] = F[:, 24]
    data["Effective Radiative Forcing|Halon1211"] = F[:, 25]
    data["Effective Radiative Forcing|Halon1202"] = F[:, 26]
    data["Effective Radiative Forcing|Halon1301"] = F[:, 27]
    data["Effective Radiative Forcing|Halon2402"] = F[:, 28]
    data["Effective Radiative Forcing|CH3Br"] = F[:, 29]
    data["Effective Radiative Forcing|CH3Cl"] = F[:, 30]
    data["Effective Radiative Forcing|Tropospheric Ozone"] = F[:, 31]
    data["Effective Radiative Forcing|Stratospheric Ozone"] = F[:, 32]
    data["Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O"] = F[:, 33]
    data["Effective Radiative Forcing|Contrails"] = F[:, 34]
    data["Effective Radiative Forcing|Aerosols|Direct Effect"] = F[:, 35]
    data["Effective Radiative Forcing|Aerosols|Indirect Effect"] = F[:, 36]
    data["Effective Radiative Forcing|Black Carbon on Snow"] = F[:, 37]
    data["Effective Radiative Forcing|Land-use Change"] = F[:, 38]
    data["Effective Radiative Forcing|Volcanic"] = F[:, 39]
    data["Effective Radiative Forcing|Solar"] = F[:, 40]
    data["Effective Radiative Forcing"] = np.sum(F, axis=1)
    data["Effective Radiative Forcing|Anthropogenic"] = np.sum(F[:, :39], axis=1)
    data["Effective Radiative Forcing|Greenhouse Gases"] = np.sum(F[:, :31], axis=1)
    # This definition does not include ozone and H2O from CH4 oxidation
    data["Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"] = np.sum(
        F[:, :15], axis=1
    )
    data["Effective Radiative Forcing|CO2, CH4 and N2O"] = np.sum(F[:, :3], axis=1)
    data["Effective Radiative Forcing|F Gases"] = np.sum(F[:, 3:15], axis=1)
    data["Effective Radiative Forcing|Montreal Protocol Halogen Gases"] = np.sum(
        F[:, 15:31], axis=1
    )
    data["Surface Temperature"] = T
    data["Airborne Fraction"] = airborne_emissions
    data["Effective Climate Feedback"] = lambda_eff
    data["Ocean Heat Uptake"] = ohc
    data["Net Energy Imbalance"] = heatflux

    unit["Atmospheric Concentrations|CO2"] = "ppm"
    unit["Atmospheric Concentrations|CH4"] = "ppb"
    unit["Atmospheric Concentrations|N2O"] = "ppb"
    unit["Atmospheric Concentrations|F-Gases|PFC|CF4"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|PFC|C2F6"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|PFC|C6F14"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC23"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC32"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC125"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC134a"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC143a"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC227ea"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC245fa"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|HFC|HFC4310mee"] = "ppt"
    unit["Atmospheric Concentrations|F-Gases|SF6"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CFC|CFC11"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CFC|CFC12"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CFC|CFC113"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CFC|CFC114"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CFC|CFC115"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CCl4"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CH3CCl3"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|HCFC22"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|HCFC141b"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|HCFC142b"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|Halon1211"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|Halon1202"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|Halon1301"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|Halon2402"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CH3Br"] = "ppt"
    unit["Atmospheric Concentrations|Montreal Gases|CH3Cl"] = "ppt"
    unit["Effective Radiative Forcing|CO2"] = "W/m**2"
    unit["Effective Radiative Forcing|CH4"] = "W/m**2"
    unit["Effective Radiative Forcing|N2O"] = "W/m**2"
    unit["Effective Radiative Forcing|CF4"] = "W/m**2"
    unit["Effective Radiative Forcing|C2F6"] = "W/m**2"
    unit["Effective Radiative Forcing|C6F14"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC23"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC32"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC125"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC134a"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC143a"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC227ea"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC245fa"] = "W/m**2"
    unit["Effective Radiative Forcing|HFC4310mee"] = "W/m**2"
    unit["Effective Radiative Forcing|F-Gases|SF6"] = "W/m**2"
    unit["Effective Radiative Forcing|CFC11"] = "W/m**2"
    unit["Effective Radiative Forcing|CFC12"] = "W/m**2"
    unit["Effective Radiative Forcing|CFC113"] = "W/m**2"
    unit["Effective Radiative Forcing|CFC114"] = "W/m**2"
    unit["Effective Radiative Forcing|CFC115"] = "W/m**2"
    unit["Effective Radiative Forcing|CCl4"] = "W/m**2"
    unit["Effective Radiative Forcing|CH3CCl3"] = "W/m**2"
    unit["Effective Radiative Forcing|HCFC22"] = "W/m**2"
    unit["Effective Radiative Forcing|HCFC141b"] = "W/m**2"
    unit["Effective Radiative Forcing|HCFC142b"] = "W/m**2"
    unit["Effective Radiative Forcing|Halon1211"] = "W/m**2"
    unit["Effective Radiative Forcing|Halon1202"] = "W/m**2"
    unit["Effective Radiative Forcing|Halon1301"] = "W/m**2"
    unit["Effective Radiative Forcing|Halon2402"] = "W/m**2"
    unit["Effective Radiative Forcing|CH3Br"] = "W/m**2"
    unit["Effective Radiative Forcing|CH3Cl"] = "W/m**2"
    unit["Effective Radiative Forcing|Tropospheric Ozone"] = "W/m**2"
    unit["Effective Radiative Forcing|Stratospheric Ozone"] = "W/m**2"
    unit["Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O"] = "W/m**2"
    unit["Effective Radiative Forcing|Contrails"] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols|Direct Effect"] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols|Indirect Effect"] = "W/m**2"
    unit["Effective Radiative Forcing|Black Carbon on Snow"] = "W/m**2"
    unit["Effective Radiative Forcing|Land-use Change"] = "W/m**2"
    unit["Effective Radiative Forcing|Volcanic"] = "W/m**2"
    unit["Effective Radiative Forcing|Solar"] = "W/m**2"
    unit["Effective Radiative Forcing"] = "W/m**2"
    unit["Effective Radiative Forcing|Anthropogenic"] = "W/m**2"
    unit["Effective Radiative Forcing|Greenhouse Gases"] = "W/m**2"
    unit["Effective Radiative Forcing|Kyoto Gases"] = "W/m**2"
    unit["Effective Radiative Forcing|CO2, CH4 and N2O"] = "W/m**2"
    unit["Effective Radiative Forcing|F Gases"] = "W/m**2"
    unit["Effective Radiative Forcing|Montreal Protocol Halogen Gases"] = "W/m**2"
    unit["Surface Temperature"] = "K"
    unit["Airborne Fraction"] = "dimensionless"
    unit["Effective Climate Feedback"] = "W/m**2/K"
    unit["Ocean Heat Uptake"] = "J"
    unit["Net Energy Imbalance"] = "W/m**2"

    return (
        {key: data[key] for key in output_vars},
        {key: unit[key] for key in output_vars},
    )
