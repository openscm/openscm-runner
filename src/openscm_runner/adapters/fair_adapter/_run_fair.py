"""
Module for running FaIR
"""
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scmdata import ScmRun, run_append

from ...settings import config
from ..utils._parallel_process import _parallel_process
from ._compat import fair_scm

LOGGER = logging.getLogger(__name__)


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
    updated_config = []
    for i, cfg in enumerate(cfgs):
        updated_config.append({})
        for key, value in cfg.items():
            if isinstance(value, list):
                updated_config[i][key] = np.asarray(value)
            else:
                updated_config[i][key] = value
        updated_config[i]["output_vars"] = output_vars

    ncpu = int(config.get("FAIR_WORKER_NUMBER", multiprocessing.cpu_count()))
    LOGGER.info("Running FaIR with %s workers", ncpu)

    parallel_process_kwargs = dict(
        func=_single_fair_iteration,
        configuration=updated_config,
        config_are_kwargs=False,
    )
    if ncpu > 1:

        with ProcessPoolExecutor(ncpu) as pool:
            res = _parallel_process(**parallel_process_kwargs, pool=pool,)
    else:
        res = _parallel_process(**parallel_process_kwargs)

    res = run_append(res)

    return res


def _single_fair_iteration(cfg):  # pylint: disable=R0914
    scenario = cfg.pop("scenario")
    model = cfg.pop("model")
    run_id = cfg.pop("run_id")
    factors = {}
    factors["gmst"] = cfg.pop("gmst_factor")
    factors["ohu"] = cfg.pop("ohu_factor")
    startyear = cfg.pop("startyear")
    output_vars = cfg.pop("output_vars")

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
        index=np.arange(startyear, startyear + nt),
        columns={
            "scenario": scenario,
            "model": model,
            "region": "World",
            "variable": variables,
            "unit": units,
            "run_id": run_id,
        },
    )

    return tempres


