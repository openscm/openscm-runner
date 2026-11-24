"""
Pieces shared by the MAGICC AR6 adapters
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import Executor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from openscm_runner.output import EnsembleMemberResult, OpenSCMRunnerOutput
from openscm_runner.verification import TIMESERIES_LEVELS

from .download import get_magicc_ar6_adapter_pieces
from .ensemble import load_ar6_ensemble
from .io import format_tabular_file
from .naming import CONCENTRATION_UNITS, from_magicc_output
from .running import (
    EnsembleMember,
    MAGICCExperiment,
    MAGICCInstallation,
    MAGICCMemberResult,
    run_magicc,
)

MAGICC_VERSION = "v7.5.3"
"""
MAGICC version the adapters use

This is the version AR6 used (with the AR6 probabilistic distribution).
"""

END_YEAR_BUFFER = 3
"""
Years MAGICC is run past the end of the input

MAGICC v7.5.3 has a last year bug
(it effectively halves emissions in the last year of a run).
So we run it a few years longer (holding the inputs constant)
and cut the output at the input's last year.
"""

FILE_HEADER = "Written by openscm-runner"
"""Header of every input file we write"""

MAGICC_AR6_V753_ROOT_DIR_ENV_VAR = "MAGICC_AR6_V753_ROOT_DIR"
"""Environment variable giving the root of a MAGICC v7.5.3 installation"""

MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR = "MAGICC_AR6_PROBABILISTIC_DISTRIBUTION"
"""Environment variable giving the path to the AR6 probabilistic distribution"""

MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR = "MAGICC_AR6_DOWNLOAD_TOKEN"  # noqa: S105
"""Environment variable giving a magicc.org download token"""


class MAGICCAR6NotFoundError(LookupError):
    """Raised when MAGICC and the AR6 probabilistic distribution can't be found"""


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6AdapterConfiguration:
    """
    Configuration for the MAGICC AR6 adapters

    Every MAGICC AR6 adapter takes one of these.
    The same configuration can be used for all of them.
    """

    magicc_root: Path
    """
    Root of a MAGICC v7.5.3 installation (with `bin` and `run` directories)

    We can't ship MAGICC, so you have to tell us where it is.
    """

    ar6_probabilistic_distribution: Path
    """
    Path to the AR6 probabilistic distribution's JSON file

    Its hash is checked, so it has to be exactly the AR6 file.
    """

    magicc_binary: Path | None = None
    """
    Path to the MAGICC binary

    If `None`, we use the binary for this platform
    in the installation's `bin` directory
    (see [get_binary_name][openscm_runner.adapters.magicc_ar6.running.]).
    Whichever binary is used, it must report version [MAGICC_VERSION][(m).].
    """

    n_workers: int = 1
    """
    Number of MAGICC copies to run at once

    With `n_workers=1` (and no `executor`),
    everything runs in the calling process,
    e.g. so you can do your own parallelisation around the adapters.
    If `executor` is given, this is the number of pieces the work is split into,
    so set it to the number of the executor's workers you want to use.
    """

    executor: Executor | None = None
    """
    Executor to run MAGICC with, e.g. a pool you manage yourself

    If `None`,
    we run MAGICC in the calling process if `n_workers` is one,
    otherwise in a pool of `n_workers` processes
    which we make (and shut down) for each call.

    If given, every piece of work is submitted to it
    and we don't shut it down: its lifetime is yours to manage.
    So you can re-use one pool across calls (and adapters),
    rather than starting new processes every time.
    Any [concurrent.futures.Executor][] works,
    e.g. a [concurrent.futures.ProcessPoolExecutor][]
    (we use the `spawn` start method for our own pools,
    which we recommend for yours too),
    a [concurrent.futures.ThreadPoolExecutor][]
    (fine here, because the work is done by MAGICC processes
    although you probably won't see as much of a time-saving because of the GIL)
    or an executor from another library (e.g. dask, loky or mpi4py).
    """

    run_checks: bool = True
    """
    Whether to verify the inputs before running

    The `run_*` functions already do this (it's a duplicate of that layer),
    this is for people who call the adapters directly.
    """

    testing_only_n_members: int | None = None
    """
    Only run the first this many members of the ensemble (for testing only)

    The adapters run the full AR6 ensemble (600 members).
    This is the escape hatch for tests which can't afford that.
    The members that are run keep their IDs,
    so the result is exactly a subset of a full run.

    /// warning | Use with caution
    If you set this, the outputs are not the AR6 distribution:
    don't use them for anything other than testing.
    ///
    """

    @classmethod
    def from_token(
        cls, token: str, *, cache_dir: Path | None = None, **kwargs: Any
    ) -> MAGICCAR6AdapterConfiguration:
        """
        Make a configuration, downloading MAGICC and the distribution from magicc.org

        Parameters
        ----------
        token
            magicc.org download token (get one by logging in at magicc.org)

        cache_dir
            Directory to save the downloads in
            (see [get_magicc_ar6_adapter_pieces][(p).download.])

        **kwargs
            Passed to the class constructor (e.g. `n_workers`)

        Returns
        -------
        :
            Initialised configuration which uses the downloaded MAGICC and distribution
        """
        pieces = get_magicc_ar6_adapter_pieces(token, cache_dir=cache_dir)

        return cls(
            magicc_root=pieces.magicc_root,
            ar6_probabilistic_distribution=pieces.ar6_probabilistic_distribution,
            **kwargs,
        )

    @classmethod
    def from_environment(cls, **kwargs: Any) -> MAGICCAR6AdapterConfiguration:
        """
        Make a configuration from environment variables

        MAGICC v7.5.3 and the AR6 probabilistic distribution come from, in order:

        1. the paths in `MAGICC_AR6_V753_ROOT_DIR`
           and `MAGICC_AR6_PROBABILISTIC_DISTRIBUTION` (both must be set)
        1. magicc.org, downloaded with the token in `MAGICC_AR6_DOWNLOAD_TOKEN`
           (see [from_token][(c).])

        Parameters
        ----------
        **kwargs
            Passed to the constructor (e.g. `n_workers`)

        Returns
        -------
        :
            Configuration

        Raises
        ------
        MAGICCAR6NotFoundError
            Only one path is set, a path doesn't exist,
            or neither the paths nor the token are set
        """
        # Empty values (e.g. copied from `.env.sample`) count as not set
        magicc_root = os.environ.get(MAGICC_AR6_V753_ROOT_DIR_ENV_VAR)
        distribution = os.environ.get(MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR)
        if not (magicc_root or distribution):
            return cls.from_token(get_magicc_download_token(), **kwargs)

        if not (magicc_root and distribution):
            msg = (
                f"Set both {MAGICC_AR6_V753_ROOT_DIR_ENV_VAR} "
                f"and {MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR}, not just one"
            )
            raise MAGICCAR6NotFoundError(msg)

        # Fail now with a clear message, rather than when MAGICC is run
        if not Path(magicc_root).is_dir():
            msg = (
                f"{MAGICC_AR6_V753_ROOT_DIR_ENV_VAR} ({magicc_root}) isn't a directory"
            )
            raise MAGICCAR6NotFoundError(msg)

        if not Path(distribution).is_file():
            msg = (
                f"{MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR} ({distribution}) "
                "isn't a file"
            )
            raise MAGICCAR6NotFoundError(msg)

        return cls(
            magicc_root=Path(magicc_root),
            ar6_probabilistic_distribution=Path(distribution),
            **kwargs,
        )

    @property
    def installation(self) -> MAGICCInstallation:
        """MAGICC installation"""
        return MAGICCInstallation(
            root_dir=Path(self.magicc_root),
            expected_version=MAGICC_VERSION,
            binary_path=self.magicc_binary,
        )

    def load_ensemble(self) -> tuple[EnsembleMember, ...]:
        """
        Load the ensemble to run

        Returns
        -------
        :
            Ensemble members
        """
        ensemble = load_ar6_ensemble(Path(self.ar6_probabilistic_distribution))
        if self.testing_only_n_members is not None:
            ensemble = ensemble[: self.testing_only_n_members]

        return ensemble


