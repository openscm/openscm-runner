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
Generate the acceptance data for the MAGICC AR6 adapters for AR6 scenarios

`MAGICCAR6AdapterAR6Scenario` (this directory)
and its variants (sibling directories, see `CASES`).
We generate them all in this one script, rather than one script per directory,
so the data generation can't get out of sync between the cases
and it is obvious what the difference between them is
(rather than having to diff multi-hundred line files).

Runs MAGICC v7.5.3 with pymagicc, the way the AR6 workflow did
(which used openscm-runner v1's MAGICC7 adapter, that itself used pymagicc;
an independent route to this package's adapter, which doesn't use pymagicc),
for the first member of the AR6 probabilistic distribution.
The input is the infilled AR6 emissions in `tests/test-data/ar6-scenarios`.
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
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pooch
from pymagicc.core import MAGICC7
from pymagicc.definitions import MAGICC7_EMISSIONS_UNITS
from pymagicc.io import MAGICCData

HERE = Path(__file__).parent
INPUT_FILE = (
    HERE.parents[3]
    / "test-data"
    / "ar6-scenarios"
    / "ar6-aim-cge-2-2-en-npi2020-900f.csv"
)
INPUT_INDEX_COLUMNS = ["model", "scenario", "region", "variable", "unit"]

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

START_YEAR = 1750
END_YEAR_BUFFER = 3
SIGNIFICANT_FIGURES = 6
# Years to save the expected output for
# (checking every year doesn't add much, this saves a lot of space)
OUTPUT_YEARS = [2015, *range(2020, 2100 + 1, 10)]

OUTPUTS = {
    # Our name: (MAGICC's name, pymagicc's name)
    "Surface Air Temperature Change": ("SURFACE_TEMP", "Surface Temperature"),
    "Effective Radiative Forcing": (
        "TOTAL_INCLVOLCANIC_ERF",
        "Effective Radiative Forcing",
    ),
    "Effective Radiative Forcing|Anthropogenic": (
        "TOTAL_ANTHRO_ERF",
        "Effective Radiative Forcing|Anthropogenic",
    ),
    "Effective Radiative Forcing|CO2": ("CO2_ERF", "Effective Radiative Forcing|CO2"),
    "Effective Radiative Forcing|CH4": ("CH4_ERF", "Effective Radiative Forcing|CH4"),
    "Effective Radiative Forcing|N2O": ("N2O_ERF", "Effective Radiative Forcing|N2O"),
    "Effective Radiative Forcing|F-Gases": (
        "FGASSUM_ERF",
        "Effective Radiative Forcing|F-Gases",
    ),
    "Effective Radiative Forcing|Montreal Protocol Halogen Gases": (
        "MHALOSUM_ERF",
        "Effective Radiative Forcing|Montreal Protocol Halogen Gases",
    ),
    "Effective Radiative Forcing|Aerosols": (
        "AEROSOL_ERF",
        "Effective Radiative Forcing|Aerosols",
    ),
    "Effective Radiative Forcing|Tropospheric Ozone": (
        "TROPOZ_ERF",
        "Effective Radiative Forcing|Tropospheric Ozone",
    ),
    "Effective Radiative Forcing|Stratospheric Ozone": (
        "STRATOZ_ERF",
        "Effective Radiative Forcing|Stratospheric Ozone",
    ),
    "Effective Radiative Forcing|Land-use Change": (
        "LANDUSE_ERF",
        "Effective Radiative Forcing|Land-use Change",
    ),
    "Effective Radiative Forcing|Solar": (
        "SOLAR_ERF",
        "Effective Radiative Forcing|Solar",
    ),
    "Effective Radiative Forcing|Volcanic": (
        "VOLCANIC_ANNUAL_ERF",
        "Effective Radiative Forcing|Volcanic",
    ),
    "Atmospheric Concentrations|CO2": ("CO2_CONC", "Atmospheric Concentrations|CO2"),
    "Atmospheric Concentrations|CH4": ("CH4_CONC", "Atmospheric Concentrations|CH4"),
    "Atmospheric Concentrations|N2O": ("N2O_CONC", "Atmospheric Concentrations|N2O"),
    "Heat Uptake": ("HEATUPTAKE_EBALANCE_TOTAL", "HEATUPTAKE_EBALANCE_TOTAL"),
}

