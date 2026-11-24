"""
Running the MAGICC executable

This is the layer the adapters are built on.
It knows nothing about experiments:
it takes the files to write, the configuration and the ensemble,
runs MAGICC and reads the output.
"""

from __future__ import annotations

import multiprocessing
import os
import platform
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .io import read_binout, write_namelist

MACOS_GFORTRAN_LIBRARY_PATHS = (
    Path("/opt/homebrew/opt/gfortran/lib/gcc/current"),
    Path("/opt/homebrew/opt/gcc/lib/gcc/current"),
)
"""
Where Homebrew puts gfortran's libraries

The macOS MAGICC binaries are dynamically linked against gfortran.
The v7.5.3 binary was linked against a path for gcc 11 specifically,
so we point `DYLD_LIBRARY_PATH` at whichever of these exists
(same approach as the MAGICC repository).
"""

GENERATED_CFG_FILES = ("MAGCFG_USER.CFG", "MAGCFG_NMLYEARS.CFG")
"""Configuration files we write ourselves (never taken from the installation)"""

OUTPUT_SETTINGS: dict[str, Any] = {
    "out_ascii_binary": "BINARY",
    "out_binary_format": 2,
    "out_parameters": 0,
}
"""Output settings every run gets"""

N_EMISSCEN_SLOTS = 8
"""Number of `file_emisscen*` slots MAGICC has"""

NO_EXTRA_SCENARIO_FILES: dict[str, Any] = {
    f"file_emisscen_{slot}": "NONE" for slot in range(2, N_EMISSCEN_SLOTS + 1)
}
"""Settings which stop MAGICC reading any scenario file other than ours"""


class MAGICCRunError(RuntimeError):
    """Raised when MAGICC fails"""


def get_binary_name() -> str:
    """
    Get the name of the MAGICC binary for this platform

    Uses the layout of the released MAGICC bundles
    (e.g. `bin/magicc-darwin-arm64`, `bin/magicc` on linux).

    Returns
    -------
    :
        Name of the binary within the installation's `bin` directory
    """
    system = platform.system()
    if system == "Darwin":
        if platform.machine() == "arm64":
            return "magicc-darwin-arm64"

        return "magicc-darwin-amd64"

    if system == "Linux":
        return "magicc"

    if system == "Windows":
        return "magicc.exe"

    msg = f"No MAGICC binary is known for {system}"
    raise NotImplementedError(msg)


def get_environment() -> dict[str, str]:
    """Get the environment to run MAGICC in"""
    env = dict(os.environ)
    for path in MACOS_GFORTRAN_LIBRARY_PATHS:
        if path.exists():
            existing = env.get("DYLD_LIBRARY_PATH", "")
            env["DYLD_LIBRARY_PATH"] = ":".join(p for p in (str(path), existing) if p)
            break

    return env


@dataclass(frozen=True)
class MAGICCInstallation:
    """
    A MAGICC installation (a released MAGICC bundle, unpacked)

    It must have the usual layout: a `bin` directory with the binaries
    and a `run` directory with the default configuration and input files.
    """

    root_dir: Path
    """Root of the installation"""

    expected_version: str
    """Version MAGICC must report (e.g. `"v7.5.3"`)"""

    binary_path: Path | None = None
    """
    Path to the binary to run

    If `None`, the binary for this platform in the installation's `bin` directory
    (see [get_binary_name][(m).]).
    """

    @property
    def binary(self) -> Path:
        """
        Absolute path to the binary to run

        Absolute because MAGICC is run from a different (temporary) directory.
        """
        if self.binary_path is not None:
            return Path(self.binary_path).resolve()

        return (Path(self.root_dir) / "bin" / get_binary_name()).resolve()

    @property
    def run_dir(self) -> Path:
        """Installation's `run` directory"""
        return self.root_dir / "run"

    def check(self) -> None:
        """
        Check the installation is usable and the right version

        Raises
        ------
        FileNotFoundError
            The binary or run directory doesn't exist

        MAGICCRunError
            The binary didn't run, or reported the wrong version
        """
        for path in (self.binary, self.run_dir):
            if not path.exists():
                msg = f"{path} doesn't exist (MAGICC installation: {self.root_dir})"
                raise FileNotFoundError(msg)

        res = subprocess.run(  # noqa: S603
            [str(self.binary), "--version"],
            capture_output=True,
            check=False,
            env=get_environment(),
        )
        version = res.stdout.decode("utf-8", errors="replace").strip()
        if res.returncode != 0 or version != self.expected_version:
            msg = (
                f"Expected MAGICC {self.expected_version} at {self.binary}, "
                f"received version {version!r} (exit code {res.returncode}). "
                f"stderr: {res.stderr.decode('utf-8', errors='replace')}"
            )
            raise MAGICCRunError(msg)


