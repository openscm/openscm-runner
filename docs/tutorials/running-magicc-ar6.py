# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Running MAGICC AR6
#
# Here we show how run MAGICC in its AR6 probabilistic configuration
# (MAGICC v7.5.3 with the 600-member AR6 probabilistic distribution)
# for four experiments that cover a range of adapters:
#
# - 1pctCO2 and abrupt-4xCO2, branching off CMIP7's pre-industrial (piControl) state
# - flat10 (constant CO2 emissions of 10 GtC/yr), also from CMIP7's pre-industrial
# - two AR6 scenarios
#
# Every experiment follows the same pattern:
#
# 1. make the inputs (a tuple of dataframes, one per experiment)
# 1. make an adapter for the model
# 1. call the experiment's `run_*` function,
#    which checks the inputs, runs each adapter and collects the results
#
# The inputs come from the data we use in our tests
# (`tests/test-data` in the repository).

# %% [markdown]
# ## Imports

# %%
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pandas_openscm

from openscm_runner import (
    OutputSpecs,
    run_ar6_scenarios,
    run_co2_concentration_driven_from_cmip7_pre_industrial,
    run_co2_emission_driven_from_cmip7_pre_industrial,
)
from openscm_runner.adapters.magicc_ar6 import (
    MAGICCAR6AdapterAR6Scenario,
    MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterConfiguration,
)

# %% [markdown]
# ## Setup

# %%
# Adds the `.openscm` accessor to dataframes, which we use for plotting
pandas_openscm.register_pandas_accessors()

# %% [markdown]
# ## Getting MAGICC
#
# MAGICC and the AR6 probabilistic distribution don't ship with openscm-runner,
# so we have to tell the adapters where they are.
# The configuration below gets them from environment variables.
# See the docstring of `MAGICCAR6AdapterConfiguration`
# for the full set of options and details.
#
# The same configuration can be used for every MAGICC AR6 adapter.
# We run several copies of MAGICC at once to speed things up (`n_workers`).

# %% editable=true slideshow={"slide_type": ""}
# If we're building these docs on Read the Docs (or in CI),
# other than for a release, we only run 10 of the 600 ensemble members
# to keep compute time low.
# You will likely want to skip this step when running yourself.
n_members = None
if (
    os.environ.get("READTHEDOCS", "False") == "True"
    # Release builds are "tag" builds
    and os.environ.get("READTHEDOCS_VERSION_TYPE") != "tag"
):
    n_members = 10
    print(
        f"WARNING: only running {n_members} of the AR6 distribution's "
        "600 ensemble members to keep compute time low, "
        "so the results shown are just illustrative"
    )

# %% editable=true slideshow={"slide_type": ""}
configuration = MAGICCAR6AdapterConfiguration.from_environment(
    n_workers=os.cpu_count() or 1,
    testing_only_n_members=n_members,
)

# %% [markdown] editable=true slideshow={"slide_type": ""}
# ## Helpers
#
# The test data lives in the repository.

# %% editable=true slideshow={"slide_type": ""}
REPO_ROOT = next(
    p for p in (Path.cwd(), *Path.cwd().parents) if (p / "pyproject.toml").exists()
)
TEST_DATA = REPO_ROOT / "tests" / "test-data"


# %% [markdown] editable=true slideshow={"slide_type": ""}
# ## 1pctCO2 and abrupt-4xCO2
#
# These are CO2-concentration-driven experiments:
# the only input is CO<sub>2</sub> concentrations,
# everything else stays at its piControl value.
# The experiments start (i.e. branch off piControl) in 1850.

# %% editable=true slideshow={"slide_type": ""}
# Could come from lots of places.
# We simply hard-code here.
pi_control_co2 = 284.29727
pi_control_co2


