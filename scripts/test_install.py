"""
Test that all of our modules can be imported

Thanks https://stackoverflow.com/a/25562415/10473080
"""
import importlib
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
# make sure csv was included
openscm_runner.adapters.fair_adapter.fair_adapter._get_natural_emissions_and_forcing(
    1750, 4
)
print(openscm_runner.__version__)