@dataclass(frozen=True)
class EnsembleMember:
    """One member of an ensemble"""

    id: str
    """ID of the member (e.g. the AR6 probabilistic distribution's `paraset_id`)"""

    configuration: Mapping[str, Any]
    """
    The member's configuration (keys are MAGICC's settings, lower case)

    The settings of the experiment being run are applied on top of this.
    """


@dataclass(frozen=True, kw_only=True)
class MAGICCExperiment:
    """
    One experiment, i.e. everything needed to run it except the ensemble members

    The experiment's files and settings are the same for every ensemble member.
    """

    files: Mapping[str, str]
    """
    Files to write into the run directory before running, name to contents

    Configuration settings refer to these by name
    (MAGICC looks in the run directory).
    """

    settings: Mapping[str, Any]
    """
    Configuration for the experiment

    Applied on top of each member's configuration.
    """

    start_year: int
    """First year of the run"""

    end_year: int
    """Last year of the run"""

    output_variables: tuple[str, ...]
    """MAGICC's names for the outputs to read (e.g. `"DAT_SURFACE_TEMP"`)"""

    steps_per_year: int = 12
    """Number of time steps per year"""

    @property
    def nml_years(self) -> dict[str, int]:
        """Contents of MAGICC's `NML_YEARS` namelist"""
        return {
            "startyear": self.start_year,
            "endyear": self.end_year,
            "stepsperyear": self.steps_per_year,
        }


@dataclass(frozen=True)
class MAGICCTask:
    """
    Some ensemble members of one experiment, to be run in one worker

    The experiment's files are written once, then each member is run.
    """

    experiment: MAGICCExperiment
    """Experiment to run"""

    members: tuple[EnsembleMember, ...]
    """Ensemble members to run"""


@dataclass(frozen=True)
class MAGICCMemberResult:
    """Result of running one ensemble member of one experiment"""

    member_id: str
    """ID of the ensemble member"""

    data: pd.DataFrame | None = None
    """Raw output (MAGICC's names), `None` if the member failed"""

    error: Exception | None = field(default=None)
    """Error raised for this member, `None` if it succeeded"""


def _populate_run_dir(installation: MAGICCInstallation, run_dir: Path) -> None:
    """
    Symlink the installation's run files into `run_dir`

    Only files (not sub-directories) and not the configuration files we write.
    """
    run_dir.mkdir()
    for path in installation.run_dir.iterdir():
        if path.is_file() and path.name not in GENERATED_CFG_FILES:
            (run_dir / path.name).symlink_to(path.resolve())


