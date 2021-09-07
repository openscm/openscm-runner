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
            "r",
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
            "{path}/inputfiles/{scen}_em.txt".format(
                path=filedir_to_pamfile, scen=scen
            ),
        )
        for k, value in self._pamset_defaults.items():
            old = "{} {}".format(k, value)
            if k in ("model_end", "scenario_start", "scenario_end"):
                new = "{} {}".format(k, pamset.get(k, value))
            else:
                new = "{} {:.4}".format(k, pamset.get(k, float(value)))
            filedata = filedata.replace(old, new)

        with open(
            os.path.join(filedir, "inputfiles", "pam_current.scm"),
            "w",
            encoding="ascii",
        ) as scfile:
            scfile.write(filedata)
