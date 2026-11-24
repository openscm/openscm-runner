"""
Reading and writing MAGICC's file formats

Only the formats the adapters need:
the tabular input files (`.IN`, `.MON`, `.SCEN7`),
namelists (`.CFG`)
and the binary output (`.BINOUT`, version 2).

Copied (no dependency) from `magicc_core.testing.io` in the MAGICC repository
(which deliberately avoids pymagicc and scmdata), with small changes:

- only formatting the tabular files (`format_tabular_file`),
  which can write a `METADATA` block-free header
  and takes the `THISFILE_*` entries MAGICC needs for `.SCEN7` files
- f90nml is imported lazily, so it is only needed if MAGICC is actually used
  (see [openscm_runner.optional_dependencies][])
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from openscm_runner.optional_dependencies import import_optional_dependency

MAGICC_FILE_ENCODING = "latin-1"
"""Encoding MAGICC's own input files use"""

TIME_COLUMN_WIDTH = 11
"""Width of the time column in MAGICC's tabular files"""

DATA_COLUMN_WIDTH = 26
"""Width of every data column in MAGICC's tabular files"""

VALUE_FORMAT = ".16e"
"""
Format used for the values we write

Enough digits to round-trip a double exactly,
so MAGICC reads exactly the numbers we were given.
"""

BINOUT_VERSION = 2
"""Version of the binary output format we read"""

ANNUAL_STEPS = 1
"""Steps per year of the binary output we read (annual)"""


def _import_f90nml(callable_name: str) -> Any:
    return import_optional_dependency(
        "f90nml", requirement="f90nml", callable_name=callable_name, extra="magicc-ar6"
    )


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return f"'{value}'"

    return str(value)


def _format_time(time: float, annualsteps: int) -> str:
    if annualsteps == 1:
        return f"{round(time)}"

    return f"{round(time, 3):.6f}"


def format_tabular_file(
    data: pd.DataFrame,
    *,
    specifications: Mapping[str, Any],
    header: str,
    label_rows: Mapping[str, Sequence[str]] | None = None,
    annualsteps: int = 1,
) -> str:
    """
    Format one of MAGICC's tabular input files

    Parameters
    ----------
    data
        Values to write, one row per data column of the file,
        with time as the columns

    specifications
        `THISFILE_SPECIFICATIONS` entries to write.
        The entries which describe the shape of the data
        (`THISFILE_DATACOLUMNS`, `THISFILE_DATAROWS`, `THISFILE_FIRSTYEAR`,
        `THISFILE_LASTYEAR`, `THISFILE_ANNUALSTEPS`, `THISFILE_FIRSTDATAROW`)
        are always computed from `data`.

    header
        Free text for the file's header

    label_rows
        Rows of column labels to write above the data, in order,
        keyed by the label in the time column (e.g. `{"GAS": [...], "YEARS": [...]}`).
        The last one must be `"YEARS"`, which is what MAGICC looks for.
        If not supplied, a single `YEARS` row is written using `data`'s index.

    annualsteps
        Steps per year in `data`

    Returns
    -------
    :
        Contents of the file
    """
    if label_rows is None:
        label_rows = {"YEARS": [str(v) for v in data.index]}

    if list(label_rows)[-1] != "YEARS":
        msg = f"The last label row must be YEARS, received {list(label_rows)}"
        raise ValueError(msg)

    times = [float(t) for t in data.columns]
    shape_keys = {
        "THISFILE_DATACOLUMNS",
        "THISFILE_DATAROWS",
        "THISFILE_FIRSTYEAR",
        "THISFILE_LASTYEAR",
        "THISFILE_FIRSTDATAROW",
        "THISFILE_ANNUALSTEPS",
    }
    spec: dict[str, Any] = {
        "THISFILE_DATACOLUMNS": len(data.index),
        "THISFILE_DATAROWS": len(times),
        "THISFILE_FIRSTYEAR": int(np.floor(min(times))),
        "THISFILE_LASTYEAR": int(np.floor(max(times))),
        "THISFILE_ANNUALSTEPS": annualsteps,
        **{k: v for k, v in specifications.items() if k not in shape_keys},
    }

    preamble = ["---- HEADER ----", "", header, ""]
    # One-based line number of the first data row:
    # the preamble, the namelist (opening line, entries, closing line),
    # the label rows, then the data.
    spec["THISFILE_FIRSTDATAROW"] = (
        len(preamble) + 1 + len(spec) + 1 + 1 + len(label_rows) + 1
    )

    lines = [*preamble, "&THISFILE_SPECIFICATIONS"]
    lines.extend(f"    {key} = {_format_value(value)}" for key, value in spec.items())
    lines.append("/")
    for label, labels in label_rows.items():
        lines.append(
            f"{label:>{TIME_COLUMN_WIDTH}}"
            + "".join(f"{v:>{DATA_COLUMN_WIDTH}}" for v in labels)
        )

    values = data.to_numpy(dtype=float)
    for i, time in enumerate(times):
        lines.append(
            f"{_format_time(time, annualsteps):>{TIME_COLUMN_WIDTH}}"
            + "".join(
                f"{value:>{DATA_COLUMN_WIDTH}{VALUE_FORMAT}}" for value in values[:, i]
            )
        )

    return "\n".join(lines) + "\n"


