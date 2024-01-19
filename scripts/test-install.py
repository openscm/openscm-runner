"""
Test that all of our modules can be imported

Also test that associated constants are set correctly

Thanks https://stackoverflow.com/a/25562415/10473080
"""
import importlib
import pkgutil
from pathlib import Path

import openscm_runner


def import_submodules(package_name: str) -> None:
    """
    Test import of submodules
    """
    package = importlib.import_module(package_name)

    for _, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + "." + name
        importlib.import_module(full_name)
        if is_pkg:
            import_submodules(full_name)


import_submodules("openscm_runner")

# make sure csvs etc. are included
openscm_runner_root = Path(openscm_runner.__file__).parent

expect_included_files = [
    "adapters/fair_adapter/natural-emissions-and-forcing.csv",
    "adapters/ciceroscm_adapter/utils_templates/gases_v1RCMIP.txt",
    "adapters/ciceroscm_adapter/utils_templates/run_dir/scm_vCH4fb_bfx",
    "adapters/ciceroscm_adapter/utils_templates/run_dir/input_RF/RFSUN/solar_IPCC.txt",
]
for file in expect_included_files:
    assert (
        openscm_runner_root / file
    ).exists(), f"{file} not packaged (root: {openscm_runner_root})"

print(openscm_runner.__version__)
