"""
Module that makes CICERO-SCM parameter files
"""
import os
from pathlib import Path


def splitall(path):
    """
    Split path into each part, top catalogue on top, filename (if included) last
    """
    out = Path(path).parts
    return out


def check_pamset_consistency(pamset):
    """
    Check consistency of parameter set so scenario_end is
    equal to or earlier than model_end
    """
    if "model_end" in pamset and "scenario_end" not in pamset:
        pamset["scenario_end"] = pamset["model_end"]
    elif "model_end" in pamset and pamset["scenario_end"] > pamset["model_end"]:
        pamset["scenario_end"] = pamset["model_end"]
    return pamset


class PARAMETERFILEWRITER:  # pylint: disable=too-few-public-methods
    """
    Class to write parameterfiles
    """

    # pylint: disable=too-many-instance-attributes
    # Eight is reasonable in this case.

    def __init__(self, udir):
        self.udir = udir
        self._pamset_defaults = {
            "model_end": 2500,
            "scenario_start": 2015,
            "scenario_end": 2500,
            "lambda": "0.540",
            "akapa": "0.341",
            "cpi": "0.556",
            "W": "1.897",
            "rlamdo": "16.618",
            "beto": "3.225",
            "mixed": "107.277",
            "dirso2_forc": "-0.457",
            "indso2_forc": "-0.514",
            "bc_forc": "0.200",
            "oc_forc": "-0.103",
        }

        with open(
            os.path.join(self.udir, "pam_RCMIP_test_klimsensdefault.scm"),
            encoding="ascii",
        ) as origfile:
            self.origfiledata = origfile.read()

    def write_parameterfile(self, pamset, filedir):
        """
        Make parameter file for single run
        """
        scen = splitall(filedir)[-1]
        filedir_to_pamfile = os.path.join(".", scen)
        filedata = self.origfiledata
        filedata = filedata.replace(
            "output_rbs/test_rcmip",
            os.path.join(filedir_to_pamfile, "outputfiles", "temp"),
        )
        filedata = filedata.replace("../input_RCP/", "")
        filedata = filedata.replace("input/ssp434_conc_", "ssp245_conc_")

        filedata = filedata.replace(
            "input/ssp434_em_RCMIP.txt",
            f"{filedir_to_pamfile}/inputfiles/{scen}_em.txt",
        )
        pamset = check_pamset_consistency(pamset)

        for k, value in self._pamset_defaults.items():
            old = f"{k} {value}"
            if k in ("model_end", "scenario_start", "scenario_end"):
                new = f"{k} {pamset.get(k, value)}"
                print(f"{k} {pamset.get(k, value)}")
            else:
                new = f"{k} {pamset.get(k, float(value)):.4}"
            filedata = filedata.replace(old, new)

        with open(
            os.path.join(filedir, "inputfiles", "pam_current.scm"),
            "w",
            encoding="ascii",
        ) as scfile:
            scfile.write(filedata)
