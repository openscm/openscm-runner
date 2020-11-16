"""
Module with functionality to make emission input files
"""
import csv
import logging
import os

import numpy as np
import pandas as pd

# import sys
# Method to convert the unit names form tonnes to grams


def unit_name_converter(unit):
    """
    Convert unit names between tonnes and grammes
    """
    uprefix = unit[0:2]
    if uprefix == "Mt":
        return "Tg{}".format(unit[2:])
    if uprefix == "kt":
        return "Gg{}".format(unit[2:])
    if uprefix == "Gt":
        return "Pg{}".format(unit[2:])
    return unit


# Method to find unit conversion factor


def unit_conv_factor(proper_unit, unit, comp):
    """
    Find conversion factor between two units
    """
    # Todo: raise exception
    conv_dict = {"P": 1.0e15, "T": 1.0e12, "G": 1.0e9, "M": 1.0e6, "k": 1.0e3}
    conv_factor = conv_dict[unit[0]] / conv_dict[proper_unit[0]]
    if unit[1:] != proper_unit[1:]:
        if unit[1:] == "g" and proper_unit[1:] == "g_C" and (comp in ("CO2", "CO2_lu")):
            conv_factor = conv_factor * 3.0 / 11  # Carbon mass fraction in CO2
        elif unit[1:] == "g" and proper_unit[1:] == "g_N" and comp == "N2O":
            conv_factor = conv_factor * 0.636  # Nitrogen mass fraction in N2O
        elif unit[1:] == "t NOx/yr" and proper_unit[1:] == "t_N" and comp == "NOx":
            conv_factor = (
                conv_factor * 0.304
            )  # Nitrogen mass fraction in NOx (approximated by NO2)
        elif unit[1:] == "g" and proper_unit[1:] == "g_S" and comp == "SO2":
            conv_factor = conv_factor * 0.501  # Sulphur mass fraction in SO2

    return conv_factor


def read_ssp245_em(ssp245_em_file):
    """
    Get default data from ssp245_RCMIP
    """
    ssp245df = pd.read_csv(ssp245_em_file, delimiter="\t", index_col=0)
    ssp245df.rename(columns=lambda x: x.strip(), inplace=True)
    ssp245df.rename(index=lambda x: x.strip(), inplace=True)
    ssp245df.rename(columns={"CO2 .1": "CO2_lu"}, inplace=True)
    return ssp245df


def get_top_of_file(ssp245_em_file):
    """
    Get the top of the emission file which will be equal for all scenarios
    """
    with open(ssp245_em_file) as semfile:
        filedata = semfile.read()
    top_of_file = filedata.split("\n2016")[0]
    return top_of_file


class SCENARIOFILEWRITER:
    """
    Class to write scenariofiles:
    """

    def __init__(self, udir):
        self.components = []
        self.units = []

        self.component_dict = {
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
        }  # Halon1212, CH3Cl
        self.initialize_units_comps(os.path.join(udir, "gases_v1RCMIP.txt"))
        self.years = range(2015, 2101)
        self.ssp245data = read_ssp245_em(os.path.join(udir, "ssp245_em_RCMIP.txt"))
        self.udir = udir

    def initialize_units_comps(self, gasfile):
        """
        Get the list of gas components and units
        from the gases file:
        """
        with open(gasfile, "r") as txt_rcpfile:
            gasreader = csv.reader(txt_rcpfile, delimiter="\t")
            next(gasreader)
            for row in gasreader:
                if row[1] == "X":
                    continue
                self.components.append(row[0])
                self.units.append(row[1])
        self.components.insert(1, "CO2_lu")
        self.units.insert(1, "Pg_C")
        self.years = np.arange(2015, 2100, 1)

    def get_unit_convfactor(self, comp, scenarioframe):
        """
        Get unit and conversion factor for component
        """
        # Find the unit and the original unit
        proper_unit = self.units[self.components.index(comp)]
        if scenarioframe.filter(variable="*{}*".format(self.component_dict[comp][0]))[
            "unit"
        ].empty:
            return proper_unit, 1

        unit = scenarioframe.filter(
            variable="*{}*".format(self.component_dict[comp][0])
        )["unit"].iat[0]
        # Getting units on the same form T/g
        if unit != proper_unit:
            if unit[0:2] == proper_unit[0:2]:
                if not (unit == "Mt NOx/yr" and proper_unit == "Mt_N"):
                    unit = proper_unit
            else:
                unit = unit_name_converter(unit)
        conv_factor = 1
        if unit != proper_unit:
            conv_factor = unit_conv_factor(proper_unit, unit, comp)
        return conv_factor

    def write_scenario_data(self, scenarioframe, odir):
        """
        Take a pyam IamDataframe scenario filter to World and specific
        scenario
        and writing out necessary emissions files
        """
        # And extra dictionary to hold data from ssp-scenario:
        # This is for components for which data is missing for the ssp
        fname = os.path.join(
            odir, "inputfiles", "{s}_em.txt".format(s=scenarioframe["scenario"][0])
        )
        logging.getLogger("pyam").setLevel(logging.ERROR)
        avail_comps = [c[10:] for c in scenarioframe.variables()]

        # Setting conversion factors for components
        for comp in self.components:
            if self.component_dict[comp][0] in avail_comps:
                self.component_dict[comp][1] = self.get_unit_convfactor(
                    comp, scenarioframe
                )
        with open(fname, "w") as sfile:
            sfile.write(get_top_of_file(os.path.join(self.udir, "ssp245_em_RCMIP.txt")))
            for year in range(2016, 2101):
                line = "\n{}".format(year)
                for comp in self.components:

                    if year < 2015 or self.component_dict[comp][0] not in avail_comps:
                        line = "{line} \t{val:.8f}".format(
                            line=line, val=float(self.ssp245data[comp][str(year)]),
                        )
                    else:

                        compframe = scenarioframe.filter(
                            variable="Emissions|{}".format(self.component_dict[comp][0])
                        )

                        compframe.interpolate(year)

                        line = "{line} \t{val:.8f}".format(
                            line=line,
                            val=float(
                                compframe[["year", "value"]].set_index("year")["value"][
                                    year
                                ]
                            )
                            * self.component_dict[comp][1],
                        )
                sfile.write("{}".format(line))
        logging.getLogger("pyam").setLevel(logging.WARNING)