# Our name: pymagicc's name, where they differ
EMISSIONS_RENAMING = {
    "Emissions|CO2|Fossil": "Emissions|CO2|MAGICC Fossil and Industrial",
    "Emissions|CO2|Biosphere": "Emissions|CO2|MAGICC AFOLU",
    "Emissions|HFC4310mee": "Emissions|HFC4310",
}

# Halon1202 was an AR6 input, but its emissions were zero in every AR6 scenario,
# so it isn't part of the AR6 scenario input and the adapter uses zero emissions
ZERO_EMISSIONS = {"Emissions|Halon1202": "kt Halon1202/yr"}

SCENARIO_FILE = "ACCEPTANCE.SCEN7"


@dataclass(frozen=True)
class Case:
    """An acceptance case: how to run MAGICC and what to save"""

    rf_total_runmodus: str
    """Which forcing drives the climate (MAGICC's `RF_TOTAL_RUNMODUS`)"""

    outputs_not_offered: tuple[str, ...] = ()
    """Outputs the adapter doesn't offer, so we don't save them"""

    co2_only: bool = False
    """
    Whether only CO2 is part of the run

    If `True`, only the input's CO2 emissions are used
    and everything else is held at pre-industrial (1750) for the whole run
    (see `hold_non_co2_at_pre_industrial`).
    """

    expected_magicc_warnings: tuple[str, ...] = ()
    """
    Warnings MAGICC logs which we expect (and so don't report)

    Any other warning is an error.
    """


CASES = {
    # Directory (sibling of this one): case
    "ar6-scenario": Case(rf_total_runmodus="ALL"),
    "ar6-scenario-anthropogenic-only": Case(
        rf_total_runmodus="ANTHROPOGENIC",
        # In this mode, MAGICC only changes the total forcing
        # (`src/MAGICC7.f90` in MAGICC v7.5.3, around lines 5276 and 9522).
        # It still reports the solar and volcanic forcing it would have applied,
        # but they aren't part of the run, so the adapter doesn't offer them.
        outputs_not_offered=(
            "Effective Radiative Forcing|Solar",
            "Effective Radiative Forcing|Volcanic",
        ),
    ),
    # This may still change: what is meant by CO2-only is still unclear
    # (e.g. which feedbacks should be included, see roadmap item B16).
    "ar6-scenario-co2-forcing-only": Case(
        rf_total_runmodus="CO2",
        # As for anthropogenic-only, MAGICC still reports every forcing
        # it would have applied, but only CO2 forcing is part of the run
        outputs_not_offered=tuple(
            v
            for v in OUTPUTS
            if v.startswith("Effective Radiative Forcing|")
            and v != "Effective Radiative Forcing|CO2"
        ),
        # Just changing `RF_TOTAL_RUNMODUS` isn't enough to match the adapter
        # (it gives 0.0175 K more warming by 2100 for this scenario):
        # MAGICC would still add the CO2 from the oxidation of fossil CH4
        # (almost all of the difference)
        # and the other gases' concentrations would follow the scenario
        # (which matters for N2O, because MAGICC's CO2 forcing depends on it).
        co2_only=True,
        # MAGICC extends its BC-on-snow forcing past the end of its input file
        # by scaling with BC emissions,
        # which are zero here, so it can't (once per hemisphere).
        # BC-on-snow forcing isn't part of the run, so this doesn't matter.
        expected_magicc_warnings=(
            "[extend_rf_box_from_switchyear_with_emissions] <WARNING> "
            "Not performing extrapolation",
        ),
    ),
}


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


def load_inputs() -> pd.DataFrame:
    out = pd.read_csv(INPUT_FILE).set_index(INPUT_INDEX_COLUMNS)
    out.columns = out.columns.astype(int)

    return out


def load_first_member(distribution: Path) -> tuple[str, dict[str, object]]:
    """Load the first member of the AR6 probabilistic distribution"""
    configurations = json.loads(distribution.read_text())["configurations"]
    first = configurations[0]

    return (
        str(first["paraset_id"]),
        {k.lower(): v for k, v in first["nml_allcfgs"].items()},
    )


