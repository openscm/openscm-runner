# /// script
# requires-python = "==3.12.*"
# dependencies = [
#   "gcages==0.14.0",
#   "pandas>=3",
# ]
# ///
"""
Generate the AR6 scenario test data from the AR6 database

The infilled emissions AR6 ran MAGICC with
and the temperature percentiles AR6 published,
for one scenario (AIM/CGE 2.2 EN_NPi2020_900f).
This follows gcages' `tests/regression/ar6/convert_ar6_res_to_checking_csvs.py`
(https://github.com/openscm/gcages/blob/abd45753bf8e964de5302b8a6407cae0879956ee/tests/regression/ar6/convert_ar6_res_to_checking_csvs.py).
This script must never import `openscm_runner`.

The input is the AR6 database's climate file
(`AR6_Scenarios_Database_World_ALL_CLIMATE_v1.1.csv`, about 3GB),
from the AR6 Scenario Explorer (https://data.ece.iiasa.ac.at/ar6/,
you have to log in to download it, so we can't download it here).

Run with `uv run --locked --script generate_data.py <path to the climate file>`
(the environment is locked in `generate_data.py.lock`).
"""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path

import pandas as pd
from gcages.hashing import get_file_hash
from gcages.renaming import SupportedNamingConventions, convert_variable_name

HERE = Path(__file__).parent

AR6_DATABASE_SHA256 = "1e4d21c5089458d84678fc760dd32e7791cec7f1ee391450256e75dd0d5c376e"
"""
sha256 of `AR6_Scenarios_Database_World_ALL_CLIMATE_v1.1.csv`

(Its md5 is 4b8aea8270566584db9d893ff7b4562e, the same as the one gcages records.)
"""

MODEL = "AIM/CGE 2.2"
SCENARIO = "EN_NPi2020_900f"

OUT_STEM = "ar6-aim-cge-2-2-en-npi2020-900f"
OUT_INDEX_COLUMNS = ["model", "scenario", "region", "variable", "unit"]

INFILLED_PREFIX = "AR6 climate diagnostics|Infilled|"
# gcages selects these with `pix.ismatch(Variable="**|Surface Temperature**MAGICC**")`
TEMPERATURE_PATTERN = r"\|Surface Temperature.*MAGICC"

# Infilled variables which are sums of the others, so not inputs
# (AR6 WG3 names, gcages doesn't know how to rename them)
AGGREGATE_VARIABLES = (
    "Emissions|CO2",
    "Emissions|F-Gases",
    "Emissions|HFC",
    "Emissions|Kyoto Gases (AR5-GWP100)",
    "Emissions|Kyoto Gases (AR6-GWP100)",
    "Emissions|PFC",
)

# Halon1202 was an AR6 input, but its emissions were zero in every AR6 scenario,
# so we drop it for simplicity and consistency with AR7 scenarios
# (it isn't one of `AR6_SCENARIO_EMISSIONS_VARIABLES` in openscm-runner).
DROPPED_VARIABLES = ("Emissions|Halon1202",)

# The AR6 scenario input uses gcages' names.
# gcages 0.14.0 calls AR6 WG3's names `IAMC` (later versions call them `AR6_WG3`).
to_gcages_name = partial(
    convert_variable_name,
    from_convention=SupportedNamingConventions.IAMC,
    to_convention=SupportedNamingConventions.GCAGES,
)

UNIT_RENAMING = {
    # HFC245ca was a mislabelling in AR6.
    # The variable of interest was always HFC245fa.
    "kt HFC245ca/yr": "kt HFC245fa/yr",
    "kt HFC43-10/yr": "kt HFC4310mee/yr",
}


def check_hash(path: Path) -> None:
    sha256 = get_file_hash(path, algorithm="sha256")
    if sha256 != AR6_DATABASE_SHA256:
        msg = f"sha256 of {path} is {sha256}, not {AR6_DATABASE_SHA256}"
        raise AssertionError(msg)


def load_scenario(path: Path) -> pd.DataFrame:
    """Load the scenario's rows (in chunks, sensible as the file is so big)"""
    chunks = [
        chunk.loc[(chunk["Model"] == MODEL) & (chunk["Scenario"] == SCENARIO)]
        # pandas>=3 reads exactly the values in the file (earlier versions didn't)
        for chunk in pd.read_csv(path, chunksize=100_000)
    ]
    out = pd.concat(chunks)
    out.columns = out.columns.str.lower()

    return out.set_index(OUT_INDEX_COLUMNS)


def make_emissions(raw: pd.DataFrame) -> pd.DataFrame:
    infilled = raw.loc[
        raw.index.get_level_values("variable").str.startswith(INFILLED_PREFIX)
    ].rename(lambda v: v.removeprefix(INFILLED_PREFIX), level="variable")
    infilled = infilled.loc[
        ~infilled.index.get_level_values("variable").isin(AGGREGATE_VARIABLES)
    ]
    out = infilled.rename(to_gcages_name, level="variable").rename(
        lambda u: UNIT_RENAMING.get(u, u), level="unit"
    )
    out = out.loc[~out.index.get_level_values("variable").isin(DROPPED_VARIABLES)]

    # The infilled emissions start in 2015 (the columns before are empty)
    out = out.dropna(axis="columns", how="all")
    if out.isna().any().any() or out.columns[0] != "2015":
        raise AssertionError(out)

    return out.sort_index()


def make_temperatures(raw: pd.DataFrame) -> pd.DataFrame:
    return raw.loc[
        raw.index.get_level_values("variable").str.contains(TEMPERATURE_PATTERN)
    ].sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "ar6_database",
        type=Path,
        help="Path to AR6_Scenarios_Database_World_ALL_CLIMATE_v1.1.csv",
    )
    args = parser.parse_args()

    check_hash(args.ar6_database)
    raw = load_scenario(args.ar6_database)

    make_emissions(raw).to_csv(HERE / f"{OUT_STEM}.csv")
    make_temperatures(raw).to_csv(HERE / f"{OUT_STEM}-ar6-gsat-percentiles.csv")


if __name__ == "__main__":
    main()