def read_tabular_file(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Read one of MAGICC's tabular input files, every column

    Parameters
    ----------
    path
        File to read

    Returns
    -------
    data :
        Values, indexed by the labels in the file's `YEARS` row,
        with time as the columns

    specifications :
        The file's `THISFILE_SPECIFICATIONS`
    """
    f90nml = _import_f90nml("read_tabular_file")

    lines = Path(path).read_text(encoding=MAGICC_FILE_ENCODING).splitlines()

    start = next(
        i
        for i, line in enumerate(lines)
        if line.strip().upper().startswith("&THISFILE_SPECIFICATIONS")
    )
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "/")
    specifications = {
        k.upper(): v
        for k, v in f90nml.reads("\n".join(lines[start : end + 1]))[
            "thisfile_specifications"
        ].items()
    }

    years_row = next(
        i
        for i in range(end, len(lines))
        if lines[i].split() and lines[i].split()[0].upper() == "YEARS"
    )
    labels = lines[years_row].split()[1:]

    times = []
    rows = []
    for line in lines[years_row + 1 :]:
        parts = line.split()
        if len(parts) != len(labels) + 1:
            continue

        times.append(float(parts[0]))
        rows.append([float(v) for v in parts[1:]])

    data = pd.DataFrame(
        np.array(rows).T,
        index=pd.Index(labels, name="label"),
        columns=times,
    )
    if int(specifications.get("THISFILE_ANNUALSTEPS", 1)) == 1:
        data = data.set_axis([round(float(t)) for t in data.columns], axis="columns")

    return data, specifications


def write_namelist(path: Path, namelists: Mapping[str, Mapping[str, Any]]) -> Path:
    """
    Write a Fortran namelist file

    Parameters
    ----------
    path
        Where to write

    namelists
        Namelist group name to the values in that group

    Returns
    -------
    :
        `path`
    """
    f90nml = _import_f90nml("write_namelist")

    nml = f90nml.Namelist({group: dict(values) for group, values in namelists.items()})
    nml.float_format = ".17g"
    nml.write(str(path), force=True)

    return path


def read_namelist(path: Path) -> dict[str, dict[str, Any]]:
    """
    Read a Fortran namelist file

    Parameters
    ----------
    path
        File to read

    Returns
    -------
    :
        Namelist group name to the values in that group, all names lowercase
    """
    f90nml = _import_f90nml("read_namelist")

    return {
        group.lower(): {k.lower(): v for k, v in values.items()}
        for group, values in f90nml.read(str(path)).items()
    }


class _BinaryStream:
    """Fortran unformatted sequential records, read one at a time"""

    def __init__(self, path: Path):
        self.data = memoryview(Path(path).read_bytes())
        self.pos = 0

    def read_record(self, dtype: str) -> np.ndarray[Any, Any]:
        size = self.data[self.pos : self.pos + 4].cast("i")[0]
        start = self.pos + 4
        record = self.data[start : start + size]
        end_size = self.data[start + size : start + size + 4].cast("i")[0]
        if end_size != size:
            msg = f"Corrupt record: {size=}, {end_size=}"
            raise ValueError(msg)

        self.pos = start + size + 4

        return np.frombuffer(record, dtype=dtype)

    def read_str(self) -> str:
        return str(self.read_record("S1").tobytes().decode().strip())


def read_binout(path: Path) -> pd.DataFrame:
    """
    Read a MAGICC binary output file (`DAT_*.BINOUT`, version 2 format)

    Parameters
    ----------
    path
        File to read

    Returns
    -------
    :
        Timeseries with `variable`, `region` and `unit` index levels,
        using MAGICC's own names, and integer years as columns
    """
    stream = _BinaryStream(path)

    magic = stream.read_str()
    if magic != "magicc":
        msg = f"{path} is not a version 2 binary output file"
        raise ValueError(msg)

    version = int(stream.read_record("<i2")[0])
    if version != BINOUT_VERSION:
        msg = f"Only version 2 binary output is supported, {path} is {version}"
        raise NotImplementedError(msg)

    n_columns = int(stream.read_record("<u4")[0])
    first_year = int(stream.read_record("<u4")[0])
    last_year = int(stream.read_record("<u4")[0])
    annual_steps = int(stream.read_record("<u4")[0])
    if annual_steps != ANNUAL_STEPS:
        msg = f"Only annual binary output is supported, {path} has {annual_steps=}"
        raise NotImplementedError(msg)

    index = []
    values = []
    for _ in range(n_columns):
        index.append((stream.read_str(), stream.read_str(), stream.read_str()))
        values.append(stream.read_record("<f8"))

    return pd.DataFrame(
        np.vstack(values),
        index=pd.MultiIndex.from_tuples(index, names=["variable", "region", "unit"]),
        columns=range(first_year, last_year + 1),
    )
