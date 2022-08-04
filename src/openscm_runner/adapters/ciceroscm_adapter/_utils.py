"""
Utility functions for CICERO-SCM adapter
"""
import os
import platform


def _get_executable(rundir):
    """
    Get the right executable for the operating system
    """
    if platform.system() == "Windows":
        executable = os.path.join(rundir, "scm_vCH4fb_bfx.exe")
    else:
        executable = os.path.join(rundir, "scm_vCH4fb_bfx")
    return executable
