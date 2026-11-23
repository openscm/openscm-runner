"""
Add locked targets to `pyproject.toml`

This adds a "locked" target
plus a "<option>-locked" target
for each optional dependency group.

Only works with uv.
"""

from __future__ import annotations

import copy
import shutil
import subprocess
from pathlib import Path

import tomli_w

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def parse_uv_export_output(raw: str) -> list[str]:
    """
    Parse `uv export` output

    Parameters
    ----------
    raw
        Raw output string

    Returns
    -------
    :
        Parsed dependencies
    """
    raw_split = raw.splitlines()
    deps = [v for v in raw_split if not v.strip().startswith("#")]

    return deps


def main():
    """
    Update the `pyproject.toml` file with locked targets
    """
    project_root = Path(__file__).parents[1]
    pyproject_file = project_root / "pyproject.toml"
    pyproject_file_out = pyproject_file
    # Handy for testing
    # pyproject_file_out = project_root / "pyproject.toml.injected"

    with open(pyproject_file, "rb") as fh:
        pyproject_in = tomllib.load(fh)

    pyproject_out = copy.deepcopy(pyproject_in)
    for optional_dep, uv_export_flags in (
        ("locked", ()),
        *(
            (f"{extra}-locked", ("--extra", extra))
            for extra in pyproject_in["project"]["optional-dependencies"]
        ),
    ):
        uv_export_res = subprocess.run(  # noqa: S603
            (
                shutil.which("uv"),
                "export",
                "--no-hashes",
                "--no-annotate",
                "--no-emit-project",
                "--no-dev",
                *uv_export_flags,
            ),
            check=True,
            stdout=subprocess.PIPE,
        )

        parsed_deps = parse_uv_export_output(uv_export_res.stdout.decode())

        pyproject_out["project"]["optional-dependencies"][optional_dep] = parsed_deps

    with open(pyproject_file_out, "wb") as f:
        tomli_w.dump(pyproject_out, f)


if __name__ == "__main__":
    main()