def to_magicc_emissions(emissions: pd.DataFrame) -> MAGICCData:
    """
    Convert to pymagicc's names and MAGICC's units

    As openscm-runner v1's MAGICC7 adapter did
    (`_convert_to_magicc_units`).
    """
    zeros = pd.DataFrame(
        0.0,
        index=pd.MultiIndex.from_tuples(
            [
                (*emissions.index[0][:3], variable, unit)
                for variable, unit in ZERO_EMISSIONS.items()
            ],
            names=emissions.index.names,
        ),
        columns=emissions.columns,
    )
    emissions = pd.concat([emissions, zeros]).rename(
        lambda v: EMISSIONS_RENAMING.get(v, v), level="variable"
    )
    last_year = emissions.columns.max()
    for year in range(last_year + 1, last_year + 1 + END_YEAR_BUFFER):
        emissions[year] = emissions[last_year]

    magicc_units = MAGICC7_EMISSIONS_UNITS.set_index("magicc_variable")[
        "emissions_unit"
    ]
    out = MAGICCData(emissions)
    for variable in out.get_unique_meta("variable"):
        magicc_name = variable.removeprefix("Emissions|").replace("|", "_")
        magicc_name = {
            "CO2_MAGICC Fossil and Industrial": "CO2I",
            "CO2_MAGICC AFOLU": "CO2B",
        }.get(magicc_name, magicc_name.upper())
        if "NOx" in variable:
            context = "NOx_conversions"
        elif "NH3" in variable:
            context = "NH3_conversions"
        else:
            context = None

        out = out.convert_unit(
            magicc_units[magicc_name], variable=variable, context=context
        )

    return out


def make_co2_only_inputs(inputs: pd.DataFrame) -> pd.DataFrame:
    """Set every emission except CO2 to zero (they don't matter, see below)"""
    out = inputs.copy()
    out.loc[
        ~out.index.get_level_values("variable").str.startswith("Emissions|CO2|")
    ] = 0.0

    return out


def hold_non_co2_at_pre_industrial(magicc: MAGICC7, end_year: int) -> dict[str, object]:
    """
    Hold everything except CO2 at pre-industrial (1750) for the whole run

    Every gas except CO2 is concentration-driven for the whole run,
    with its concentrations held at their 1750 values
    (so their emissions don't matter).
    Fossil CH4 emissions are zero for the whole run (history included),
    because MAGICC adds the CO2 from their oxidation to the fossil CO2 emissions
    (even if CH4 is concentration-driven).

    Writes the files into the run directory and returns the settings to use them.
    """
    defaults = magicc.default_config["nml_allcfgs"]
    run_dir = Path(magicc.run_dir)

    def write_held(filename: str, *, value: float | None = None) -> str:
        if not filename:
            # No file (e.g. MAGICC has no concentrations for Halon1202),
            # so MAGICC uses zero, which is also its 1750 value
            return filename

        original = MAGICCData(str(run_dir / filename))
        timeseries = original.timeseries()
        if value is None:
            if timeseries.columns[-1].year < end_year:
                raise AssertionError((filename, timeseries.columns[-1]))

            held = timeseries[[c for c in timeseries.columns if c.year == START_YEAR]]
            timeseries.loc[:, :] = held.to_numpy()
        else:
            timeseries.loc[:, :] = value

        out = MAGICCData(timeseries)
        out.metadata = {"header": f"{filename} held at {START_YEAR} values"}
        name = f"ACCEPTANCE_PI_{filename}"
        out.write(str(run_dir / name), magicc_version=7)

        return name

    return {
        # Concentration-driven for the whole run
        **{
            f"{group}_switchfromconc2emis_year": end_year + 1
            for group in ("ch4", "n2o", "fgas", "mhalo")
        },
        "file_ch4_conc": write_held(defaults["file_ch4_conc"]),
        "file_n2o_conc": write_held(defaults["file_n2o_conc"]),
        "fgas_files_conc": [write_held(f) for f in defaults["fgas_files_conc"]],
        "mhalo_files_conc": [write_held(f) for f in defaults["mhalo_files_conc"]],
        # No fossil CH4, so no CO2 from its oxidation
        "file_ch4i_emis": write_held(defaults["file_ch4i_emis"], value=0.0),
    }


