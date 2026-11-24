"""
Public errors raised by the adapter API.
"""


class UnsupportedOutputError(ValueError):
    """Raised when an adapter cannot provide a requested output."""


class InvalidInputError(ValueError):
    """Raised when an input does not comply with its experiment definition."""
