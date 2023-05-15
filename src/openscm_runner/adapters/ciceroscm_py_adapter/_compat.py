"""
Handling of compatibility of ciceroscm imports with different states of installation
"""
# pylint:disable=unused-import
try:
    import ciceroscm as cscmpy

    HAS_CICEROSCM_PY = True
except ImportError:
    cscmpy = None
    HAS_CICEROSCM_PY = False
