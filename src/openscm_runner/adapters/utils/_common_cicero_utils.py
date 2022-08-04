"""
Module with various common utilities
for both CICERO-SCM implementations
to avoid code duplication
"""

import openscm_units


def _unit_conv_factor(unit, cicero_unit):
    """
    Convert cicero units that can't be automatically dealt with
    in openscm_units
    """
    with openscm_units.unit_registry.context("NOx_conversions"):

        if cicero_unit.startswith("GgH1"):
            conv_factor = (
                openscm_units.unit_registry(unit)
                .to(cicero_unit.replace("GgH1", "GgHalon1"))
                .magnitude
            )
        elif cicero_unit.startswith("GgH2"):
            conv_factor = (
                openscm_units.unit_registry(unit)
                .to(cicero_unit.replace("GgH2", "GgHalon2"))
                .magnitude
            )
        else:
            conv_factor = openscm_units.unit_registry(unit).to(cicero_unit).magnitude

    return conv_factor


cicero_comp_dict = {
    "CO2_lu": ["CO2|MAGICC AFOLU", 1],
    "CFC-113": ["CFC113", 1],
    "CFC-114": ["CFC114", 1],
    "SO2": ["Sulfur", 1],
    "NMVOC": ["VOC", 1],
    "CFC-11": ["CFC11", 1],
    "CFC-115": ["CFC115", 1],
    "CFC-12": ["CFC12", 1],
    "HCFC-141b": ["HCFC141b", 1],
    "HCFC-142b": ["HCFC142b", 1],
    "HCFC-22": ["HCFC22", 1],
    "H-1211": ["Halon1211", 1],
    "H-1301": ["Halon1301", 1],
    "H-2402": ["Halon2402", 1],
    "CO2": ["CO2|MAGICC Fossil and Industrial", 1],
    "CH4": ["CH4", 1],
    "N2O": ["N2O", 1],
    "CH3Br": ["CH3Br", 1],
    "CCl4": ["CCl4", 1],
    "CH3CCl3": ["CH3CCl3", 1],
    "HCFC-123": ["HCFC-123", 1],
    "HFC125": ["HFC125", 1],
    "HFC134a": ["HFC134a", 1],
    "HFC143a": ["HFC143a", 1],
    "HFC227ea": ["HFC227ea", 1],
    "HFC23": ["HFC23", 1],
    "HFC245fa": ["HFC245fa", 1],
    "HFC32": ["HFC32", 1],
    "HFC4310mee": ["HFC4310mee", 1],
    "C2F6": ["C2F6", 1],
    "C6F14": ["C6F14", 1],
    "CF4": ["CF4", 1],
    "SF6": ["SF6", 1],
    "NOx": ["NOx", 1],
    "CO": ["CO", 1],
    "NH3": ["NH3", 1],
    "BMB_AEROS_BC": ["BMB_AEROS_BC", 1],
    "BMB_AEROS_OC": ["BMB_AEROS_OC", 1],
    "BC": ["BC", 1],
    "OC": ["OC", 1],
}
# Halon1212, CH3Cl

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
