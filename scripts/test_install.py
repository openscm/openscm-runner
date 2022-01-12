"""
Test that all of our modules can be imported

Thanks https://stackoverflow.com/a/25562415/10473080
"""
import importlib
import os.path
import pkgutil

import openscm_runner
import openscm_runner.adapters.fair_adapter.fair_adapter


def import_submodules(package_name):
    package = importlib.import_module(package_name)

    for _, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + "." + name
        print(full_name)
        importlib.import_module(full_name)
        if is_pkg:
            import_submodules(full_name)


import_submodules("openscm_runner")

# make sure csvs etc. are included
openscm_runner_root = os.path.dirname(openscm_runner.__file__)
assert os.path.isfile(
    os.path.join(
        openscm_runner_root, "adapters/fair_adapter/natural-emissions-and-forcing.csv"
    )
)
assert os.path.isfile(
    os.path.join(
        openscm_runner_root,
        "adapters/ciceroscm_adapter/utils_templates/gases_v1RCMIP.txt",
    )
)
assert os.path.isfile(
    os.path.join(
        openscm_runner_root,
        "adapters/ciceroscm_adapter/utils_templates/run_dir/scm_vCH4fb_bfx",
    )
)
assert os.path.isfile(
    os.path.join(
        openscm_runner_root,
        "adapters/ciceroscm_adapter/utils_templates/run_dir/input_RF/RFSUN/solar_IPCC.txt",
    )
)

print(openscm_runner.__version__)