def get_magicc_download_token() -> str:
    """
    Get the magicc.org download token from `MAGICC_AR6_DOWNLOAD_TOKEN`

    Returns
    -------
    :
        Token

    Raises
    ------
    MAGICCAR6NotFoundError
        `MAGICC_AR6_DOWNLOAD_TOKEN` isn't set (or is empty)
    """
    token = os.environ.get(MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR)
    if not token:
        msg = (
            f"Set {MAGICC_AR6_DOWNLOAD_TOKEN_ENV_VAR} to a magicc.org download token "
            "(log in at https://magicc.org/download/magicc7 to get one) "
            f"or set {MAGICC_AR6_V753_ROOT_DIR_ENV_VAR} "
            f"and {MAGICC_AR6_PROBABILISTIC_DISTRIBUTION_ENV_VAR}. "
        )
        raise MAGICCAR6NotFoundError(msg)

    return token


@dataclass(frozen=True, kw_only=True)
class MAGICCAR6Experiment:
    """
    One experiment for a MAGICC AR6 adapter to run

    Everything needed to run the experiment and convert its output.
    """

    files: Mapping[str, str]
    """Files to write into the run directory, name to contents"""

    settings: Mapping[str, Any]
    """
    Configuration for the experiment

    Applied on top of each ensemble member's configuration.
    """

    start_year: int
    """First year MAGICC runs"""

    end_year: int
    """Last year MAGICC runs (including any buffer, see [END_YEAR_BUFFER][(m).])"""

    output_first_year: int
    """First year of output to return"""

    output_last_year: int
    """Last year of output to return"""

    output_variables: Mapping[str, str]
    """Output variables to return: our name to MAGICC's name"""

    experiment_levels: Mapping[str, Any]
    """
    Index levels (and their values) that identify the experiment

    These are added to the output.
    """

    def to_magicc_experiment(self) -> MAGICCExperiment:
        """
        Get the experiment to give to MAGICC

        Returns
        -------
        :
            Experiment, as [run_magicc][openscm_runner.adapters.magicc_ar6.running.]
            needs it
        """
        return MAGICCExperiment(
            files=self.files,
            settings=self.settings,
            start_year=self.start_year,
            end_year=self.end_year,
            output_variables=tuple(dict.fromkeys(self.output_variables.values())),
        )


