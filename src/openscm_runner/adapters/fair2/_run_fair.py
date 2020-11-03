"""
Module for running FaIR
"""
import logging

import numpy as np
from fair.constants.general import EARTH_RADIUS, SECONDS_PER_YEAR
import fair.emissions_driven as fair_scm
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
    fair_output :  :obj:`pyam.IamDataFrame`
        Output data

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

    dropped_df = fair_output.timeseries().droplevel(['scenario','model','region',])
    data = {}
    unit = {}
    for key in dropped_df.index:
        data[key[0]] = dropped_df.loc[key].values
        unit[key[0]] = key[1]

    data["Effective Radiative Forcing|Greenhouse Gases"] = \
        np.sum([dropped_df[key] for key in\
            ["Effective Radiative Forcing|" + x for x in\
                ["CO2","CH4","N2O","CF4","C2F6","C6F14","HFC23",
                 "HFC32","HFC125","HFC134a","HFC143a","HFC227ea",
                 "HFC245fa","HFC4310mee","F-Gases|SF6","CFC11",
                 "CFC12","CFC113","CFC114","CFC115","CCl4","CH3CCl3",
                 "HCFC22","HCFC141b","HCFC142b","Halon1211",
                 "Halon1202","Halon1301","Halon2402","CH3Br","CH3Cl",
                 "Tropospheric Ozone"]]],\
             axis = 0)
    unit["Effective Radiative Forcing|Greenhouse Gases"] = \
        unit["Effective Radiative Forcing"]

    data["Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"] = \
        np.sum([dropped_df[key] for key in\
            ["Effective Radiative Forcing|" + x for x in\
                ["CO2","CH4","N2O","F-Gases|PFC|CF4","F-Gases|PFC|C2F6",
                 "F-Gases|PFC|C6F14","F-Gases|HFC|HFC23",
                 "F-Gases|HFC|HFC32","F-Gases|HFC|HFC125",
                 "F-Gases|HFC|HFC134a","F-Gases|HFC|HFC143a",
                 "F-Gases|HFC|HFC227ea","F-Gases|HFC|HFC245fa",
                 "F-Gases|HFC|HFC4310mee","F-Gases|SF6"]]],\
             axis = 0)
    unit["Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"] = \
        unit["Effective Radiative Forcing"]

    data["Effective Radiative Forcing|CO2, CH4 and N2O"] = \
        np.sum([dropped_df[key] for key in\
            ["Effective Radiative Forcing|" + x for x in\
                ["CO2","CH4","N2O"]]],\
             axis = 0)
    unit["Effective Radiative Forcing|CO2, CH4 and N2O"] = \
        unit["Effective Radiative Forcing"]

    data["Effective Radiative Forcing|F Gases"] = \
        np.sum([dropped_df[key] for key in\
            ["Effective Radiative Forcing|" + x for x in\
                ["CF4","C2F6","C6F14","HFC23","HFC32","HFC125",
                 "HFC134a","HFC143a","HFC227ea","HFC245fa",
                 "HFC4310mee","F-Gases|SF6"]]],\
             axis = 0)
    unit["Effective Radiative Forcing|F Gases"] = \
        unit["Effective Radiative Forcing"]

    data["Effective Radiative Forcing|Montreal Protocol Halogen Gases"] = \
        np.sum([dropped_df[key] for key in\
            ["Effective Radiative Forcing|" + x for x in\
                ["Montreal Gases|CFC|CFC11","Montreal Gases|CFC|CFC12",
                 "Montreal Gases|CFC|CFC113","Montreal Gases|CH3Cl"
                 "Montreal Gases|CFC|CFC114","Montreal Gases|CH3Br"
                 "Montreal Gases|CFC|CFC115","Montreal Gases|CCl4",
                 "Montreal Gases|CH3CCl3","Montreal Gases|HCFC22",
                 "Montreal Gases|HCFC141b","Montreal Gases|HCFC142b",
                 "Montreal Gases|Halon1211","Montreal Gases|Halon1202",
                 "Montreal Gases|Halon1301","Montreal Gases|Halon2402"]]],\
             axis = 0)
    unit["Effective Radiative Forcing|Montreal Protocol Halogen Gases"] = \
        unit["Effective Radiative Forcing"]

    data["Effective Radiative Forcing|Aerosols|Direct Effect"] = \
        np.sum([dropped_df[key] for key in\
            ["Effective Radiative Forcing|" + x for x in\
                ["Effective Radiative Forcing|Aerosols|Direct Effect|Sulfur",
                 "Aerosols|Direct Effect|Secondary Organic Aerosol",
                 "Aerosols|Direct Effect|Nitrate",
                 "Aerosols|Direct Effect|BC","Aerosols|Direct Effect|OC"]]],\
             axis = 0)
    unit["Effective Radiative Forcing|Aerosols|Direct Effect"] = \
        unit["Effective Radiative Forcing"]

    data["Effective Radiative Forcing|Aerosols"] = \
        np.sum([dropped_df[key] for key in\
            ["Effective Radiative Forcing|" + x for x in\
                ["Aerosols|Direct Effect|Sulfur",
                 "Aerosols|Direct Effect|Secondary Organic Aerosol",
                 "Aerosols|Direct Effect|Nitrate","Aerosols|Direct Effect|BC",
                 "Aerosols|Direct Effect|OC","Aerosols|Indirect Effect"]]],\
            axis = 0)
    unit["Effective Radiative Forcing|Aerosols"] = \
        unit["Effective Radiative Forcing"]

    data["Surface Temperature (GMST)"] = \
        data["Surface Temperature"] * factors["gmst"]
    unit["Surface Temperature"] = \
        unit["Surface Temperature"]
    #data["Airborne Fraction"] = airborne_emissions
    #data["Effective Climate Feedback"] = lambda_eff
    #data["Heat Content"] = ohc
    #data["Heat Content|Ocean"] = ohc * factors["ohu"]
    #data["Net Energy Imbalance"] = heatflux
    #data["Heat Uptake"] = heatflux * toa_to_joule
    #data["Heat Uptake|Ocean"] = heatflux * toa_to_joule * factors["ohu"]

    nt = len(data["Surface Temperature"])

    out = ({}, {}, nt)
    for key in output_vars:
        if key not in data:
            LOGGER.warning("%s not available from FaIR 2.0", key)
            continue

        out[0][key] = data[key]
        out[1][key] = unit[key]

    return out
