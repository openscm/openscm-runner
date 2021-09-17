"""
Handling of compatibility of MAGICC imports with different states of installation
"""
# pylint:disable=unused-import
try:
    import f90nml
    import pymagicc

    HAS_PYMAGICC = True
except ImportError:
    f90nml = None
    pymagicc = None
    HAS_PYMAGICC = False
