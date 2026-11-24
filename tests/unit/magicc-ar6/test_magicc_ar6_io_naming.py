"""
Unit tests of the MAGICC adapters' file writing and name/unit translation

These don't need MAGICC.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openscm_runner.adapters.magicc_ar6.base import hold_last_value
from openscm_runner.adapters.magicc_ar6.io import (
    format_conc_in,
    format_hemispheric_monthly_forcing_in,
    format_scen7,
    format_tabular_file,
    read_binout,
    read_tabular_file,
)
from openscm_runner.adapters.magicc_ar6.naming import (
    from_magicc_output,
    split_natural_forcing,
    to_magicc_concentrations,
    to_magicc_emissions,
    to_magicc_gas,
)
from openscm_runner.adapters.magicc_ar6.running import MAGICCInstallation

pint = pytest.importorskip("pint")

pytestmark = pytest.mark.magicc_ar6

TEST_DATA_DIR = Path(__file__).parents[2] / "test-data"


def make_emissions(rows: dict[tuple[str, str], float]) -> pd.DataFrame:
    return pd.DataFrame(
        [[v, v] for v in rows.values()],
        index=pd.MultiIndex.from_tuples(list(rows), names=["variable", "unit"]),
        columns=[2015, 2016],
    )


def test_to_magicc_emissions_conversions() -> None:
    res = to_magicc_emissions(
        make_emissions(
            {
                ("Emissions|CO2|Fossil", "Mt CO2/yr"): 44_000.0,
                ("Emissions|CO2|Biosphere", "Mt CO2/yr"): 4_400.0,
                ("Emissions|N2O", "kt N2O/yr"): 4_400.0,
                ("Emissions|SOx", "Mt SO2/yr"): 100.0,
                ("Emissions|NOx", "Mt NO2/yr"): 46.0,
                ("Emissions|NH3", "Mt NH3/yr"): 17.0,
                ("Emissions|NMVOC", "Mt VOC/yr"): 3.0,
                ("Emissions|HFC4310mee", "kt HFC4310mee/yr"): 2.0,
                ("Emissions|cC4F8", "kt cC4F8/yr"): 1.0,
            }
        )
    )[2015]

    exp = {
        ("CO2I", "Gt C / yr"): 12.0,
        ("CO2B", "Gt C / yr"): 1.2,
        ("N2O", "Mt N2ON / yr"): 2.8,
        ("SOX", "Mt S / yr"): 50.0,
        ("NOX", "Mt N / yr"): 14.0,
        ("NH3", "Mt N / yr"): 14.0,
        ("NMVOC", "Mt NMVOC / yr"): 3.0,
        ("HFC4310", "kt HFC4310 / yr"): 2.0,
        ("CC4F8", "kt CC4F8 / yr"): 1.0,
    }
    for key, value in exp.items():
        np.testing.assert_allclose(res.loc[key], value)


def test_to_magicc_emissions_all_ar6_species() -> None:
    scenario = pd.read_csv(
        TEST_DATA_DIR / "ar6-scenarios" / "ar6-aim-cge-2-2-en-npi2020-900f.csv"
    ).set_index(["model", "scenario", "region", "variable", "unit"])
    scenario.columns = scenario.columns.astype(int)

    res = to_magicc_emissions(scenario)

    assert res.shape[0] == scenario.shape[0]
    assert not res.index.get_level_values("variable").duplicated().any()


@pytest.mark.parametrize(
    "variable",
    ("Emissions|CO2|Other", "Emissions|Junk", "Atmospheric Concentrations|CO2"),
)
def test_to_magicc_emissions_unsupported_variable(variable: str) -> None:
    with pytest.raises(ValueError, match="aren't supported for MAGICC"):
        to_magicc_emissions(make_emissions({(variable, "Mt CO2/yr"): 1.0}))


def test_to_magicc_emissions_converts_any_compatible_unit() -> None:
    res = to_magicc_emissions(
        make_emissions({("Emissions|CO2|Fossil", "Mt C/yr"): 1000.0})
    )
    np.testing.assert_allclose(res.loc[("CO2I", "Gt C / yr")], 1.0)


def test_to_magicc_emissions_incompatible_unit() -> None:
    with pytest.raises(pint.DimensionalityError):
        to_magicc_emissions(
            make_emissions({("Emissions|CO2|Fossil", "Mt CH4/yr"): 1.0})
        )


def test_to_magicc_emissions_duplicate_variable() -> None:
    emissions = pd.DataFrame(
        [[1.0, 1.0], [2.0, 2.0]],
        index=pd.MultiIndex.from_tuples(
            [
                ("Emissions|CH4", "World", "Mt CH4/yr"),
                ("Emissions|CH4", "R5ASIA", "Mt CH4/yr"),
            ],
            names=["variable", "region", "unit"],
        ),
        columns=[2015, 2016],
    )
    with pytest.raises(ValueError, match=r"more than once: \['Emissions\|CH4'\]"):
        to_magicc_emissions(emissions)


def test_to_magicc_gas() -> None:
    assert to_magicc_gas("HFC4310mee") == "HFC4310"
    assert to_magicc_gas("cC4F8") == "CC4F8"
    # The full mapping is written out, nothing passes through unchecked
    with pytest.raises(ValueError, match="isn't a gas MAGICC knows"):
        to_magicc_gas("HFC4310MEE")


def test_to_magicc_concentrations() -> None:
    res = to_magicc_concentrations(
        make_emissions(
            {
                ("Atmospheric Concentrations|CO2", "ppm"): 280.0,
                ("Atmospheric Concentrations|CH4", "ppm"): 0.8,
                ("Atmospheric Concentrations|HFC4310mee", "ppt"): 1.0,
            }
        )
    )
    assert res.loc["CO2", 2016] == 280.0
    np.testing.assert_allclose(res.loc["CH4", 2015], 800.0)
    assert res.loc["HFC4310", 2015] == 1.0

    with pytest.raises(pint.DimensionalityError):
        to_magicc_concentrations(
            make_emissions({("Atmospheric Concentrations|CO2", "W/m^2"): 280.0})
        )


def test_split_natural_forcing() -> None:
    rest, natural = split_natural_forcing(
        make_emissions(
            {
                ("Atmospheric Concentrations|CO2", "ppm"): 280.0,
                ("Effective Radiative Forcing|Solar", "mW/m^2"): 100.0,
            }
        )
    )
    assert rest.index.get_level_values("variable").tolist() == [
        "Atmospheric Concentrations|CO2"
    ]
    assert list(natural) == ["SOLAR"]
    np.testing.assert_allclose(natural["SOLAR"].to_numpy(), 0.1)


def test_hold_last_value() -> None:
    start = pd.DataFrame(
        [[1.0, 3.0], [np.nan, 2.0]],
        index=pd.Index(["a", "b"], name="variable"),
        columns=[2015, 2016],
    )
    res = hold_last_value(start, 3)

    assert res.columns.tolist() == [2015, 2016, 2017, 2018, 2019]
    np.testing.assert_allclose(res.loc["a"].to_numpy(), [1.0, 3.0, 3.0, 3.0, 3.0])
    # Existing values (even NaN) are untouched
    np.testing.assert_allclose(res.loc["b"].to_numpy(), [np.nan, 2.0, 2.0, 2.0, 2.0])
    # The input isn't changed
    assert start.columns.tolist() == [2015, 2016]


def test_scen7_round_trip(tmp_path: Path) -> None:
    emissions = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]],
        index=pd.MultiIndex.from_tuples(
            [("CO2I", "Gt C / yr"), ("SOX", "Mt S / yr")], names=["variable", "unit"]
        ),
        columns=[2015, 2016],
    )
    path = tmp_path / "TEST.SCEN7"
    path.write_text(format_scen7(emissions), encoding="latin-1")

    data, spec = read_tabular_file(path)
    assert spec["THISFILE_DATTYPE"] == "SCEN7"
    assert spec["THISFILE_REGIONMODE"] == "WORLD"
    assert spec["THISFILE_FIRSTYEAR"] == 2015
    assert "GAS" in path.read_text()
    np.testing.assert_allclose(data.to_numpy(), emissions.to_numpy())


def test_scen7_requires_units() -> None:
    # Index of MAGICC's gas names only: the caller has to say what the units are
    emissions = pd.DataFrame([[1.0, 2.0]], index=["CO2I"], columns=[2015, 2016])

    with pytest.raises(ValueError, match=r"`variable` and `unit` index levels"):
        format_scen7(emissions)


def test_scen7_wrong_unit_raises() -> None:
    emissions = pd.DataFrame(
        [[1.0, 2.0]],
        index=pd.MultiIndex.from_tuples(
            [("CO2I", "Mt CO2 / yr")], names=["variable", "unit"]
        ),
        columns=[2015, 2016],
    )

    with pytest.raises(ValueError, match=r"Not MAGICC's units.*CO2I.*Mt CO2 / yr"):
        format_scen7(emissions)


def test_scen7_unknown_gas_raises() -> None:
    emissions = pd.DataFrame(
        [[1.0, 2.0]],
        index=pd.MultiIndex.from_tuples(
            [("CO2", "Gt C / yr")], names=["variable", "unit"]
        ),
        columns=[2015, 2016],
    )

    with pytest.raises(ValueError, match=r"Not gases a \.SCEN7 file can have.*CO2"):
        format_scen7(emissions)


def test_conc_in_round_trip(tmp_path: Path) -> None:
    values = pd.Series([277.0, 280.0, 290.0], index=[1750, 1751, 1752])
    path = tmp_path / "CO2_CONC.IN"
    path.write_text(format_conc_in("CO2", values), encoding="latin-1")

    data, spec = read_tabular_file(path)
    assert spec["THISFILE_UNITS"] == "ppm"
    assert data.columns.tolist() == [1750, 1751, 1752]
    np.testing.assert_allclose(data.to_numpy()[0], values.to_numpy())


def test_monthly_forcing_times(tmp_path: Path) -> None:
    values = pd.Series([0.0, 1.0], index=[1750, 1751])
    path = tmp_path / "VOLCANIC_RF.MON"
    path.write_text(
        format_hemispheric_monthly_forcing_in("VOLCANIC_ANNUAL_RF", values),
        encoding="latin-1",
    )

    data, spec = read_tabular_file(path)
    assert spec["THISFILE_ANNUALSTEPS"] == 12
    assert data.shape == (2, 24)
    # MAGICC's convention: start of each month, three decimal places
    assert data.columns[1] == 1750.083
    np.testing.assert_allclose(data.iloc[:, 12:].to_numpy(), 1.0)


def test_installation_binary_is_absolute() -> None:
    """MAGICC is run from a temporary directory, so a relative root must still work"""
    installation = MAGICCInstallation(
        root_dir=Path("relative") / "magicc", expected_version="v7.5.3"
    )
    assert installation.binary.is_absolute()

    with_override = MAGICCInstallation(
        root_dir=Path("relative"),
        expected_version="v7.5.3",
        binary_path=Path("bin") / "magicc",
    )
    assert with_override.binary.is_absolute()
    assert with_override.binary.name == "magicc"


def test_format_tabular_file_last_label_row_must_be_years() -> None:
    with pytest.raises(ValueError, match="The last label row must be YEARS"):
        format_tabular_file(
            pd.DataFrame([[1.0]], index=["CO2"], columns=[2000]),
            specifications={},
            header="test",
            label_rows={"YEARS": ["CO2"], "GAS": ["CO2"]},
        )


def test_format_tabular_file_default_label_rows() -> None:
    """Without label rows, a single YEARS row of `data`'s index"""
    res = format_tabular_file(
        pd.DataFrame([[1.0], [2.0]], index=["CO2", "CH4"], columns=[2000]),
        specifications={},
        header="test",
    )

    (years_row,) = (line for line in res.splitlines() if "YEARS" in line)
    assert years_row.split() == ["YEARS", "CO2", "CH4"]


