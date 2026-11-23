# /// script
# requires-python = "==3.11.*"
# dependencies = [
#   "pooch",
#   "pymagicc==2.1.5",
# ]
#
# [tool.uv]
# # pymagicc (via scmdata) breaks with newer packages (e.g. xarray),
# # so resolve as of a date when pymagicc 2.1.5 was current
# exclude-newer = "2024-04-01T00:00:00Z"
# ///
"""
Generate the acceptance data for `MAGICCAR6AdapterERFDrivenFromEquilibrium`

Runs MAGICC v7.5.3 with pymagicc
(an independent route to the adapter's, which doesn't use pymagicc),
for the first member of the AR6 probabilistic distribution.
This script must never import `openscm_runner`.

Run from this directory with
`uv run --env-file ../../../../../.env --script generate_data.py`
(the environment is locked in `generate_data.py.lock`).
MAGICC v7.5.3 and the AR6 probabilistic distribution are found as in the tests:
the paths in `MAGICC_AR6_V753_ROOT_DIR` and `MAGICC_AR6_PROBABILISTIC_DISTRIBUTION`
or, if they aren't set, downloaded from magicc.org with the token in
`MAGICC_AR6_DOWNLOAD_TOKEN`.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import pooch
from pymagicc.core import MAGICC7
from pymagicc.io import MAGICCData

HERE = Path(__file__).parent

DOWNLOAD_URL = "https://magicc.org/api/download?type={type}&token={token}"
# The official archives, as saved by pooch
# (they are served with `Content-Encoding: gzip`, so they arrive as .tar files).
# Type on magicc.org: (archive name, sha256, directory to extract into)
DOWNLOADS = {
    "MAGICC7": (
        "magicc-v7.5.3.tar",
        "948f9fdc37d91d01c93df8f147f4f125db9668afef55710eb84f6db7ae2ee75b",
        "magicc-v7.5.3",
    ),
    "AR6_PROBABILISTIC": (
        "magicc-ar6-0fd0f62-f023edb-drawnset.tar",
        "b289ca718cbc6d9dc06d95a389fb515c46eacedafcfe09aa0dca8d35c50767a8",
        "magicc-ar6-0fd0f62-f023edb-drawnset",
    ),
}

FIRST_YEAR = 1850
LAST_YEAR = 2100
END_YEAR_BUFFER = 3
SIGNIFICANT_FIGURES = 6
# The abrupt step is in the first year, the eruption-like dip starts in this year
ERUPTION_YEAR = 1883
# Years to save the expected output for
# (checking every year doesn't add much, this saves a lot of space).
# Every year for 10 years after the abrupt step and the dip,
# where the response changes quickly.
OUTPUT_YEARS = [
    *range(FIRST_YEAR, FIRST_YEAR + 10 + 1),
    *range(ERUPTION_YEAR, ERUPTION_YEAR + 10 + 1),
    2015,
    *range(2020, 2100 + 1, 10),
]

OUTPUTS = {
    # Our name: (MAGICC's name, pymagicc's name)
    "Surface Air Temperature Change": ("SURFACE_TEMP", "Surface Temperature"),
    "Effective Radiative Forcing": (
        "TOTAL_INCLVOLCANIC_ERF",
        "Effective Radiative Forcing",
    ),
    "Heat Uptake": ("HEATUPTAKE_EBALANCE_TOTAL", "HEATUPTAKE_EBALANCE_TOTAL"),
}

ERF_FILE = "PYMAGICC_EXTRA_RF.IN"


def download(magicc_type: str) -> Path:
    """Download from magicc.org (if not already downloaded), returning the directory"""
    archive_name, sha256, extract_dir = DOWNLOADS[magicc_type]
    cache_dir = Path(pooch.os_cache("openscm-runner")) / "magicc-ar6"
    # The URL includes the token, so keep it out of pooch's logs
    pooch.get_logger().setLevel("WARNING")
    pooch.retrieve(
        DOWNLOAD_URL.format(
            type=magicc_type, token=os.environ["MAGICC_AR6_DOWNLOAD_TOKEN"]
        ),
        known_hash=f"sha256:{sha256}",
        fname=archive_name,
        path=cache_dir,
        processor=pooch.Untar(extract_dir=extract_dir),
        # magicc.org can be slow to respond
        downloader=pooch.HTTPDownloader(timeout=60),
    )

    return cache_dir / extract_dir


def get_magicc_ar6() -> tuple[Path, Path]:
    """Get MAGICC's root and the AR6 probabilistic distribution, as the tests do"""
    magicc_root = os.environ.get("MAGICC_AR6_V753_ROOT_DIR")
    distribution = os.environ.get("MAGICC_AR6_PROBABILISTIC_DISTRIBUTION")
    if magicc_root and distribution:
        return Path(magicc_root), Path(distribution)

    return (
        download("MAGICC7"),
        download("AR6_PROBABILISTIC")
        / "0fd0f62-derived-metrics-id-f023edb-drawnset.json",
    )


def get_binary(magicc_root: Path) -> Path:
    system = platform.system()
    if system == "Darwin":
        name = (
            "magicc-darwin-arm64"
            if platform.machine() == "arm64"
            else "magicc-darwin-amd64"
        )
    elif system == "Linux":
        name = "magicc"
    else:
        raise NotImplementedError(system)

    return (magicc_root / "bin" / name).resolve()