def _process_output(fair_output, output_vars, factors):  # pylint: disable=R0915
    """
    Make sense of FaIR1.6 output

    Parameters
    ----------
    fair_output : tuple
        7-tuple of concentrations, forcing, temperature, lambda_eff, ohc, heatflux, airborne_emissions:
            c : np.ndarray
                (nt, 31) array of greenhouse gas concentrations
            f : np.ndarray
                (nt, 41) array of effective radiative forcings
            t : np.ndarray
                (nt,) array of temperature
            lambda_eff: np.ndarray
                effective climate feedback
            ohc : np.ndarray
                total ocean heat uptake
            heatflux:
                heat transfer into the ocean
            airborne_emissions:
                atmospheric carbon content

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
    (
        concentrations,
        forcing,
        temperature,
        lambda_eff,
        ohc,
        heatflux,
        airborne_emissions,
    ) = fair_output

    data = {}
    unit = {}

    data["Atmospheric Concentrations|CO2"] = concentrations[:, 0]
    data["Atmospheric Concentrations|CH4"] = concentrations[:, 1]
    data["Atmospheric Concentrations|N2O"] = concentrations[:, 2]
    data["Atmospheric Concentrations|CF4"] = concentrations[:, 3]
    data["Atmospheric Concentrations|C2F6"] = concentrations[:, 4]
    data["Atmospheric Concentrations|C6F14"] = concentrations[:, 5]
    data["Atmospheric Concentrations|HFC23"] = concentrations[:, 6]
    data["Atmospheric Concentrations|HFC32"] = concentrations[:, 7]
    data["Atmospheric Concentrations|HFC125"] = concentrations[:, 8]
    data["Atmospheric Concentrations|HFC134a"] = concentrations[:, 9]
    data["Atmospheric Concentrations|HFC143a"] = concentrations[:, 10]
    data["Atmospheric Concentrations|HFC227ea"] = concentrations[:, 11]
    data["Atmospheric Concentrations|HFC245fa"] = concentrations[:, 12]
    data["Atmospheric Concentrations|HFC4310mee"] = concentrations[:, 13]
    data["Atmospheric Concentrations|SF6"] = concentrations[:, 14]
    data["Atmospheric Concentrations|CFC11"] = concentrations[:, 15]
    data["Atmospheric Concentrations|CFC12"] = concentrations[:, 16]
    data["Atmospheric Concentrations|CFC113"] = concentrations[:, 17]
    data["Atmospheric Concentrations|CFC114"] = concentrations[:, 18]
    data["Atmospheric Concentrations|CFC115"] = concentrations[:, 19]
    data["Atmospheric Concentrations|CCl4"] = concentrations[:, 20]
    data["Atmospheric Concentrations|CH3CCl3"] = concentrations[:, 21]
    data["Atmospheric Concentrations|HCFC22"] = concentrations[:, 22]
    data["Atmospheric Concentrations|HCFC141b"] = concentrations[:, 23]
    data["Atmospheric Concentrations|HCFC142b"] = concentrations[:, 24]
    data["Atmospheric Concentrations|Halon1211"] = concentrations[:, 25]
    data["Atmospheric Concentrations|Halon1202"] = concentrations[:, 26]
    data["Atmospheric Concentrations|Halon1301"] = concentrations[:, 27]
    data["Atmospheric Concentrations|Halon2402"] = concentrations[:, 28]
    data["Atmospheric Concentrations|CH3Br"] = concentrations[:, 29]
    data["Atmospheric Concentrations|CH3Cl"] = concentrations[:, 30]
    data["Effective Radiative Forcing|CO2"] = forcing[:, 0]
    data["Effective Radiative Forcing|CH4"] = forcing[:, 1]
    data["Effective Radiative Forcing|N2O"] = forcing[:, 2]
    data["Effective Radiative Forcing|CF4"] = forcing[:, 3]
    data["Effective Radiative Forcing|C2F6"] = forcing[:, 4]
    data["Effective Radiative Forcing|C6F14"] = forcing[:, 5]
    data["Effective Radiative Forcing|HFC23"] = forcing[:, 6]
    data["Effective Radiative Forcing|HFC32"] = forcing[:, 7]
    data["Effective Radiative Forcing|HFC125"] = forcing[:, 8]
    data["Effective Radiative Forcing|HFC134a"] = forcing[:, 9]
    data["Effective Radiative Forcing|HFC143a"] = forcing[:, 10]
    data["Effective Radiative Forcing|HFC227ea"] = forcing[:, 11]
    data["Effective Radiative Forcing|HFC245fa"] = forcing[:, 12]
    data["Effective Radiative Forcing|HFC4310mee"] = forcing[:, 13]
    data["Effective Radiative Forcing|SF6"] = forcing[:, 14]
    data["Effective Radiative Forcing|CFC11"] = forcing[:, 15]
    data["Effective Radiative Forcing|CFC12"] = forcing[:, 16]
    data["Effective Radiative Forcing|CFC113"] = forcing[:, 17]
    data["Effective Radiative Forcing|CFC114"] = forcing[:, 18]
    data["Effective Radiative Forcing|CFC115"] = forcing[:, 19]
    data["Effective Radiative Forcing|CCl4"] = forcing[:, 20]
    data["Effective Radiative Forcing|CH3CCl3"] = forcing[:, 21]
    data["Effective Radiative Forcing|HCFC22"] = forcing[:, 22]
    data["Effective Radiative Forcing|HCFC141b"] = forcing[:, 23]
    data["Effective Radiative Forcing|HCFC142b"] = forcing[:, 24]
    data["Effective Radiative Forcing|Halon1211"] = forcing[:, 25]
    data["Effective Radiative Forcing|Halon1202"] = forcing[:, 26]
    data["Effective Radiative Forcing|Halon1301"] = forcing[:, 27]
    data["Effective Radiative Forcing|Halon2402"] = forcing[:, 28]
    data["Effective Radiative Forcing|CH3Br"] = forcing[:, 29]
    data["Effective Radiative Forcing|CH3Cl"] = forcing[:, 30]
    data["Effective Radiative Forcing|Tropospheric Ozone"] = forcing[:, 31]
    data["Effective Radiative Forcing|Stratospheric Ozone"] = forcing[:, 32]
    data["Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O"] = forcing[:, 33]
    data["Effective Radiative Forcing|Contrails"] = forcing[:, 34]
    data["Effective Radiative Forcing|Aerosols|Direct Effect|SOx"] = forcing[:, 35]
    data[
        "Effective Radiative Forcing|Aerosols|Direct Effect|Secondary Organic Aerosol"
    ] = forcing[:, 36]
    data["Effective Radiative Forcing|Aerosols|Direct Effect|Nitrate"] = forcing[:, 37]
    data["Effective Radiative Forcing|Aerosols|Direct Effect|BC"] = forcing[:, 38]
    data["Effective Radiative Forcing|Aerosols|Direct Effect|OC"] = forcing[:, 39]
    data["Effective Radiative Forcing|Aerosols|Indirect Effect"] = forcing[:, 40]
    data["Effective Radiative Forcing|Black Carbon on Snow"] = forcing[:, 41]
    data["Effective Radiative Forcing|Land-use Change"] = forcing[:, 42]
    data["Effective Radiative Forcing|Volcanic"] = forcing[:, 43]
    data["Effective Radiative Forcing|Solar"] = forcing[:, 44]
    data["Effective Radiative Forcing"] = np.sum(forcing, axis=1)
    data["Effective Radiative Forcing|Anthropogenic"] = np.sum(forcing[:, :43], axis=1)
    data["Effective Radiative Forcing|Greenhouse Gases"] = np.sum(
        forcing[:, :31], axis=1
    )
    # This definition does not include ozone and H2O from CH4 oxidation
    data["Effective Radiative Forcing|Kyoto Gases"] = np.sum(forcing[:, :15], axis=1)
    data["Effective Radiative Forcing|CO2, CH4 and N2O"] = np.sum(
        forcing[:, :3], axis=1
    )
    # What is the rigorous definition here? CFCs are not included but contain F
    data["Effective Radiative Forcing|F-Gases"] = np.sum(forcing[:, 3:15], axis=1)
    data["Effective Radiative Forcing|Montreal Protocol Halogen Gases"] = np.sum(
        forcing[:, 15:31], axis=1
    )
    data["Effective Radiative Forcing|Aerosols|Direct Effect"] = np.sum(
        forcing[:, 35:40], axis=1
    )
    data["Effective Radiative Forcing|Aerosols"] = np.sum(forcing[:, 35:41], axis=1)
    data["Effective Radiative Forcing|Ozone"] = np.sum(forcing[:, 31:33], axis=1)
    data["Surface Air Temperature Change"] = temperature
    data["Surface Air Ocean Blended Temperature Change"] = temperature * factors["gmst"]
    data["Airborne Fraction"] = airborne_emissions
    data["Effective Climate Feedback"] = lambda_eff
    data["Heat Content"] = ohc
    data["Heat Content|Ocean"] = ohc * factors["ohu"]
    data["Net Energy Imbalance"] = heatflux
    data["Heat Uptake"] = heatflux
    data["Heat Uptake|Ocean"] = heatflux * factors["ohu"]

    unit["Atmospheric Concentrations|CO2"] = "ppm"
    unit["Atmospheric Concentrations|CH4"] = "ppb"
    unit["Atmospheric Concentrations|N2O"] = "ppb"
    unit["Atmospheric Concentrations|CF4"] = "ppt"
    unit["Atmospheric Concentrations|C2F6"] = "ppt"
    unit["Atmospheric Concentrations|C6F14"] = "ppt"
    unit["Atmospheric Concentrations|HFC23"] = "ppt"
    unit["Atmospheric Concentrations|HFC32"] = "ppt"
    unit["Atmospheric Concentrations|HFC125"] = "ppt"
    unit["Atmospheric Concentrations|HFC134a"] = "ppt"
    unit["Atmospheric Concentrations|HFC143a"] = "ppt"
    unit["Atmospheric Concentrations|HFC227ea"] = "ppt"
    unit["Atmospheric Concentrations|HFC245fa"] = "ppt"
    unit["Atmospheric Concentrations|HFC4310mee"] = "ppt"
    unit["Atmospheric Concentrations|SF6"] = "ppt"
    unit["Atmospheric Concentrations|CFC11"] = "ppt"
    unit["Atmospheric Concentrations|CFC12"] = "ppt"
    unit["Atmospheric Concentrations|CFC113"] = "ppt"
    unit["Atmospheric Concentrations|CFC114"] = "ppt"
    unit["Atmospheric Concentrations|CFC115"] = "ppt"
    unit["Atmospheric Concentrations|CCl4"] = "ppt"
    unit["Atmospheric Concentrations|CH3CCl3"] = "ppt"
    unit["Atmospheric Concentrations|HCFC22"] = "ppt"
    unit["Atmospheric Concentrations|HCFC141b"] = "ppt"
    unit["Atmospheric Concentrations|HCFC142b"] = "ppt"
    unit["Atmospheric Concentrations|Halon1211"] = "ppt"
    unit["Atmospheric Concentrations|Halon1202"] = "ppt"
    unit["Atmospheric Concentrations|Halon1301"] = "ppt"
    unit["Atmospheric Concentrations|Halon2402"] = "ppt"
    unit["Atmospheric Concentrations|CH3Br"] = "ppt"
    unit["Atmospheric Concentrations|CH3Cl"] = "ppt"
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
    unit["Effective Radiative Forcing|SF6"] = "W/m**2"
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
    unit["Effective Radiative Forcing|Aerosols|Direct Effect|SOx"] = "W/m**2"
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
    unit["Effective Radiative Forcing|F-Gases"] = "W/m**2"
    unit["Effective Radiative Forcing|Montreal Protocol Halogen Gases"] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols|Direct Effect"] = "W/m**2"
    unit["Effective Radiative Forcing|Aerosols"] = "W/m**2"
    unit["Effective Radiative Forcing|Ozone"] = "W/m**2"
    unit["Surface Air Temperature Change"] = "K"
    unit["Surface Air Ocean Blended Temperature Change"] = "K"
    unit["Airborne Fraction"] = "dimensionless"
    unit["Effective Climate Feedback"] = "W/m**2/K"
    unit["Heat Content"] = "J"
    unit["Heat Content|Ocean"] = "J"
    unit["Net Energy Imbalance"] = "W/m**2"
    unit["Heat Uptake"] = "W/m**2"
    unit["Heat Uptake|Ocean"] = "W/m**2"

    nt = len(temperature)

    out = ({}, {}, nt)
    for key in output_vars:
        if key not in data:
            LOGGER.warning("%s not available from FaIR", key)
            continue

        out[0][key] = data[key]
        out[1][key] = unit[key]

    return out
