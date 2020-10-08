"""
Module for running FaIR
"""
import logging

import numpy as np
from fair.constants.general import EARTH_RADIUS, SECONDS_PER_YEAR
import fair.version_two.emissions_driven as fair_scm
from scmdata import ScmRun, run_append

LOGGER = logging.getLogger(__name__)
toa_to_joule = 4 * np.pi * EARTH_RADIUS ** 2 * SECONDS_PER_YEAR


def run_fair(cfgs, output_vars):  # pylint: disable=R0914
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
    :obj:`ScmRun`
        :obj:`ScmRun` instance with all results.
    """
    res = []

    for cfg in cfgs:
        scenario = cfg.pop("scenario")
        model = cfg.pop("model")
        run_id = cfg.pop("run_id")
        factors = {}
        factors["gmst"] = cfg.pop("gmst_factor")
        factors["ohu"] = cfg.pop("ohu_factor")
        data, unit, nt = _process_output(fair_scm(**cfg), output_vars, factors)

        data_scmrun = []
        variables = []
        units = []
        for key, variable in data.items():
            variables.append(key)
            data_scmrun.append(variable)
            units.append(unit[key])

        tempres = ScmRun(
            np.vstack(data_scmrun).T,
            index=np.arange(1765, 1765 + nt),
            columns={
                "scenario": scenario,
                "model": model,
                "region": "World",
                "variable": variables,
                "unit": units,
                "run_id": run_id,
            },
        )

        res.append(tempres)

    res = run_append(res)

    return res


def _process_output(fair_output, output_vars, factors):
    """
    Make sense of FaIR2.0 output

    Parameters
    ----------
    fair_output :  dict
        Dictionary of Emissions, Concentrations, Radiative Forcing, Temperature and Alpha
            emissions : :obj:`pd.DataFrame`
                Pandas DataFrame giving timeseries of GHG emissions
            C :
                Pandas DataFrame giving timeseries of GHG concentrations
            RF : 
                Pandas DataFrame giving timeseries of Radiative Forcing, by gas + external + total
            T : 
                Pandas DataFrame giving timeseries of Temperature
            alpha : 
                Pandas DataFrame giving timeseries of Alpha by gas

    output_vars : list[str]
        List of output variables

    factors : dict[(Union[float, numpy.ndarray])]
        ohu : ratio of ocean heat uptake to total Earth energy uptake
        gmst : ratio of GMST to GSAT

    Returns
    -------
    data : dict
        dict of climate model output
    unit : dict
        dict of units corresponding to data
    nt : int
        number of timesteps modelled
    """
    
    emissions_df = fair_output['emissions']
    C_df = fair_output['C']
    RF_df = fair_output['RF']
    T_df = fair_output['T']
    alpha_df = fair_output['alpha']

    data = {}
    unit = {}

    data["Atmospheric Concentrations|CO2"] = C_df.loc["CO2"].to_numpy()
    data["Atmospheric Concentrations|CH4"] = C_df.loc["CH4"].to_numpy()
    data["Atmospheric Concentrations|N2O"] = C_df.loc["N2O"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|PFC|CF4"] = C_df.loc["CF4"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|PFC|C2F6"] = C_df.loc["C2F6"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|PFC|C6F14"] = C_df.loc["C6F14"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC23"] = C_df.loc["HFC23"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC32"] = C_df.loc["HFC32"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC125"] = C_df.loc["HFC125"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC134a"] = C_df.loc["HFC134a"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC143a"] = C_df.loc["HFC143a"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC227ea"] = C_df.loc["HFC227ea"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC245fa"] = C_df.loc["HFC245fa"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|HFC|HFC4310mee"] = C_df.loc["HFC4310mee"].to_numpy()
    data["Atmospheric Concentrations|F-Gases|SF6"] = C_df.loc["SF6"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC11"] = C_df.loc["CFC11"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC12"] = C_df.loc["CFC12"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC113"] = C_df.loc["CFC113"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC114"] = C_df.loc["CFC114"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CFC|CFC115"] = C_df.loc["CFC115"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CCl4"] = C_df.loc["CCl4"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CH3CCl3"] = C_df.loc["CH3CCl3"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|HCFC22"] = C_df.loc["HCFC22"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|HCFC141b"] = C_df.loc["HCFC141b"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|HCFC142b"] = C_df.loc["HCFC142b"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|Halon1211"] = C_df.loc["Halon1211"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|Halon1202"] = C_df.loc["Halon1202"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|Halon1301"] = C_df.loc["Halon1301"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|Halon2402"] = C_df.loc["Halon2402"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CH3Br"] = C_df.loc["CH3Br"].to_numpy()
    data["Atmospheric Concentrations|Montreal Gases|CH3Cl"] = C_df.loc["CH3Cl"].to_numpy()

    data["Effective Radiative Forcing|CO2"] = RF_df.loc["CO2"].to_numpy()
    data["Effective Radiative Forcing|CH4"] = RF_df.loc["CH4"].to_numpy()
    data["Effective Radiative Forcing|N2O"] = RF_df.loc["N2O"].to_numpy()
    data["Effective Radiative Forcing|CF4"] = RF_df.loc["CF4"].to_numpy()
    data["Effective Radiative Forcing|C2F6"] = RF_df.loc["C2F6"].to_numpy()
    data["Effective Radiative Forcing|C6F14"] = RF_df.loc["C6F14"].to_numpy()
    data["Effective Radiative Forcing|HFC23"] = RF_df.loc["HFC23"].to_numpy()
    data["Effective Radiative Forcing|HFC32"] = RF_df.loc["HFC32"].to_numpy()
    data["Effective Radiative Forcing|HFC125"] = RF_df.loc["HFC125"].to_numpy()
    data["Effective Radiative Forcing|HFC134a"] = RF_df.loc["HFC134a"].to_numpy()
    data["Effective Radiative Forcing|HFC143a"] = RF_df.loc["HFC143a"].to_numpy()
    data["Effective Radiative Forcing|HFC227ea"] = RF_df.loc["HFC227ea"].to_numpy()
    data["Effective Radiative Forcing|HFC245fa"] = RF_df.loc["HFC245fa"].to_numpy()
    data["Effective Radiative Forcing|HFC4310mee"] = RF_df.loc["HFC4310mee"].to_numpy()
    data["Effective Radiative Forcing|F-Gases|SF6"] = RF_df.loc["SF6"].to_numpy()
    data["Effective Radiative Forcing|CFC11"] = RF_df.loc["CFC11"].to_numpy()
    data["Effective Radiative Forcing|CFC12"] = RF_df.loc["CFC12"].to_numpy()
    data["Effective Radiative Forcing|CFC113"] = RF_df.loc["CFC113"].to_numpy()
    data["Effective Radiative Forcing|CFC114"] = RF_df.loc["CFC114"].to_numpy()
    data["Effective Radiative Forcing|CFC115"] = RF_df.loc["CFC115"].to_numpy()
    data["Effective Radiative Forcing|CCl4"] = RF_df.loc["CCl4"].to_numpy()
    data["Effective Radiative Forcing|CH3CCl3"] = RF_df.loc["CH3CCl3"].to_numpy()
    data["Effective Radiative Forcing|HCFC22"] = RF_df.loc["HCFC22"].to_numpy()
    data["Effective Radiative Forcing|HCFC141b"] = RF_df.loc["HCFC141b"].to_numpy()
    data["Effective Radiative Forcing|HCFC142b"] = RF_df.loc["HCFC142b"].to_numpy()
    data["Effective Radiative Forcing|Halon1211"] = RF_df.loc["Halon1211"].to_numpy()
    data["Effective Radiative Forcing|Halon1202"] = RF_df.loc["Halon1202"].to_numpy()
    data["Effective Radiative Forcing|Halon1301"] = RF_df.loc["Halon1301"].to_numpy()
    data["Effective Radiative Forcing|Halon2402"] = RF_df.loc["Halon2402"].to_numpy()
    data["Effective Radiative Forcing|CH3Br"] = RF_df.loc["CH3Br"].to_numpy()
    data["Effective Radiative Forcing|CH3Cl"] = RF_df.loc["CH3Cl"].to_numpy()
    #data["Effective Radiative Forcing|Tropospheric Ozone"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Stratospheric Ozone"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Contrails"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Aerosols|Direct Effect|Sulfur"] = RF_df.loc["CO2"].to_numpy()
    #data[
    #    "Effective Radiative Forcing|Aerosols|Direct Effect|Secondary Organic Aerosol"
    #] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Aerosols|Direct Effect|Nitrate"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Aerosols|Direct Effect|BC"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Aerosols|Direct Effect|OC"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Aerosols|Indirect Effect"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Black Carbon on Snow"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Land-use Change"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Volcanic"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Solar"] = RF_df.loc["CO2"].to_numpy()
    data["Effective Radiative Forcing"] = RF_df.loc["Total"].to_numpy()
    #data["Effective Radiative Forcing|Anthropogenic"] = RF_df.loc["CO2"].to_numpy()
    data["Effective Radiative Forcing|Greenhouse Gases"] = RF_df.loc["CO2"].to_numpy()
    # This definition does not include ozone and H2O from CH4 oxidation
    data["Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"] =  RF_df.loc["CO2"].to_numpy() +\
                                                                        RF_df.loc["CH4"].to_numpy() +\
                                                                        RF_df.loc["N2O"].to_numpy() +\
                                                                        RF_df.loc["CF4"].to_numpy() +\
                                                                        RF_df.loc["C2F6"].to_numpy() +\
                                                                        RF_df.loc["C6F14"].to_numpy() +\
                                                                        RF_df.loc["HFC23"].to_numpy() +\
                                                                        RF_df.loc["HFC32"].to_numpy() +\
                                                                        RF_df.loc["HFC125"].to_numpy() +\
                                                                        RF_df.loc["HFC134a"].to_numpy() +\
                                                                        RF_df.loc["HFC143a"].to_numpy() +\
                                                                        RF_df.loc["HFC227ea"].to_numpy() +\
                                                                        RF_df.loc["HFC245fa"].to_numpy() +\
                                                                        RF_df.loc["HFC4310mee"].to_numpy() +\
                                                                        RF_df.loc["SF6"].to_numpy()
    data["Effective Radiative Forcing|CO2, CH4 and N2O"] =  RF_df.loc["CO2"].to_numpy() +\
                                                            RF_df.loc["CH4"].to_numpy() +\
                                                            RF_df.loc["N2O"].to_numpy()
    data["Effective Radiative Forcing|F Gases"] =   RF_df.loc["CF4"].to_numpy() +\
                                                    RF_df.loc["C2F6"].to_numpy() +\
                                                    RF_df.loc["C6F14"].to_numpy() +\
                                                    RF_df.loc["HFC23"].to_numpy() +\
                                                    RF_df.loc["HFC32"].to_numpy() +\
                                                    RF_df.loc["HFC125"].to_numpy() +\
                                                    RF_df.loc["HFC134a"].to_numpy() +\
                                                    RF_df.loc["HFC143a"].to_numpy() +\
                                                    RF_df.loc["HFC227ea"].to_numpy() +\
                                                    RF_df.loc["HFC245fa"].to_numpy() +\
                                                    RF_df.loc["HFC4310mee"].to_numpy() +\
                                                    RF_df.loc["SF6"].to_numpy()
    data["Effective Radiative Forcing|Montreal Protocol Halogen Gases"] =   RF_df.loc["CFC11"].to_numpy() +\
                                                                            RF_df.loc["CFC12"].to_numpy() +\
                                                                            RF_df.loc["CFC113"].to_numpy() +\
                                                                            RF_df.loc["CFC114"].to_numpy() +\
                                                                            RF_df.loc["CFC115"].to_numpy() +\
                                                                            RF_df.loc["CCl4"].to_numpy() +\
                                                                            RF_df.loc["CH3CCl3"].to_numpy() +\
                                                                            RF_df.loc["HCFC22"].to_numpy() +\
                                                                            RF_df.loc["HCFC141b"].to_numpy() +\
                                                                            RF_df.loc["HCFC142b"].to_numpy() +\
                                                                            RF_df.loc["Halon1211"].to_numpy() +\
                                                                            RF_df.loc["Halon1202"].to_numpy() +\
                                                                            RF_df.loc["Halon1301"].to_numpy() +\
                                                                            RF_df.loc["Halon2402"].to_numpy() +\
                                                                            RF_df.loc["CH3Br"].to_numpy() +\
                                                                            RF_df.loc["CH3Cl"].to_numpy()
    #data["Effective Radiative Forcing|Aerosols|Direct Effect"] = RF_df.loc["CO2"].to_numpy()
    #data["Effective Radiative Forcing|Aerosols"] = RF_df.loc["CO2"].to_numpy()

    data["Surface Temperature"] = T_df.to_numpy()
    data["Surface Temperature (GMST)"] = T_df.to_numpy() * factors["gmst"]
    #data["Airborne Fraction"] = airborne_emissions
    #data["Effective Climate Feedback"] = lambda_eff
    #data["Heat Content"] = ohc
    #data["Heat Content|Ocean"] = ohc * factors["ohu"]
    #data["Net Energy Imbalance"] = heatflux
    #data["Heat Uptake"] = heatflux * toa_to_joule
    #data["Heat Uptake|Ocean"] = heatflux * toa_to_joule * factors["ohu"]

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
    unit["Effective Radiative Forcing|Aerosols|Direct Effect|Sulfur"] = "W/m**2"
    unit[
        "Effective Radiative Forcing|Aerosols|Direct Effect|Secondary Organic Aerosol"
    ] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols|Direct Effect|Nitrate"] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols|Direct Effect|BC"] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols|Direct Effect|OC"] = "W/m**2"
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
    unit["Effective Radiative Forcing|Aerosols|Direct Effect"] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols"] = "W/m**2"
    unit["Surface Temperature"] = "K"
    unit["Surface Temperature (GMST)"] = "K"
    unit["Airborne Fraction"] = "dimensionless"
    unit["Effective Climate Feedback"] = "W/m**2/K"
    unit["Heat Content"] = "J"
    unit["Heat Content|Ocean"] = "J"
    unit["Net Energy Imbalance"] = "W/m**2"
    unit["Heat Uptake"] = "J/yr"
    unit["Heat Uptake|Ocean"] = "J/yr"

    nt = len(data["Surface Temperature"])

    out = ({}, {}, nt)
    for key in output_vars:
        if key not in data:
            LOGGER.warning("%s not available from FaIR 2.0", key)
            continue

        out[0][key] = data[key]
        out[1][key] = unit[key]

    return out
