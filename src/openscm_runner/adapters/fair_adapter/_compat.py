"""
Handling of compatibility of fair imports with different states of installation
"""
# pylint:disable=unused-import
try:
    import fair
    from fair.forward import fair_scm

    HAS_FAIR = True
except ImportError:
    fair = None
    fair_scm = None
    HAS_FAIR = False
