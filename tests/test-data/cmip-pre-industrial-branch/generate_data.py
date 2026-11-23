# /// script
# requires-python = "==3.12.*"
# dependencies = [
#   "pandas>=3",
#   "pooch",
# ]
# ///
"""
Generate the CMIP pre-industrial branch test data from RCMIP phase 3

Input for the CMIP pre-industrial branch (concentration-driven) experiments,
in the input's names and units: concentrations,
natural (solar and volcanic) forcing
and aerosol (and aerosol/ozone precursor) emissions, 1850-2100.

- CMIP6: `ssp245` (which includes the history)
- CMIP7: the CMIP7 M scenario (`scen7-M`, which includes the history)
  concentrations and natural forcing.
  RCMIP phase 3 has no emissions for the CMIP7 scenarios (`scen7-*`),
  so the emissions are the `historical` experiment's (1850-2023),
  held constant at their 2023 values.

The natural forcing is RCMIP phase 3's,
so it isn't zero in 1850 (i.e. it isn't relative to piControl,
see decision B19).
The data comes from the RCMIP phase 3 protocol
(https://gitlab.com/rcmip/rcmip-phase-3, tag v3.0.1, pinned to its commit).
This script must never import `openscm_runner`.

Run with `uv run --locked --script generate_data.py`
(the environment is locked in `generate_data.py.lock`).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pooch

HERE = Path(__file__).parent

RCMIP3_URL = (
    "https://gitlab.com/rcmip/rcmip-phase-3/-/raw/"
    "449e56d880d79c0ceca11530e0701c282204179b/{path}"
)
RCMIP3_FILES = {
    # Path in the repository: sha256
    "RCMIP3_input_datafiles/rcmip_phase3_concentrations_v3.0.1.csv": (
        "1bc8876f87e2fe97caa37443ee3f0e1b2908d40a30ac7c84967a04f3ddb29634"
    ),
    "RCMIP3_input_datafiles/rcmip_phase3_emissions_v3.0.1.csv": (
        "6b32df00635b513a44242ca3a4a62457a93fb9ebfa9ebf2afb860882e75ade51"
    ),
    "RCMIP3_input_datafiles/rcmip_phase3_forcing_v3.0.1.csv": (
        "71cff486d1d8a1bb5b7274f4c5a9c7c9cf46ed707e5abf7023b999531256f4f2"
    ),
    "ScenarioMIP/rcmip_phase3_concentrations_ScenarioMIP_v3.0.1.csv": (
        "ebdfb66f5b1191270cab27ee99de1695248a6a67c255eb544dc229d3bafdff97"
    ),
    "ScenarioMIP/rcmip_phase3_forcing_ScenarioMIP_v3.0.1.csv": (
        "d880a8ed7dc319828ad5eb43f1515b5969dd72be5fccbaf0b91fc5ec7b73758c"
    ),
}

FIRST_YEAR = 1850
LAST_YEAR = 2100
LAST_HISTORICAL_YEAR_CMIP7 = 2023

INDEX_COLUMNS = ["scenario", "variable", "region", "unit"]

NATURAL_FORCING = {
    # RCMIP's name: the input's name
    "Effective Radiative Forcing|Natural|Solar": "Effective Radiative Forcing|Solar",
    "Effective Radiative Forcing|Natural|Volcanic": (
        "Effective Radiative Forcing|Volcanic"
    ),
}

AEROSOL_EMISSIONS = {
    # RCMIP's name: (the input's name, the input's unit)
    "Emissions|BC": ("Emissions|BC", "Mt BC/yr"),
    "Emissions|CO": ("Emissions|CO", "Mt CO/yr"),
    "Emissions|NH3": ("Emissions|NH3", "Mt NH3/yr"),
    # RCMIP's NOx is NO2 mass (e.g. CMIP6 1850: 13.46 Mt, MAGICC's is 13.5 Mt NO2)
    "Emissions|NOx": ("Emissions|NOx", "Mt NO2/yr"),
    "Emissions|OC": ("Emissions|OC", "Mt OC/yr"),
    "Emissions|Sulfur": ("Emissions|SOx", "Mt SO2/yr"),
    "Emissions|VOC": ("Emissions|NMVOC", "Mt VOC/yr"),
}

N_CONCENTRATION_SPECIES = 43


def load(path: str) -> pd.DataFrame:
    """Download a file from RCMIP phase 3 (if not already downloaded) and load it"""
    local = Path(
        pooch.retrieve(
            RCMIP3_URL.format(path=path),
            known_hash=f"sha256:{RCMIP3_FILES[path]}",
            fname=Path(path).name,
            path=pooch.os_cache("openscm-runner") / "rcmip3",
        )
    )
    out = pd.read_csv(local, low_memory=False)

    return out.loc[out["Region"] == "World"]


def select(
    df: pd.DataFrame, scenario: str, era: str, last_year: int = LAST_YEAR
) -> pd.DataFrame:
    out = df.loc[(df["Scenario"] == scenario) & (df["Mip_Era"] == era)]
    out = out.set_index(["Variable", "Unit"])[
        [str(y) for y in range(FIRST_YEAR, last_year + 1)]
    ]
    if out.empty or out.isna().any().any():
        raise AssertionError((scenario, era, out))

    return out


def select_history_then_constant(
    df: pd.DataFrame, scenario: str, era: str
) -> pd.DataFrame:
    """Select the history (to `LAST_HISTORICAL_YEAR_CMIP7`), then hold it constant"""
    history = select(df, scenario, era, last_year=LAST_HISTORICAL_YEAR_CMIP7)
    future = pd.DataFrame(
        {
            str(y): history[str(LAST_HISTORICAL_YEAR_CMIP7)]
            for y in range(LAST_HISTORICAL_YEAR_CMIP7 + 1, LAST_YEAR + 1)
        }
    )

    return pd.concat([history, future], axis="columns")


def to_concentrations(df: pd.DataFrame) -> list[tuple[tuple[str, str], pd.Series]]:
    # e.g. "Atmospheric Concentrations|F-Gases|HFC|HFC125"
    # -> "Atmospheric Concentrations|HFC125"
    out = [
        ((f"Atmospheric Concentrations|{variable.split('|')[-1]}", unit), values)
        for (variable, unit), values in df.iterrows()
        if variable.startswith("Atmospheric Concentrations|")
    ]
    if len(out) != N_CONCENTRATION_SPECIES:
        raise AssertionError(len(out))

    return out


def to_natural_forcing(df: pd.DataFrame) -> list[tuple[tuple[str, str], pd.Series]]:
    return [
        ((NATURAL_FORCING[variable], unit), values)
        for (variable, unit), values in df.iterrows()
        if variable in NATURAL_FORCING
    ]


def to_aerosol_emissions(
    df: pd.DataFrame,
) -> list[tuple[tuple[str, str], pd.Series]]:
    return [
        (AEROSOL_EMISSIONS[variable], values)
        for (variable, _), values in df.iterrows()
        if variable in AEROSOL_EMISSIONS
    ]


def to_frame(
    scenario: str, rows: list[tuple[tuple[str, str], pd.Series]]
) -> pd.DataFrame:
    out = pd.DataFrame(
        [values.to_numpy() for _, values in rows],
        index=pd.MultiIndex.from_tuples(
            [(scenario, variable, "World", unit) for (variable, unit), _ in rows],
            names=INDEX_COLUMNS,
        ),
        columns=rows[0][1].index,
    )

    return out.sort_index()


def main() -> None:
    concentrations = load(
        "RCMIP3_input_datafiles/rcmip_phase3_concentrations_v3.0.1.csv"
    )
    emissions = load("RCMIP3_input_datafiles/rcmip_phase3_emissions_v3.0.1.csv")
    forcing = load("RCMIP3_input_datafiles/rcmip_phase3_forcing_v3.0.1.csv")
    scenariomip_concentrations = load(
        "ScenarioMIP/rcmip_phase3_concentrations_ScenarioMIP_v3.0.1.csv"
    )
    scenariomip_forcing = load(
        "ScenarioMIP/rcmip_phase3_forcing_ScenarioMIP_v3.0.1.csv"
    )

    to_frame(
        "ssp245",
        [
            *to_concentrations(select(concentrations, "ssp245", "CMIP6")),
            *to_natural_forcing(select(forcing, "ssp245", "CMIP6")),
            *to_aerosol_emissions(select(emissions, "ssp245", "CMIP6")),
        ],
    ).to_csv(HERE / "cmip6-ssp245.csv")

    to_frame(
        "scen7-M",
        [
            *to_concentrations(select(scenariomip_concentrations, "scen7-M", "CMIP7")),
            *to_natural_forcing(select(scenariomip_forcing, "scen7-M", "CMIP7")),
            # No emissions for the CMIP7 scenarios, so history held constant
            *to_aerosol_emissions(
                select_history_then_constant(emissions, "historical", "CMIP7")
            ),
        ],
    ).to_csv(HERE / "cmip7-scen7-m.csv")


if __name__ == "__main__":
    main()
