"""
Module with functionality to make emission input files
"""

# Todo: optimise to speed up reading and writing

import csv
import logging
import os
import re

import numpy as np
import pandas as pd


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


def unit_conv_factor(cicero_unit, unit, comp):
    """
    Find conversion factor between two units
    """
    conv_dict = {"P": 1.0e15, "T": 1.0e12, "G": 1.0e9, "M": 1.0e6, "k": 1.0e3}
    conv_factor = conv_dict[unit[0]] / conv_dict[cicero_unit[0]]
    if unit[1:] != cicero_unit[1:]:
        if (
            unit[1:] == "g CO2/yr"
            and cicero_unit[1:] == "g_C"
            and (comp in ("CO2", "CO2_lu"))
        ):
            conv_factor = conv_factor * 3.0 / 11  # Carbon mass fraction in CO2
        elif unit[1:] == "g N2O/yr" and cicero_unit[1:] == "g_N" and comp == "N2O":
            conv_factor = conv_factor * 0.636  # Nitrogen mass fraction in N2O
        elif unit[1:] == "t NOx/yr" and cicero_unit[1:] == "t_N" and comp == "NOx":
            conv_factor = (
                conv_factor * 0.304
            )  # Nitrogen mass fraction in NOx (approximated by NO2)
        elif unit[1:] == "g SO2/yr" and cicero_unit[1:] == "g_S" and comp == "SO2":
            conv_factor = conv_factor * 0.501  # Sulphur mass fraction in SO2

    return conv_factor


def _read_ssp245_em(ssp245_em_file):
    """
    Get default data from ssp245_RCMIP
    """
    ssp245df = pd.read_csv(
        ssp245_em_file, delimiter="\t", index_col=0
    )  # TODO: use scmdata for a more stable and faster API
    ssp245df.rename(columns=lambda x: x.strip(), inplace=True)
    ssp245df.rename(index=lambda x: x.strip(), inplace=True)
    ssp245df.rename(columns={"CO2 .1": "CO2_lu"}, inplace=True)
    return ssp245df


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
        self.years = np.arange(2015, 2101)  # TODO: get these numbers from scenarioframe
        self.ssp245data = _read_ssp245_em(os.path.join(udir, "ssp245_em_RCMIP.txt"))
        self.udir = udir

    def get_top_of_file(self, ssp245_em_file):
        """
        Get the top of the emission file which will be equal for all scenarios
        """
        with open(ssp245_em_file) as semfile:
            filedata = semfile.read()
            top_of_file = filedata.split("\n{}".format(self.years[0]))[0]

        return top_of_file

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
        self.units.insert(1, "Pg/C")

    def get_unit_convfactor(self, comp, scenarioframe):
        """
        Get unit and conversion factor for component
        """
        # Find the unit and the original unit
        cicero_unit = self.units[self.components.index(comp)]
        for row_index in scenarioframe[scenarioframe.keys()[0]].keys():
            if row_index[3] == "Emissions|{}".format(self.component_dict[comp][0]):
                unit = row_index[4]

        # Getting units on the same form T/g
        if unit != cicero_unit:
            if unit[0:2] == cicero_unit[0:2]:
                if not (
                    unit in ("Mt CO/yr", "Mt VOC/yr", "Mt NH3/yr")
                    and cicero_unit == "Mt"
                ):
                    unit = cicero_unit
            else:
                unit = unit_name_converter(unit)
        conv_factor = 1
        if unit != cicero_unit:
            conv_factor = unit_conv_factor(cicero_unit, unit, comp)
        return conv_factor

    def transform_scenarioframe(self, scenarioframe):
        """
        Get rid of multiindex and interpolate scenarioframe
        """
        scenarioframe = scenarioframe.reset_index((0, 1, 2, 4), drop=True)
        years = scenarioframe.keys()

        if not isinstance(years[0], np.int64):
            yearsint = [np.int64(d.year) for d in years]
            scenarioframe.rename(
                lambda d: np.int64(d.year), axis="columns", inplace=True
            )
        else:
            yearsint = years

        self.years = np.arange(yearsint[0], yearsint[-1] + 1)
        for year in self.years:
            if year not in scenarioframe.columns:
                scenarioframe[year] = np.nan

        scenarioframe = scenarioframe.reindex(sorted(scenarioframe.columns), axis=1)
        interpol = scenarioframe.interpolate(axis=1)

        return interpol

    def write_scenario_data(self, scenarioframe, odir):
        """
        Take a scenariodataframe
        and writing out necessary emissions files
        """
        fname = os.path.join(
            odir,
            "inputfiles",
            "{s}_em.txt".format(
                s=re.sub(
                    "[^a-zA-Z0-9_-]",
                    "",
                    scenarioframe[scenarioframe.keys()[0]].keys()[0][1],
                )
            ),
        )
        logging.getLogger("pyam").setLevel(logging.ERROR)
        avail_comps = [
            c[3].replace("Emissions|", "")
            for c in scenarioframe[scenarioframe.keys()[0]].keys()
        ]
        interpol = self.transform_scenarioframe(scenarioframe)
        printout_frame = pd.DataFrame(columns=self.components)
        # Setting conversion factors for components with data from scenarioframe
        for comp in self.components:
            if self.component_dict[comp][0] in avail_comps:
                convfactor = self.get_unit_convfactor(comp, scenarioframe)
                printout_frame[comp] = (
                    interpol.T["Emissions|{}".format(self.component_dict[comp][0])]
                    * convfactor
                )
            else:
                printout_frame[comp] = (
                    self.ssp245data[comp]
                    .loc[str(self.years[0]) : str(self.years[-1])]
                    .to_numpy()
                )

        with open(fname, "w") as sfile:
            sfile.write(
                self.get_top_of_file(os.path.join(self.udir, "ssp245_em_RCMIP.txt"))
            )
        printout_frame.to_csv(fname, sep="\t", mode="a", float_format="%.8f")