def fortran_record(payload: bytes, end_size: int | None = None) -> bytes:
    """Fortran unformatted sequential record (as MAGICC's binary output uses)"""
    size = len(payload)
    end = size if end_size is None else end_size

    return struct.pack("<i", size) + payload + struct.pack("<i", end)


@pytest.mark.parametrize(
    "contents, error, match",
    (
        pytest.param(
            fortran_record(b"magicc", end_size=5),
            ValueError,
            "Corrupt record",
            id="corrupt-record",
        ),
        pytest.param(
            fortran_record(b"pymagicc"),
            ValueError,
            "is not a version 2 binary output file",
            id="not-binout",
        ),
        pytest.param(
            fortran_record(b"magicc") + fortran_record(struct.pack("<h", 1)),
            NotImplementedError,
            "Only version 2 binary output is supported",
            id="version-1",
        ),
        pytest.param(
            fortran_record(b"magicc")
            + fortran_record(struct.pack("<h", 2))
            # Columns, first year, last year, then steps per year
            + b"".join(fortran_record(struct.pack("<I", v)) for v in (1, 1850, 1851))
            + fortran_record(struct.pack("<I", 12)),
            NotImplementedError,
            "Only annual binary output is supported",
            id="monthly",
        ),
    ),
)
def test_read_binout_errors(
    tmp_path: Path, contents: bytes, error: type[Exception], match: str
) -> None:
    path = tmp_path / "DAT_TEST.BINOUT"
    path.write_bytes(contents)

    with pytest.raises(error, match=match):
        read_binout(path)


