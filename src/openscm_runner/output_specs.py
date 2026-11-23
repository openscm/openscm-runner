"""Output requests and capability validation, independent of experiment type."""

from dataclasses import dataclass
from typing import Protocol

from .adapter_errors import UnsupportedOutputError

STANDARD_OUTPUT_VARIABLES: tuple[str, ...] = (
    "Surface Air Temperature Change",
    "Surface Air Ocean Blended Temperature Change",
    "Effective Radiative Forcing|Anthropogenic",
    "Atmospheric Concentrations|CO2",
    "Effective Radiative Forcing|Anthropogenic|Aerosol",
    "Heat Content|Ocean",
    "Atmospheric Concentrations|CH4",
    "Heat Uptake",
    "Effective Radiative Forcing|Anthropogenic|CO2",
    "Effective Radiative Forcing|Greenhouse Gases",
)
"""
Backend-independent standard outputs

Other requests can build off this
or simply write out their own explicit names.
"""
# TODO: consider switching to set[str, ...] (although that might be mutable?)
# and adding definitions of all of these variables alongside these names.


@dataclass(frozen=True, slots=True)
class OutputSpecs:
    """Output variables requested from a configured adapter.

    Outputs use the `World` region.
    """

    output_variables: tuple[str, ...]

    def __post_init__(self) -> None:  # noqa: D105
        if not isinstance(self.output_variables, tuple):
            msg = "output_variables must be a tuple of strings"
            raise TypeError(msg)

        if not self.output_variables:
            msg = "output_variables must not be empty"
            raise ValueError(msg)

        if any(
            not isinstance(value, str) or not value for value in self.output_variables
        ):
            msg = "output_variables must only contain non-empty strings"
            raise TypeError(msg)

        if len(set(self.output_variables)) != len(self.output_variables):
            msg = "output_variables must not contain duplicates"
            raise ValueError(msg)


class OutputCapabilities(Protocol):
    """Output declarations required by every experiment adapter protocol."""

    @property
    def supported_output_variables(self) -> frozenset[str]:
        """Output variables supported by this adapter"""
        ...


def validate_output_request(
    adapter: OutputCapabilities, output_specs: OutputSpecs
) -> None:
    """Raise before execution if the adapter cannot provide a requested output."""
    unsupported_variables = (
        set(output_specs.output_variables) - adapter.supported_output_variables
    )
    if unsupported_variables:
        msg = (
            "Unsupported output request: "
            f"variables {sorted(unsupported_variables)!r} "
            f"(supported: {sorted(adapter.supported_output_variables)!r})"
        )
        raise UnsupportedOutputError(msg)