def run_experiments(
    experiments: Sequence[MAGICCAR6Experiment],
    *,
    configuration: MAGICCAR6AdapterConfiguration,
) -> tuple[OpenSCMRunnerOutput, ...]:
    """
    Run MAGICC and convert the results

    Parameters
    ----------
    experiments
        Experiments to run

    configuration
        Configuration to run with

    Returns
    -------
    :
        One output per experiment, in order
    """
    installation = configuration.installation
    installation.check()

    results = run_magicc(
        installation,
        experiments=[e.to_magicc_experiment() for e in experiments],
        ensemble=configuration.load_ensemble(),
        n_workers=configuration.n_workers,
        executor=configuration.executor,
    )

    return tuple(
        OpenSCMRunnerOutput(
            members=tuple(
                _to_member_result(r, experiment=experiment) for r in member_results
            )
        )
        for member_results, experiment in zip(results, experiments, strict=True)
    )


def _to_member_result(
    result: MAGICCMemberResult, *, experiment: MAGICCAR6Experiment
) -> EnsembleMemberResult:
    if result.error is not None:
        return EnsembleMemberResult.from_failure(result.member_id, result.error)

    if result.data is None:  # pragma: no cover
        raise AssertionError

    try:
        data = from_magicc_output(
            result.data,
            output_variables=experiment.output_variables,
            first_year=experiment.output_first_year,
            last_year=experiment.output_last_year,
            experiment_levels=experiment.experiment_levels,
        )
    except Exception as exc:
        return EnsembleMemberResult.from_failure(result.member_id, exc)

    return EnsembleMemberResult.from_success(result.member_id, data)


def get_experiment_levels(inp: pd.DataFrame) -> dict[str, Any]:
    """
    Get the index levels (and values) that identify an experiment

    Parameters
    ----------
    inp
        Input for one experiment

    Returns
    -------
    :
        Every index level other than the timeseries levels, with its (single) value
    """
    return {
        str(name): inp.index.get_level_values(i)[0]
        for i, name in enumerate(inp.index.names)
        if name not in TIMESERIES_LEVELS
    }


def hold_last_value(df: pd.DataFrame, n_years: int) -> pd.DataFrame:
    """
    Extend timeseries by holding their last value constant

    Parameters
    ----------
    df
        Timeseries, integer years as columns

    n_years
        Number of years to extend by

    Returns
    -------
    :
        Extended timeseries
    """
    last = int(df.columns.max())

    return df.reindex(
        columns=[*df.columns, *range(last + 1, last + n_years + 1)], method="ffill"
    )