def make_raw_output(rows: dict[tuple[str, str, str], list[float]]) -> pd.DataFrame:
    return pd.DataFrame(
        list(rows.values()),
        index=pd.MultiIndex.from_tuples(
            list(rows), names=["variable", "region", "unit"]
        ),
        columns=[1850, 1851, 1852],
    )


def test_from_magicc_output_without_experiment_levels() -> None:
    raw = make_raw_output(
        {
            ("SURFACE_TEMP", "GLOBAL", "K"): [0.0, 0.1, 0.2],
            ("SURFACE_TEMP", "NHLAND", "K"): [0.0, 0.3, 0.4],
        }
    )

    res = from_magicc_output(
        raw,
        output_variables={"Surface Air Temperature Change": "SURFACE_TEMP"},
        first_year=1851,
        last_year=1851,
        experiment_levels={},
    )

    pd.testing.assert_frame_equal(
        res,
        pd.DataFrame(
            [[0.1]],
            index=pd.MultiIndex.from_tuples(
                [("Surface Air Temperature Change", "World", "K")],
                names=["variable", "region", "unit"],
            ),
            columns=[1851],
        ),
    )


def test_from_magicc_output_more_than_one_timeseries() -> None:
    raw = make_raw_output(
        {
            ("SURFACE_TEMP", "GLOBAL", "K"): [0.0, 0.1, 0.2],
            ("SURFACE_TEMP", "GLOBAL", "mK"): [0.0, 100.0, 200.0],
        }
    )

    with pytest.raises(ValueError, match="Expected exactly one SURFACE_TEMP GLOBAL"):
        from_magicc_output(
            raw,
            output_variables={"Surface Air Temperature Change": "SURFACE_TEMP"},
            first_year=1850,
            last_year=1852,
            experiment_levels={},
        )