def set_up_environment(magicc_root: Path) -> None:
    """Tell pymagicc where MAGICC is and help the macOS binary find gfortran"""
    os.environ["MAGICC_EXECUTABLE_7"] = str(get_binary(magicc_root))
    for path in (
        Path("/opt/homebrew/opt/gfortran/lib/gcc/current"),
        Path("/opt/homebrew/opt/gcc/lib/gcc/current"),
    ):
        if path.exists():
            os.environ["DYLD_LIBRARY_PATH"] = str(path)
            break


def make_inputs() -> pd.DataFrame:
    """
    Make the inputs (one row per experiment, years as columns)

    - a ramp with a volcanic eruption-like dip
    - an abrupt step (abrupt-2xCO2-like)
    """
    years = np.arange(FIRST_YEAR, LAST_YEAR + 1)
    ramp = np.linspace(0.0, 4.0, years.size)
    ramp[years == ERUPTION_YEAR] -= 3.0
    ramp[years == ERUPTION_YEAR + 1] -= 1.5
    step = np.full(years.size, 3.7)

    return pd.DataFrame(
        [ramp, step],
        index=pd.MultiIndex.from_tuples(
            [
                (scenario, "Effective Radiative Forcing", "World", "W/m^2")
                for scenario in ("erf-ramp-with-eruption", "erf-abrupt-step")
            ],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=years,
    )


def load_first_member(distribution: Path) -> tuple[str, dict[str, object]]:
    """Load the first member of the AR6 probabilistic distribution"""
    configurations = json.loads(distribution.read_text())["configurations"]
    first = configurations[0]

    return (
        str(first["paraset_id"]),
        {k.lower(): v for k, v in first["nml_allcfgs"].items()},
    )


def write_erf_file(magicc: MAGICC7, erf: pd.Series) -> None:
    """Write the ERF (zero in the start year) with pymagicc"""
    start_year = FIRST_YEAR - 1
    values = pd.concat(
        [
            pd.Series([0.0], index=[start_year]),
            erf,
            pd.Series(
                [erf.iloc[-1]] * END_YEAR_BUFFER,
                index=range(LAST_YEAR + 1, LAST_YEAR + 1 + END_YEAR_BUFFER),
            ),
        ]
    )
    mdata = MAGICCData(
        values.to_numpy(),
        index=[int(y) for y in values.index],
        columns={
            "model": ["unspecified"],
            "scenario": ["unspecified"],
            "climate_model": ["unspecified"],
            "variable": ["Radiative Forcing|Extra"],
            "region": ["World"],
            "unit": ["W/m^2"],
            "todo": ["SET"],
        },
    )
    mdata.metadata = {"header": "ERF for openscm-runner acceptance data"}
    mdata.write(str(Path(magicc.run_dir) / ERF_FILE), magicc_version=7)


def run_one(magicc: MAGICC7, config: dict[str, object], erf: pd.Series) -> pd.DataFrame:
    write_erf_file(magicc, erf)
    res = magicc.run(
        only=[pymagicc_name for _, pymagicc_name in OUTPUTS.values()],
        startyear=FIRST_YEAR - 1,
        endyear=LAST_YEAR + END_YEAR_BUFFER,
        **config,
        rf_total_runmodus="QEXTRA",
        rf_extra_read=1,
        file_extra_rf=ERF_FILE,
        rf_extra_offset=0.0,
        rf_extra_factor=1.0,
        rf_efficacy_qxtra=1.0,
        rf_preind_referenceyr=FIRST_YEAR - 1,
        rf_initialization_method="JUMPSTART",
        # MAGICC only writes the files we ask for (its default is none)
        out_dynamic_vars=[f"DAT_{magicc_name}" for magicc_name, _ in OUTPUTS.values()],
        out_ascii_binary="BINARY",
        out_binary_format=2,
    )

    df = res.filter(region="World").timeseries()
    out = []
    for variable, (_, pymagicc_name) in OUTPUTS.items():
        selected = df.xs(pymagicc_name, level="variable", drop_level=False)
        if selected.shape[0] != 1:
            raise AssertionError((variable, selected))

        values = selected.iloc[0]
        values.index = [t.year for t in values.index]
        (unit,) = selected.index.get_level_values("unit")
        out.append(((variable, "World", unit), values.loc[FIRST_YEAR:LAST_YEAR]))

    return pd.DataFrame(
        [v for _, v in out],
        index=pd.MultiIndex.from_tuples(
            [k for k, _ in out], names=["variable", "region", "unit"]
        ),
    )


def round_significant(df: pd.DataFrame) -> pd.DataFrame:
    return df.apply(
        lambda col: col.map(lambda v: float(f"{v:.{SIGNIFICANT_FIGURES}g}"))
    )


def main() -> None:
    magicc_root, distribution = get_magicc_ar6()
    set_up_environment(magicc_root)
    # Round first, so the input file is exactly what MAGICC was run with
    inputs = round_significant(make_inputs())
    member_id, config = load_first_member(distribution)

    outputs = []
    with MAGICC7() as magicc:
        for (scenario, *_), erf in inputs.iterrows():
            res = run_one(magicc, config, erf)
            res = pd.concat(
                {(scenario, member_id): res}, names=["scenario", "ensemble_member"]
            )
            outputs.append(res)

    expected = pd.concat(outputs)
    expected.columns = expected.columns.astype(int)
    expected = expected.reorder_levels(
        ["scenario", "variable", "region", "unit", "ensemble_member"]
    )

    inputs.to_csv(HERE / "input.csv")
    round_significant(expected.loc[:, OUTPUT_YEARS]).to_csv(
        HERE / "expected-output.csv"
    )


if __name__ == "__main__":
    main()