# TODO: delete this
def undo_magicc_emissions_averaging(emissions: pd.DataFrame) -> pd.DataFrame:
    """
    Get the emissions to give MAGICC so that it uses the emissions you want

    MAGICC v7.5.3 calculates aerosol forcing and optical thickness
    (direct aerosol, BC on snow and, via the optical thicknesses,
    aerosol-cloud forcing) from the average of the emissions
    in year `t` and year `t + 1`.
    The adapters pass emissions on as given (that is how MAGICC has always behaved).
    If you want these calculations to see `emissions` exactly instead,
    pass the output of this function to the adapter.

    This only applies to those calculations.
    MAGICC's gas cycles, tropospheric ozone and nitrate use each year's emissions
    as given, so they see the output of this function
    (including any zig-zags, see below) rather than `emissions`.
    See the note on averaging in
    [openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch][].

    The output `x` satisfies `(x[t] + x[t + 1]) / 2 == emissions[t]`
    for every year in `emissions`.
    To make the last year exact, `x` has one more year than `emissions`.
    Throw away the output for that extra year
    (MAGICC's emissions in it aren't anything you asked for).

    The condition above only fixes `x` up to an alternating term
    (`+c, -c, +c, ...`), which MAGICC's averaging can't see.
    We fix it by keeping the first year unchanged (`x[first] == emissions[first]`).
    That keeps the join with whatever MAGICC has before the first year
    (e.g. history, or the piControl state) the same as without this function.

    Things to be aware of:

    - the output can zig-zag, because exactness needs it.
      E.g. a step change (`0, 0, 0, 1, 1, 1`) becomes `0, 0, 0, 0, 2, 0, 2`,
      which zig-zags for ever after the step.
      Choosing the alternating term differently just moves the zig-zag
      to before the step: no timeseries averages to a step without one.
      Similarly, emissions which are flat and then increase linearly
      become a staircase (`0, 0, 0, 1, 2, 3` becomes `0, 0, 0, 0, 2, 2, 4`).
      If you don't need the emissions in each year exactly,
      MAGICC's default behaviour (half a year of smoothing) may be preferable.
    - the output can be negative where the emissions change quickly

    Parameters
    ----------
    emissions
        Emissions you want MAGICC to use, consecutive integer years as columns

    Returns
    -------
    :
        Emissions to give MAGICC (same index and units as `emissions`),
        with one more year than `emissions`

    Raises
    ------
    ValueError
        The columns aren't consecutive integer years
    """
    years = [int(y) for y in emissions.columns]
    if years != list(range(years[0], years[0] + len(years))):
        msg = f"Columns must be consecutive integer years, received {years}"
        raise ValueError(msg)

    wanted = emissions.to_numpy(dtype=float)
    out = np.empty((wanted.shape[0], wanted.shape[1] + 1))
    out[:, 0] = wanted[:, 0]
    for i in range(1, out.shape[1]):
        out[:, i] = 2 * wanted[:, i - 1] - out[:, i - 1]

    return pd.DataFrame(out, index=emissions.index, columns=[*years, years[-1] + 1])


# TODO: Put these in IO?
SHAPE_SPECIFICATIONS: frozenset[str] = frozenset(
    {
        "THISFILE_DATACOLUMNS",
        "THISFILE_DATAROWS",
        "THISFILE_FIRSTYEAR",
        "THISFILE_LASTYEAR",
        "THISFILE_ANNUALSTEPS",
        "THISFILE_FIRSTDATAROW",
    }
)
"""
`THISFILE_SPECIFICATIONS` which describe a file's shape

`format_tabular_file` writes these, so they aren't copied from the original file.
"""


# TODO: put this in IO?
def format_held_tabular_file(
    values: pd.Series[float],
    *,
    years: Iterable[Any],
    specifications: Mapping[str, Any],
    header: str,
) -> str:
    """
    Format a tabular input file which holds the same values every year

    Parameters
    ----------
    values
        Value in each column of the file (the index is the file's `YEARS` labels)

    years
        Years to write

    specifications
        The original file's `THISFILE_SPECIFICATIONS`
        (the ones which describe its shape are dropped)

    header
        Header of the file

    Returns
    -------
    :
        Contents of the file
    """
    return format_tabular_file(
        pd.DataFrame({int(y): values for y in years}),
        specifications={
            k: v for k, v in specifications.items() if k not in SHAPE_SPECIFICATIONS
        },
        header=header,
        label_rows={"YEARS": [str(v) for v in values.index]},
    )


