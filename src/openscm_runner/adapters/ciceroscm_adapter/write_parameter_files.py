"""
Module that makes Cicero-SCM parameter files
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
            os.path.join(self.udir, "pam_RCMIP_test_klimsensdefault.scm"), "r"
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
            new = "{} {:.4}".format(k, pamset.get(k, float(self._pamset_defaults[k])))
            filedata = filedata.replace(old, new)

        with open(
            os.path.join(filedir, "inputfiles", "pam_current.scm"), "w"
        ) as scfile:
            scfile.write(filedata)
