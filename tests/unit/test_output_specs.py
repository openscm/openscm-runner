"""Output-request behavior retained when extracting the old API definitions."""

import pytest

from openscm_runner import (
    STANDARD_OUTPUT_VARIABLES,
    OutputSpecs,
    UnsupportedOutputError,
    validate_output_request,
)


class Capabilities:
    supported_output_variables = frozenset({"Surface Air Temperature Change"})


@pytest.mark.parametrize(
    ("values", "error", "message"),
    [
        ([], TypeError, "must be a tuple"),
        ((), ValueError, "must not be empty"),
        (("",), TypeError, "non-empty strings"),
        ((1,), TypeError, "non-empty strings"),
        (("duplicate", "duplicate"), ValueError, "must not contain duplicates"),
    ],
)
def test_invalid_requests(values, error, message):
    with pytest.raises(error, match=message):
        OutputSpecs(values)


def test_standard_outputs_and_extended_request():
    assert STANDARD_OUTPUT_VARIABLES == (
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
    specs = OutputSpecs(STANDARD_OUTPUT_VARIABLES)
    assert specs.output_variables == STANDARD_OUTPUT_VARIABLES
    extended = (*STANDARD_OUTPUT_VARIABLES, "Additional Diagnostic")
    assert OutputSpecs(extended).output_variables == extended


def test_output_variables_remain_explicit():
    with pytest.raises(TypeError, match="output_variables"):
        OutputSpecs()


def test_regions_are_not_an_output_request():
    with pytest.raises(TypeError, match="output_regions"):
        OutputSpecs(("Surface Air Temperature Change",), output_regions=("Europe",))


def test_supported_request():
    validate_output_request(
        Capabilities(), OutputSpecs(("Surface Air Temperature Change",))
    )


@pytest.mark.parametrize(
    ("variables", "message"),
    [
        (("Unknown",), "variables.*Unknown"),
    ],
)
def test_unsupported_request(variables, message):
    with pytest.raises(UnsupportedOutputError, match=message):
        validate_output_request(Capabilities(), OutputSpecs(variables))