# %% editable=true slideshow={"slide_type": ""}
def make_co2_concentrations(experiment, values, years):
    """Make the input for one CO2-concentration-driven experiment"""
    return pd.DataFrame(
        [values],
        index=pd.MultiIndex.from_tuples(
            [(experiment, "Atmospheric Concentrations|CO2", "World", "ppm")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=years,
    )


years = np.arange(1850, 2000)
one_pct_co2 = make_co2_concentrations(
    "1pctCO2", pi_control_co2 * 1.01 ** (years - years[0]), years
)

abrupt_4xco2 = make_co2_concentrations(
    "abrupt-4xCO2", np.full(2300 - 1850 + 1, 4 * pi_control_co2), np.arange(1850, 2301)
)
one_pct_co2

# %% [markdown] editable=true slideshow={"slide_type": ""}
# We run both experiments in one call.
# The results contain one result per adapter
# (here we only have one adapter),
# each with one output per input, in the same order as the inputs.
# `raise_if_any_failed` raises if anything went wrong
# (either an adapter or any of its ensemble members failed).

# %% editable=true slideshow={"slide_type": ""}
co2_output_specs = OutputSpecs(
    output_variables=(
        "Atmospheric Concentrations|CO2",
        "Effective Radiative Forcing|CO2",
        "Surface Air Temperature Change",
    )
)

results = run_co2_concentration_driven_from_cmip7_pre_industrial(
    co2_concentrations=(one_pct_co2, abrupt_4xco2),
    adapters=(
        MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial(
            configuration=configuration
        ),
    ),
    output_specs=co2_output_specs,
)
results.raise_if_any_failed()
one_pct_co2_res, abrupt_4xco2_res = (output.as_df() for output in results[0].outputs)
one_pct_co2_res

# %% editable=true slideshow={"slide_type": ""}
co2_conc_res = pd.concat([one_pct_co2_res, abrupt_4xco2_res])
for variable in co2_conc_res.index.get_level_values("variable").unique():
    co2_conc_res.loc[
        co2_conc_res.index.get_level_values("variable") == variable
    ].openscm.plot_plume_after_calculating_quantiles(quantile_over="ensemble_member")
    plt.show()

# %% [markdown] editable=true slideshow={"slide_type": ""}
# ## flat10
#
# flat10 is CO2-emission-driven:
# here we do constant fossil CO2 emissions of 10 GtC/yr and 5 GtC/yr from 1850,
# with the carbon cycle calculating the CO2 concentrations.

# %%
years = np.arange(1850, 2300 + 1)
flat10 = pd.DataFrame(
    [np.full(years.size, 10.0)],
    index=pd.MultiIndex.from_tuples(
        [("esm-flat10", "Emissions|CO2|Fossil", "World", "GtC/yr")],
        names=["scenario", "variable", "region", "unit"],
    ),
    columns=years,
)


results = run_co2_emission_driven_from_cmip7_pre_industrial(
    co2_emissions=(
        flat10,
        flat10.rename({"esm-flat10": "esm-flat5"}, level="scenario") / 2.0,
    ),
    adapters=(
        MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial(
            configuration=configuration
        ),
    ),
    output_specs=co2_output_specs,
)
results.raise_if_any_failed()
flat10_res = pd.concat([output.as_df() for output in results[0].outputs])
flat10_res

# %%
for variable in flat10_res.index.get_level_values("variable").unique():
    flat10_res.loc[
        flat10_res.index.get_level_values("variable") == variable
    ].openscm.plot_plume_after_calculating_quantiles(quantile_over="ensemble_member")
    plt.show()

# %% [markdown]
# ## AR6 scenarios
#
# AR6 scenarios are emissions scenarios from 2015,
# with the 52 species AR6 used.
# The adapter adds the history (from 1750), as AR6 did.
# Our test data has two scenarios:
# AIM/CGE 2.2 EN_NPi2020_900f
# and GCAM 5.3 NGFS2_Current Policies
# (AR6's illustrative "current policies" pathway).


# %%
def load_ar6_scenario(filename):
    """Load one of the AR6 scenario test data files"""
    out = pd.read_csv(TEST_DATA / "ar6-scenarios" / filename)
    out = out.set_index(["model", "scenario", "region", "variable", "unit"])
    out.columns = out.columns.astype(int)

    return out


ar6_scenarios = tuple(
    load_ar6_scenario(filename)
    for filename in (
        "ar6-aim-cge-2-2-en-npi2020-900f.csv",
        "ar6-gcam-5-3-ngfs2-current-policies.csv",
    )
)
ar6_scenarios[0]

# %% [markdown]
# As before, we run both scenarios in one call
# and get one output per scenario, in the same order.

# %%
results = run_ar6_scenarios(
    ar6_scenarios=ar6_scenarios,
    adapters=(MAGICCAR6AdapterAR6Scenario(configuration=configuration),),
    output_specs=OutputSpecs(
        output_variables=(
            "Effective Radiative Forcing",
            "Surface Air Temperature Change",
        )
    ),
)
results.raise_if_any_failed()
ar6_res = pd.concat([output.as_df() for output in results[0].outputs])

# %% [markdown]
# The outputs are MAGICC's own:
# relative to its pre-industrial reference (1750).

# %%
for variable in ar6_res.index.get_level_values("variable").unique():
    ar6_res.loc[
        ar6_res.index.get_level_values("variable") == variable
    ].openscm.plot_plume_after_calculating_quantiles(quantile_over="ensemble_member")
    plt.show()
