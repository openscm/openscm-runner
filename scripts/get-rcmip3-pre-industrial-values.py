# /// script
# requires-python = "==3.12.*"
# dependencies = [
#   "openscm-units",
#   "pandas>=3",
#   "pooch",
# ]
# ///
"""
Get the pre-industrial values for each CMIP phase from RCMIP phase 3

These are the values in `src/openscm_runner/adapters/magicc_ar6/pre_industrial.py`
(MAGICC's names and units), which this script prints:

- `pi_control_concentrations`: CMIP7 from RCMIP phase 3's `piControl` experiment,
  CMIP6 from its `historical-cmip6` experiment in 1850
  (RCMIP phase 3 has no CMIP6 piControl concentrations)
- `pi_control_emissions`: RCMIP phase 3's `historical-cmip6` (CMIP6)
  and `historical` (CMIP7) experiments in 1850
  as `(value, unit)`, with units openscm-units can parse
  (unit conversions with openscm-units, as the adapters do)

Only non-zero values are printed (`pre_industrial.py` fills in the zeros).
The data comes from the Zenodo release of the RCMIP phase 3 protocol, v3.0.1
(https://doi.org/10.5281/zenodo.23347317).
The hashes of the bundle and of the files we use from it are checked.
This script must never import `openscm_runner`.

Run with `uv run --locked --script get-rcmip3-pre-industrial-values.py`
(the environment is locked in `get-rcmip3-pre-industrial-values.py.lock`).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pooch
from openscm_units import unit_registry

RCMIP3_BUNDLE_URL = (
    "https://zenodo.org/api/records/23347317/files/"
    "RCMIP3_protocol_bundle_V3_0_1.zip/content"
)
RCMIP3_BUNDLE_FILENAME = "RCMIP3_protocol_bundle_V3_0_1.zip"
RCMIP3_BUNDLE_SHA256 = (
    "03dc520c1a0636d3033bd7ca193474dce101e1d17c2d202a4db327d26b1532b4"
)
RCMIP3_FILES = {
    # Path in the bundle: sha256
    "RCMIP3_input_datafiles/rcmip_phase3_concentrations_v3.0.1.csv": (
        "1bc8876f87e2fe97caa37443ee3f0e1b2908d40a30ac7c84967a04f3ddb29634"
    ),
    "RCMIP3_input_datafiles/rcmip_phase3_emissions_v3.0.1.csv": (
        "6b32df00635b513a44242ca3a4a62457a93fb9ebfa9ebf2afb860882e75ade51"
    ),
}

YEAR = "1850"

CONCENTRATION_SCENARIOS = {
    # CMIP phase: RCMIP phase 3's experiment to take the 1850 concentrations from
    "CMIP6": "historical-cmip6",
    "CMIP7": "piControl",
}

CONCENTRATION_UNITS = {
    # Gas: unit (the same in RCMIP and MAGICC), any gas not in here is in ppt
    "CO2": "ppm",
    "CH4": "ppb",
    "N2O": "ppb",
}

# RCMIP's name (last part of the variable): MAGICC's name,
# where MAGICC's name isn't just RCMIP's in upper case
CONCENTRATION_RENAMING = {"HFC4310mee": "HFC4310"}

EMISSIONS_SCENARIOS = {
    # CMIP phase: RCMIP phase 3's historical experiment for it
    "CMIP6": "historical-cmip6",
    "CMIP7": "historical",
}

EMISSIONS_VARIABLES = {
    # RCMIP's name: (MAGICC's name, RCMIP's unit, MAGICC's unit, context)
    "Emissions|CO2|Energy and Industrial Processes": (
        "CO2I",
        "Mt CO2/yr",
        "Gt C/yr",
        None,
    ),
    "Emissions|CO2|AFOLU": ("CO2B", "Mt CO2/yr", "Gt C/yr", None),
    "Emissions|CH4": ("CH4", "Mt CH4/yr", "Mt CH4/yr", None),
    "Emissions|N2O": ("N2O", "kt N2O/yr", "Mt N2ON/yr", None),
    "Emissions|BC": ("BC", "Mt BC/yr", "Mt BC/yr", None),
    "Emissions|OC": ("OC", "Mt OC/yr", "Mt OC/yr", None),
    "Emissions|CO": ("CO", "Mt CO/yr", "Mt CO/yr", None),
    # VOC and NMVOC are the same thing
    "Emissions|VOC": ("NMVOC", "Mt VOC/yr", "Mt NMVOC/yr", None),
    "Emissions|Sulfur": ("SOX", "Mt SO2/yr", "Mt S/yr", None),
    # RCMIP's NOx is NO2 mass (e.g. CMIP6 1850: 13.46 Mt, MAGICC's is 13.5 Mt NO2)
    "Emissions|NOx": ("NOX", "Mt NO2/yr", "Mt N/yr", "NOx_conversions"),
    "Emissions|NH3": ("NH3", "Mt NH3/yr", "Mt N/yr", "NH3_conversions"),
}
"""Emissions which aren't halogenated gases"""

