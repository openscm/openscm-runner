"""Output requests and capability validation, independent of experiment type."""

from dataclasses import dataclass
from typing import Protocol

from .errors import UnsupportedOutputError

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
# Adding definitions of these variables (and maybe using a frozenset) is roadmap W19


@dataclass(frozen=True, slots=True)
class OutputSpecs:
    """Output variables requested from a configured adapter.

    Outputs use the `World` region.
    """

    output_variables: tuple[str, ...]

    def __post_init__(self) -> None:  # noqa: D105
        # Runtime check for callers who don't use a type checker
        if not isinstance(self.output_variables, tuple):
            msg = "output_variables must be a tuple of strings"  # type: ignore[unreachable]
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
