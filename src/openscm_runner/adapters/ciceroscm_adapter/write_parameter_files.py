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
        filedata = filedata.replace(
            "lambda 0.540", "lambda {:.4}".format(pamset["lambda"])
        )
        filedata = filedata.replace(
            "akapa 0.341", "akapa {:.4}".format(pamset["akapa"])
        )
        filedata = filedata.replace("cpi 0.556", "cpi {:.4}".format(pamset["cpi"]))
        filedata = filedata.replace("W 1.897", "W {:.4}".format(pamset["W"]))
        filedata = filedata.replace(
            "rlamdo 16.618", "rlamdo {:.4}".format(pamset["rlamdo"])
        )
        filedata = filedata.replace("beto 3.225", "beto {:.4}".format(pamset["beto"]))
        filedata = filedata.replace(
            "mixed 107.277", "mixed {:.4}".format(pamset["mixed"])
        )
        filedata = filedata.replace(
            "dirso2_forc -0.457", "dirso2_forc {:.4}".format((pamset["dirso2_forc"])),
        )
        filedata = filedata.replace(
            "indso2_forc -0.514", "indso2_forc {:.4}".format((pamset["indso2_forc"])),
        )
        filedata = filedata.replace(
            "bc_forc 0.200", "bc_forc {:.4}".format((pamset["bc_forc"]))
        )
        filedata = filedata.replace(
            "oc_forc -0.103", "oc_forc {:.4}".format((pamset["oc_forc"]))
        )
        with open(
            os.path.join(filedir, "inputfiles", "pam_current.scm"), "w"
        ) as scfile:
            scfile.write(filedata)
