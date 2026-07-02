"""
Canonical openscm-runner emissions-variable names and a checker.

The runner expects scenarios to use a fixed naming convention for
emissions variables. The list below is the source of truth and was
copied (not imported) from
``gcages.databases.emissions_variables.EMISSIONS_VARIABLES``
(the ``openscm_runner`` column) to avoid taking gcages as a runtime
dependency.

If you need translation between openscm-runner names and another
naming convention (RCMIP, IAMC, CMIP7 ScenarioMIP, AR6 CFC infilling,
gcages), use
[`gcages.renaming.convert_variable_name`](https://github.com/openscm/gcages)
in the application layer rather than carrying it inside the wrapper.
"""
from __future__ import annotations

from collections.abc import Iterable

# Canonical emissions variable names, copied from
# ``gcages.databases.emissions_variables`` (openscm_runner column).
# Keep alphabetical so diffs against future gcages updates are obvious.
KNOWN_EMISSIONS_VARIABLES: frozenset[str] = frozenset(
    {
        "Emissions|BC",
        "Emissions|C2F6",
        "Emissions|C3F8",
        "Emissions|C4F10",
        "Emissions|C5F12",
        "Emissions|C6F14",
        "Emissions|C7F16",
        "Emissions|C8F18",
        "Emissions|CCl4",
        "Emissions|CF4",
        "Emissions|CFC11",
        "Emissions|CFC113",
        "Emissions|CFC114",
        "Emissions|CFC115",
        "Emissions|CFC12",
        "Emissions|CH2Cl2",
        "Emissions|CH3Br",
        "Emissions|CH3CCl3",
        "Emissions|CH3Cl",
        "Emissions|CH4",
        "Emissions|CHCl3",
        "Emissions|CO",
        "Emissions|CO2",
        "Emissions|CO2|MAGICC AFOLU",
        "Emissions|CO2|MAGICC Fossil and Industrial",
        "Emissions|HCFC141b",
        "Emissions|HCFC142b",
        "Emissions|HCFC22",
        "Emissions|HFC125",
        "Emissions|HFC134a",
        "Emissions|HFC143a",
        "Emissions|HFC152a",
        "Emissions|HFC227ea",
        "Emissions|HFC23",
        "Emissions|HFC236fa",
        "Emissions|HFC245fa",
        "Emissions|HFC32",
        "Emissions|HFC365mfc",
        "Emissions|HFC4310mee",
        "Emissions|Halon1202",
        "Emissions|Halon1211",
        "Emissions|Halon1301",
        "Emissions|Halon2402",
        "Emissions|N2O",
        "Emissions|NF3",
        "Emissions|NH3",
        "Emissions|NOx",
        "Emissions|OC",
        "Emissions|SF6",
        "Emissions|SO2F2",
        "Emissions|Sulfur",
        "Emissions|VOC",
        "Emissions|cC4F8",
    }
)


def check_variables_are_as_expected(variables: Iterable[str]) -> None:
    """
    Raise :class:`ValueError` if any name is not in
    :data:`KNOWN_EMISSIONS_VARIABLES`.

    Variables that don't start with ``"Emissions|"`` are passed
    through silently: the canonical list only covers emissions, and
    output variables (e.g. ``"Surface Temperature"``,
    ``"Atmospheric Concentrations|CO2"``) live on a separate axis.

    Parameters
    ----------
    variables
        Iterable of variable names found on the scenarios DataFrame.

    Raises
    ------
    ValueError
        One or more emissions variables are not in the canonical
        openscm-runner list. The error names every unknown variable
        so the caller can fix them all in one go.
    """
    emissions_variables = {
        var for var in variables if var.startswith("Emissions|")
    }
    unknown = sorted(emissions_variables - KNOWN_EMISSIONS_VARIABLES)
    if unknown:
        raise ValueError(
            "Unknown emissions variable(s) on the input scenarios: "
            f"{unknown}. The canonical openscm-runner emissions names "
            "are listed in "
            "``openscm_runner._variables.KNOWN_EMISSIONS_VARIABLES``. "
            "If you need to translate from a different naming scheme "
            "(IAMC, RCMIP, CMIP7 ScenarioMIP, etc.), do that "
            "translation upstream of openscm_runner."
        )
