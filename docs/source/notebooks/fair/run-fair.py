# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Minimal OpenSCM-Runner example with FaIR

# %%
import openscm_runner

# %%
openscm_runner.__version__

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scmdata import ScmRun

from openscm_runner.adapters import FAIR
from openscm_runner.run import run
from openscm_runner.utils import calculate_quantiles

# %%
fair = FAIR()

# %%
fair.get_version()

# %%
input_scenarios = ScmRun(
    str(
        Path("..")
        / ".."
        / ".."
        / ".."
        / "tests"
        / "test-data"
        / "rcmip_scen_ssp_world_emissions.csv"
    ),
    lowercase_cols=True,
)

input_scenarios.head(30)

# %%
res_run = run(
    climate_models_cfgs={
        "FAIR": [
            {},  # passing an empty list of an empty dict will run with defaults
            {"q": np.array([0.3, 0.45]), "r0": 30.0, "lambda_global": 0.9},
            {"q": np.array([0.35, 0.4]), "r0": 25.0, "lambda_global": 1.1},
        ],
    },
    scenarios=input_scenarios,
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
# Note in the plots below that 'model' is the IAM that produced the scenario. In all cases, the climate model is FaIR.

# %%
res_run.get_unique_meta("climate_model", no_duplicates=True)

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
res_run.filter(variable="Surface Air Temperature Change").plumeplot(
    ax=ax, **plot_kwargs
)
ax.axhline(1.1)
ax.axvline(2018)

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
res_run.filter(variable="Atmospheric Concentrations|CO2").plumeplot(
    ax=ax, **plot_kwargs
)

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
ax, legend_items = res_run.filter(
    variable="Effective Radiative Forcing*", scenario="ssp245"
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
res_run.filter(
    variable="Surface Air Temperature Change", year=2100, scenario=["ssp126"]
).values.max()

# %%
res_run.filter(
    variable="Surface Air Temperature Change", year=2100, scenario=["ssp126"]
).values.min()

# %%
res_run.filter(
    variable="Surface Air Temperature Change", year=2100, scenario=["ssp370"]
).values.max()

# %%
res_run.filter(
    variable="Surface Air Temperature Change", year=2100, scenario=["ssp370"]
).values.min()

# %%
quantiles = calculate_quantiles(res_run, [0.05, 0.17, 0.5, 0.83, 0.95])

# %%
quantiles.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp126"],
    quantile=0.05,
).values[0][0]

# %%
quantiles.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp126"],
    quantile=0.95,
).values[0][0]

# %%
quantiles.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp370"],
    quantile=0.05,
).values[0][0]

# %%
quantiles.filter(
    variable="Surface Air Temperature Change",
    year=2100,
    scenario=["ssp370"],
    quantile=0.95,
).values[0][0]