def write_scenario_file(magicc: MAGICC7, emissions: MAGICCData) -> None:
    writer = MAGICCData(emissions.timeseries())
    writer["todo"] = "SET"
    writer.metadata = {"header": "Scenario for openscm-runner acceptance data"}
    writer.write(str(Path(magicc.run_dir) / SCENARIO_FILE), magicc_version=7)


def run(
    magicc: MAGICC7,
    config: dict[str, object],
    last_year: int,
    rf_total_runmodus: str,
    extra_settings: dict[str, object],
    expected_magicc_warnings: tuple[str, ...],
) -> pd.DataFrame:
    with warnings.catch_warnings():
        # pymagicc warns whenever MAGICC logs a warning (without saying which),
        # we check MAGICC's warnings ourselves below
        warnings.filterwarnings("ignore", message="magicc logged a WARNING message")
        res = magicc.run(
            only=[pymagicc_name for _, pymagicc_name in OUTPUTS.values()],
            startyear=START_YEAR,
            endyear=last_year + END_YEAR_BUFFER,
            **config,
            file_emisscen=SCENARIO_FILE,
            **{f"file_emisscen_{i}": "NONE" for i in range(2, 9)},
            rf_total_runmodus=rf_total_runmodus,
            **extra_settings,
            # MAGICC only writes the files we ask for (its default is none)
            out_dynamic_vars=[
                f"DAT_{magicc_name}" for magicc_name, _ in OUTPUTS.values()
            ],
            out_ascii_binary="BINARY",
            out_binary_format=2,
        )

    unexpected_warnings = [
        line
        for line in res.metadata["stderr"].splitlines()
        if "<WARNING>" in line
        and not any(expected in line for expected in expected_magicc_warnings)
    ]
    if unexpected_warnings:
        raise AssertionError("\n".join(unexpected_warnings))

    df = res.filter(region="World").timeseries()
    out = []
    for variable, (_, pymagicc_name) in OUTPUTS.items():
        selected = df.xs(pymagicc_name, level="variable", drop_level=False)
        if selected.shape[0] != 1:
            raise AssertionError((variable, selected))

        values = selected.iloc[0]
        values.index = [t.year for t in values.index]
        (unit,) = selected.index.get_level_values("unit")
        out.append(((variable, "World", unit), values.loc[START_YEAR:last_year]))

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
    inputs = load_inputs()
    (model,) = inputs.index.get_level_values("model").unique()
    (scenario,) = inputs.index.get_level_values("scenario").unique()
    member_id, config = load_first_member(distribution)

    last_year = inputs.columns.max()
    with MAGICC7() as magicc:
        for directory, case in CASES.items():
            if case.co2_only:
                emissions = make_co2_only_inputs(inputs)
                extra_settings = hold_non_co2_at_pre_industrial(
                    magicc, end_year=last_year + END_YEAR_BUFFER
                )
            else:
                emissions = inputs
                extra_settings = {}

            write_scenario_file(magicc, to_magicc_emissions(emissions))
            res = run(
                magicc,
                config,
                last_year=last_year,
                rf_total_runmodus=case.rf_total_runmodus,
                extra_settings=extra_settings,
                expected_magicc_warnings=case.expected_magicc_warnings,
            )
            res = res.loc[
                ~res.index.get_level_values("variable").isin(case.outputs_not_offered)
            ]

            expected = pd.concat(
                {(model, scenario, member_id): res},
                names=["model", "scenario", "ensemble_member"],
            )
            expected.columns = expected.columns.astype(int)
            expected = expected.reorder_levels(
                ["model", "scenario", "variable", "region", "unit", "ensemble_member"]
            )

            round_significant(expected.loc[:, OUTPUT_YEARS]).to_csv(
                HERE.parent / directory / "expected-output.csv"
            )


if __name__ == "__main__":
    main()