def _run_once(
    installation: MAGICCInstallation,
    run_dir: Path,
    out_dir: Path,
    output_variables: Sequence[str],
) -> pd.DataFrame:
    # So a run which doesn't write an output fails loudly
    # instead of the previous member's output being read
    for variable in output_variables:
        (out_dir / f"{variable}.BINOUT").unlink(missing_ok=True)

    res = subprocess.run(  # noqa: S603
        [str(installation.binary)],
        cwd=run_dir,
        capture_output=True,
        check=False,
        env=get_environment(),
    )
    stdout = res.stdout.decode("utf-8", errors="replace")
    stderr = res.stderr.decode("utf-8", errors="replace")
    missing = [v for v in output_variables if not (out_dir / f"{v}.BINOUT").exists()]
    if (
        res.returncode != 0
        or "<FATAL>" in stdout + stderr
        or "<ERROR>" in stdout + stderr
        or missing
    ):
        msg = (
            f"MAGICC failed (exit code {res.returncode}, missing outputs {missing}).\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
        raise MAGICCRunError(msg)

    return pd.concat([read_binout(out_dir / f"{v}.BINOUT") for v in output_variables])


def _run_task(
    installation: MAGICCInstallation, task: MAGICCTask
) -> list[MAGICCMemberResult]:
    """
    Run one task in a fresh temporary directory

    Each member's failure is caught and recorded, so the other members still run.
    """
    experiment = task.experiment
    with tempfile.TemporaryDirectory(prefix="magicc-") as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        out_dir = root / "out"
        # This is just a directory of symlinks plus the experiment's files,
        # so it is cheap compared to running MAGICC even once.
        # Hence we make a fresh one for every task
        # rather than setting up workers up front and re-using them
        # (which also means nothing can leak from one task to the next).
        _populate_run_dir(installation, run_dir)
        out_dir.mkdir()

        for name, contents in experiment.files.items():
            path = run_dir / name
            # Replace the installation's file of the same name, if there is one
            path.unlink(missing_ok=True)
            path.write_text(contents, encoding="latin-1")

        write_namelist(
            run_dir / "MAGCFG_NMLYEARS.CFG", {"nml_years": experiment.nml_years}
        )

        results = []
        for member in task.members:
            user = {
                **member.configuration,
                **experiment.settings,
                **OUTPUT_SETTINGS,
                "out_dynamic_vars": list(experiment.output_variables),
            }
            try:
                write_namelist(run_dir / "MAGCFG_USER.CFG", {"nml_allcfgs": user})
                data = _run_once(
                    installation, run_dir, out_dir, experiment.output_variables
                )
            except Exception as exc:
                results.append(MAGICCMemberResult(member_id=member.id, error=exc))
                continue

            results.append(MAGICCMemberResult(member_id=member.id, data=data))

    return results


def _split_contiguous(items: Sequence[Any], n: int) -> list[list[Any]]:
    """Split `items` into (at most) `n` contiguous chunks of near-equal size"""
    n = max(1, min(n, len(items)))
    size, remainder = divmod(len(items), n)
    chunks = []
    start = 0
    for i in range(n):
        stop = start + size + (1 if i < remainder else 0)
        chunks.append(list(items[start:stop]))
        start = stop

    return chunks


def _run_tasks(
    installation: MAGICCInstallation,
    tasks: Sequence[MAGICCTask],
    *,
    executor: Executor,
) -> list[list[MAGICCMemberResult]]:
    """Run tasks with an executor, returning the results in the same order"""
    futures = [executor.submit(_run_task, installation, task) for task in tasks]

    return [f.result() for f in futures]


def run_magicc(
    installation: MAGICCInstallation,
    *,
    experiments: Sequence[MAGICCExperiment],
    ensemble: Sequence[EnsembleMember],
    n_workers: int = 1,
    executor: Executor | None = None,
) -> list[list[MAGICCMemberResult]]:
    """
    Run every ensemble member for every experiment

    Parameters
    ----------
    installation
        MAGICC to run

    experiments
        Experiments to run

    ensemble
        Ensemble members to run for each experiment

    n_workers
        Number of MAGICC copies to run at once.
        If `executor` is given, the number of pieces to split the work into
        (i.e. the number of the executor's workers to use).

    executor
        Executor to run MAGICC with.
        If `None`, we run MAGICC in this process if `n_workers` is one,
        otherwise in a pool of `n_workers` processes which we make for this call.
        If given, we submit every piece of work to it and don't shut it down
        (its lifetime is yours to manage).

    Returns
    -------
    :
        For each experiment (in order), the result for each member (in order).
        Members that failed have their error recorded rather than raised.
    """
    # Split each experiment's members so all the workers are used,
    # even if there is only one experiment.
    # The chunks are contiguous, so concatenating their results
    # gives the members back in order.
    n_chunks = max(1, n_workers // max(1, len(experiments)))
    tasks_by_experiment = [
        [
            MAGICCTask(experiment=experiment, members=tuple(chunk))
            for chunk in _split_contiguous(ensemble, n_chunks)
        ]
        for experiment in experiments
    ]
    tasks = [task for tasks in tasks_by_experiment for task in tasks]

    if executor is not None:
        task_results = _run_tasks(installation, tasks, executor=executor)
    elif n_workers <= 1 or len(tasks) == 1:
        task_results = [_run_task(installation, task) for task in tasks]
    else:
        with ProcessPoolExecutor(
            max_workers=min(n_workers, len(tasks)),
            mp_context=multiprocessing.get_context("spawn"),
        ) as pool:
            task_results = _run_tasks(installation, tasks, executor=pool)

    # `task_results` is in the same order as `tasks`,
    # so we can regroup by experiment without any extra bookkeeping
    task_results_iter = iter(task_results)

    return [
        [result for _ in experiment_tasks for result in next(task_results_iter)]
        for experiment_tasks in tasks_by_experiment
    ]
