# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Minimal OpenSCM-Runner example with MAGICC
#
# MAGICC can be downloaded from [magicc.org](https://magicc.org/download/magicc7).

# %%
import os
from pathlib import Path

import matplotlib.pyplot as plt
import scmdata

import openscm_runner
import openscm_runner.adapters
import openscm_runner.run
import openscm_runner.utils

# %%
openscm_runner.__version__

# %% [markdown]
# To run MAGICC, we need to set the following environment variable so OpenSCM-Runner knows where to look for the MAGICC binary.

# %%
os.environ["MAGICC_EXECUTABLE_7"] = str(
    Path("..")
    / ".."
    / ".."
    / ".."
    / "bin"
    / "magicc"
    / "magicc-v7.5.3"
    / "bin"
    / "magicc"
)
# # Some users also need something like this
# os.environ["DYLD_LIBRARY_PATH"] = "/opt/homebrew/opt/gfortran/lib/gcc/current/"

# %%
magicc7 = openscm_runner.adapters.MAGICC7

# %%
magicc7.get_version()

# %%
input_emissions = scmdata.ScmRun(
    str(
        Path("..")
        / ".."
        / ".."
        / ".."
        / "tests"
        / "test-data"
        / "clean_scenarios_full_ssps.csv"
    ),
    lowercase_cols=True,
)

input_emissions.head(30)

# %%
magicc_res = openscm_runner.run.run(
    climate_models_cfgs={
        "MAGICC7": [
            {},  # passing an empty list of an empty dict will run with defaults
            {"core_climatesensitivity": 3.0},
            {"core_climatesensitivity": 3.5},
            {"core_climatesensitivity": 2.5},
        ],
    },
    scenarios=input_emissions,
    output_variables=(
        "Surface Air Temperature Change",
        "Atmospheric Concentrations|CO2",
        "Effective Radiative Forcing",
        "Effective Radiative Forcing|CO2",
        "Effective Radiative Forcing|Aerosols",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        "Effective Radiative Forcing|Aerosols|Direct Effect",
        "Effective Radiative Forcing|Aerosols|Indirect Effect",
    ),
)

# %% [markdown]
# Note in the plots below that 'model' is the IAM that produced the scenario. In all cases, the climate model is MAGICC.

# %%
magicc_res.get_unique_meta("climate_model", no_duplicates=True)

# %%
plot_kwargs = dict(
    quantiles_plumes=[((0.05, 0.95), 0.5), ((0.5,), 1.0)],
    quantile_over="run_id",
    hue_var="scenario",
    style_var="model",
    style_label="IAM",
    time_axis="year",
)

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
magicc_res.filter(variable="Surface Air Temperature Change", region="World").plumeplot(
    ax=ax, **plot_kwargs
)
ax.axhline(1.2)
ax.axvline(2018)

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
magicc_res.filter(variable="Atmospheric Concentrations|CO2", region="World").plumeplot(
    ax=ax, **plot_kwargs
)

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
ax, legend_items = magicc_res.filter(
    variable="Effective Radiative Forcing*", scenario="ssp245", region="World"
).plumeplot(
    quantiles_plumes=[((0.05, 0.95), 0.5), ((0.5,), 1.0)],
    quantile_over="run_id",
    hue_var="variable",
    hue_label="Variable",
    style_var="scenario",
    style_label="Scenario",
    ax=ax,
    time_axis="year",
)
ax.legend(handles=legend_items, ncol=2, loc="upper left")

# %%
magicc_res.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp126"],
    region="World",
).values.max()

# %%
magicc_res.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp126"],
    region="World",
).values.min()

# %%
magicc_res.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp370"],
    region="World",
).values.max()

# %%
magicc_res.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp370"],
    region="World",
).values.min()

# %%
quantiles = openscm_runner.utils.calculate_quantiles(
    magicc_res, [0.05, 0.17, 0.5, 0.83, 0.95]
)

# %%
quantiles.filter(
    variable="Surface Air Temperature Change",
    region="World",
    year=2100,
    scenario=["ssp126"],
    quantile=0.05,
).values[0][0]

# %%
quantiles.filter(
    variable="Surface Air Temperature Change",
    region="World",
    year=2100,
    scenario=["ssp126"],
    quantile=0.95,
).values[0][0]

# %%
quantiles.filter(
    variable="Surface Air Temperature Change",
    region="World",
    year=2100,
    scenario=["ssp370"],
    quantile=0.05,
).values[0][0]

# %% [markdown]
# quantiles.filter(
#     variable="Surface Air Temperature Change",
#     region="World",
#     year=2100,
#     scenario=["ssp370"],
#     quantile=0.95,
# ).values[0][0]
