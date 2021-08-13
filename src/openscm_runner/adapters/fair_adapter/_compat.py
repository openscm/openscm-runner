"""
Handling of compatibility of fair imports with different states of installation
"""
# pylint:disable=unused-import
try:
    import fair

    HAS_FAIR = True
except ImportError:
    fair = None
    HAS_FAIR = False