# TODO: put this in IO?
def format_scen7(emissions: pd.DataFrame) -> str:
    """
    Format a `.SCEN7` file (World-only emissions)

    Parameters
    ----------
    emissions
        Emissions in MAGICC's names and units
        (`variable` and `unit` index levels), integer years as columns

    Returns
    -------
    :
        Contents of the file
    """
    gases = list(emissions.index.get_level_values("variable"))
    units = [
        u.replace(" / ", "_per_").replace(" ", "_")
        for u in emissions.index.get_level_values("unit")
    ]

    return format_tabular_file(
        emissions,
        specifications={
            "THISFILE_UNITS": "MISC",
            "THISFILE_DATTYPE": "SCEN7",
            "THISFILE_REGIONMODE": "WORLD",
        },
        header=FILE_HEADER,
        label_rows={
            "GAS": gases,
            "TODO": ["SET"] * len(gases),
            "UNITS": units,
            "YEARS": ["WORLD"] * len(gases),
        },
    )


# TODO: put this in IO?
def format_conc_in(gas: str, values: pd.Series[float]) -> str:
    """
    Format a global concentration input file (`*_CONC.IN`)

    Parameters
    ----------
    gas
        MAGICC's name for the gas

    values
        Concentrations, integer years as the index

    Returns
    -------
    :
        Contents of the file
    """
    unit = CONCENTRATION_UNITS[gas]

    return format_tabular_file(
        values.to_frame().T,
        specifications={
            "THISFILE_UNITS": unit,
            "THISFILE_DATTYPE": "NOTUSED",
            "THISFILE_REGIONMODE": "FOURBOX",
        },
        header=FILE_HEADER,
        label_rows={
            "VARIABLE": [f"{gas}_CONC"],
            "TODO": ["SET"],
            "UNITS": [unit],
            "YEARS": ["WORLD"],
        },
    )


# TODO: put this in IO?
def format_forcing_in(variable: str, values: pd.Series[float]) -> str:
    """
    Format a global, annual forcing input file (e.g. `*_SOLAR_RF.IN`)

    Parameters
    ----------
    variable
        MAGICC's name for the variable (e.g. `"SOLAR_RF"`)

    values
        Forcing (W/m^2), integer years as the index

    Returns
    -------
    :
        Contents of the file
    """
    return format_tabular_file(
        values.to_frame().T,
        specifications={
            "THISFILE_UNITS": "Wpermsuper2",
            "THISFILE_DATTYPE": "NOTUSED",
            "THISFILE_REGIONMODE": "FOURBOX",
        },
        header=FILE_HEADER,
        label_rows={
            "VARIABLE": [variable],
            "TODO": ["SET"],
            "UNITS": ["Wpermsuper2"],
            "YEARS": ["WORLD"],
        },
    )


# TODO: put this in IO?
def format_hemispheric_monthly_forcing_in(
    variable: str, values: pd.Series[float]
) -> str:
    """
    Format a monthly, hemispheric forcing input file (e.g. `*_VOLCANIC_RF.MON`)

    The same values are written for both hemispheres.

    Parameters
    ----------
    variable
        MAGICC's name for the variable (e.g. `"VOLCANIC_ANNUAL_RF"`)

    values
        Forcing (W/m^2), integer years as the index
        (the annual value is used for every month)

    Returns
    -------
    :
        Contents of the file
    """
    # MAGICC's convention for monthly files: decimal years at the start of each month
    times = [
        round(year + month / 12, 3) for year in values.index for month in range(12)
    ]
    monthly = [v for v in values.to_numpy() for _ in range(12)]

    return format_tabular_file(
        pd.DataFrame([monthly, monthly], columns=times),
        specifications={
            "THISFILE_UNITS": "Wpermsuper2",
            "THISFILE_DATTYPE": "NOTUSED",
            "THISFILE_REGIONMODE": "HEMISPHERIC",
        },
        header=FILE_HEADER,
        label_rows={
            "VARIABLE": [variable, variable],
            "TODO": ["SET", "SET"],
            "UNITS": ["Wpermsuper2", "Wpermsuper2"],
            "YEARS": ["NH", "SH"],
        },
        annualsteps=12,
    )