HALOGENATED_RENAMING = {
    # RCMIP's name (last part of the variable): MAGICC's name,
    # where MAGICC's name isn't just RCMIP's in upper case
    "HFC4310mee": "HFC4310",
}


def load(member: str) -> pd.DataFrame:
    """
    Load a file from the RCMIP phase 3 bundle

    The bundle is downloaded (and the file extracted) if not already done.
    """
    extracted = pooch.retrieve(
        RCMIP3_BUNDLE_URL,
        known_hash=f"sha256:{RCMIP3_BUNDLE_SHA256}",
        fname=RCMIP3_BUNDLE_FILENAME,
        path=pooch.os_cache("openscm-runner") / "rcmip3",
        processor=pooch.Unzip(members=[member]),
    )
    (path,) = (Path(p) for p in extracted if Path(p).as_posix().endswith(member))
    if pooch.file_hash(str(path), alg="sha256") != RCMIP3_FILES[member]:
        raise AssertionError(path)

    out = pd.read_csv(path, low_memory=False)

    return out.loc[out["Region"] == "World"]


def print_concentrations(concentrations: pd.DataFrame, era: str) -> None:
    """Print the non-zero piControl concentrations for a CMIP era (MAGICC's names)"""
    selected = concentrations.loc[
        (concentrations["Scenario"] == CONCENTRATION_SCENARIOS[era])
        & (concentrations["Mip_Era"] == era)
    ]
    print(f"{era} pi_control_concentrations ({CONCENTRATION_SCENARIOS[era]}):")
    for _, row in selected.sort_values("Variable").iterrows():
        rcmip_gas = row["Variable"].split("|")[-1]
        gas = CONCENTRATION_RENAMING.get(rcmip_gas, rcmip_gas.upper())
        if row["Unit"] != CONCENTRATION_UNITS.get(gas, "ppt"):
            raise AssertionError(row)

        value = float(row[YEAR])
        if value != 0.0:
            print(f'    "{gas}": {value!r},')


def convert(value: float, unit: str, magicc_unit: str, context: str | None) -> float:
    """Convert a value to MAGICC's unit (using `context` for the conversion if given)"""
    quantity = unit_registry.Quantity(value, unit)
    if context is None:
        return float(quantity.to(magicc_unit).magnitude)

    with unit_registry.context(context):
        return float(quantity.to(magicc_unit).magnitude)


def print_emissions(emissions: pd.DataFrame, era: str) -> None:
    """Print the 1850 historical emissions for a CMIP era (MAGICC's names and units)"""
    selected = emissions.loc[
        (emissions["Scenario"] == EMISSIONS_SCENARIOS[era])
        & (emissions["Mip_Era"] == era)
    ].set_index("Variable")
    print(f"{era} pi_control_emissions ({EMISSIONS_SCENARIOS[era]}):")
    for variable, (gas, unit, magicc_unit, context) in EMISSIONS_VARIABLES.items():
        rcmip_unit = selected.loc[variable, "Unit"]
        # RCMIP calls NO2 mass NOx (see above)
        if rcmip_unit.replace("NOx", "NO2") != unit:
            raise AssertionError((variable, rcmip_unit))

        value = convert(float(selected.loc[variable, YEAR]), unit, magicc_unit, context)
        print(f'    "{gas}": ({value!r}, "{magicc_unit}"),')

    # Halogenated gases (kt/yr in both RCMIP and MAGICC)
    for variable, row in selected.sort_index().iterrows():
        if variable in EMISSIONS_VARIABLES or variable.startswith("Emissions|CO2"):
            continue

        rcmip_gas = variable.split("|")[-1]
        if row["Unit"] != f"kt {rcmip_gas}/yr":
            raise AssertionError((variable, row["Unit"]))

        value = float(row[YEAR])
        if value != 0.0:
            gas = HALOGENATED_RENAMING.get(rcmip_gas, rcmip_gas.upper())
            print(f'    "{gas}": ({value!r}, "{row["Unit"]}"),')


def main() -> None:
    """Print the pre-industrial values for CMIP6 and CMIP7"""
    concentrations = load(
        "RCMIP3_input_datafiles/rcmip_phase3_concentrations_v3.0.1.csv"
    )
    emissions = load("RCMIP3_input_datafiles/rcmip_phase3_emissions_v3.0.1.csv")
    for era in ("CMIP6", "CMIP7"):
        print_concentrations(concentrations, era)
        print_emissions(emissions, era)


if __name__ == "__main__":
    main()
