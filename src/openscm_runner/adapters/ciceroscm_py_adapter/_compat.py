"""
Handling of compatibility of fair imports with different states of installation
"""
# pylint:disable=unused-import
try:
    import ciceroscm as cscmpy

    HAS_CICEROSCM = True
except ImportError:
    cscmpy = None
    HAS_CICEROSCM_PY = False
