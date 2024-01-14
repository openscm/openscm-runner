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
# # FaIR: Specifying factors for GMST/GSAT conversion and amount of total Earth energy in the ocean

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scmdata import ScmRun

from openscm_runner.adapters import FAIR
from openscm_runner.run import run

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

# %%
fair_results = run(
    climate_models_cfgs={
        "FAIR": [
            {},  # passing an empty list of an empty dict will run with defaults
            {"ohu_factor": 0.95, "gmst_factor": np.linspace(0.90, 1.00, 351)},
        ],
    },
    scenarios=input_scenarios,
    output_variables=(
        "Surface Air Ocean Blended Temperature Change",
        "Heat Content|Ocean",
        "Heat Uptake|Ocean",
    ),
)

# %% [markdown]
# Note in the plots below that 'model' is the IAM that produced the scenario. In all cases, the climate model is FaIR.

# %%
fair_results.get_unique_meta("climate_model", no_duplicates=True)

# %% [markdown]
# In the below we plot two runs per scenario. The first is with default OHU and GMST factors (0.92 and 1/1.04) and the second is with the specified factors (0.95 for OHU and a time-varying one for GMST).

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
fair_results.filter(variable="Surface Air Ocean Blended Temperature Change").lineplot(
    hue="scenario",
    style="model",
    ax=ax,
    time_axis="year",
    units="run_id",
    estimator=None,
)

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
fair_results.filter(variable="Heat Uptake|Ocean").lineplot(
    hue="scenario",
    style="model",
    ax=ax,
    time_axis="year",
    units="run_id",
    estimator=None,
)

# %%
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
fair_results.filter(variable="Heat Content|Ocean").lineplot(
    hue="scenario",
    style="model",
    ax=ax,
    time_axis="year",
    units="run_id",
    estimator=None,
)
