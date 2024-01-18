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
# # Minimal OpenSCM-Runner example with CICERO-SCM

# %%
# NBVAL_IGNORE_OUTPUT
import logging
import os.path

import matplotlib.pyplot as plt
import scmdata

import openscm_runner
from openscm_runner.adapters import CICEROSCM
from openscm_runner.run import run

# %%
STDERR_INFO_HANDLER = logging.StreamHandler()
FORMATTER = logging.Formatter(
    "%(asctime)s %(name)s %(threadName)s - %(levelname)s:  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
STDERR_INFO_HANDLER.setFormatter(FORMATTER)

OPENSCM_RUNNER_LOGGER = logging.getLogger("openscm_runner")
OPENSCM_RUNNER_LOGGER.setLevel(logging.INFO)
OPENSCM_RUNNER_LOGGER.addHandler(STDERR_INFO_HANDLER)

# %%
# NBVAL_IGNORE_OUTPUT
openscm_runner.__version__

# %%
cicero_scm = CICEROSCM()
cicero_scm.get_version()

# %%
# NBVAL_IGNORE_OUTPUT
input_emissions = scmdata.ScmRun(
    os.path.join("..", "tests", "test-data", "rcmip_scen_ssp_world_emissions.csv"),
    lowercase_cols=True,
)

input_emissions.head(30)

# %%
# NBVAL_IGNORE_OUTPUT
res = run(
    climate_models_cfgs={
        "CICEROSCM": [
            # @marit, how do you get the model to stop in 2100?
            {
                "scenario_end": input_emissions["year"].max(),
                "model_end": input_emissions["year"].max(),
                **cfg,
            }
            for cfg in [
                #             {},  # passing an empty list of an empty dict will do <@marit to write>
                {
                    "Index": 30040,
                    "lambda": 0.540,
                    "akapa": 0.341,
                    "cpi": 0.556,
                    "W": 1.897,
                    "rlamdo": 16.618,
                    "beto": 3.225,
                    "mixed": 107.277,
                    "dirso2_forc": -0.457,
                    "indso2_forc": -0.514,
                    "bc_forc": 0.200,
                    "oc_forc": -0.103,
                },
                {
                    "Index": 1,
                    "lambda": 0.3925,
                    "akapa": 0.2421,
                    "cpi": 0.3745,
                    "W": 0.8172,
                    "rlamdo": 16.4599,
                    "beto": 4.4369,
                    "mixed": 35.4192,
                    "dirso2_forc": -0.3428,
                    "indso2_forc": -0.3856,
                    "bc_forc": 0.1507,
                    "oc_forc": -0.0776,
                },
                #             {"q": np.array([0.3, 0.45]), "r0": 30.0, "lambda_global": 0.9},
                #             {"q": np.array([0.35, 0.4]), "r0": 25.0, "lambda_global": 1.1},
            ]
        ],
    },
    scenarios=input_emissions,
    output_variables=(
        "Surface Air Temperature Change",
        "Atmospheric Concentrations|CO2",
        "Effective Radiative Forcing",
        "Effective Radiative Forcing|CO2",
        "Effective Radiative Forcing|CH4",
        "Effective Radiative Forcing|N2O",
        "Effective Radiative Forcing|Greenhouse Gases",
        "Effective Radiative Forcing|Aerosols",
        "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        "Effective Radiative Forcing|Aerosols|Direct Effect",
        "Effective Radiative Forcing|Aerosols|Indirect Effect",
    ),
    # not yet implemented
    #     out_config={"CICEROSCM": ("lambda",)}
).filter(
    year=range(1, input_emissions["year"].max() + 1)
)  # TODO: remove filter once we know how to stop the model

# %%
# NBVAL_IGNORE_OUTPUT
res.head()

# %%
# NBVAL_IGNORE_OUTPUT
res.tail()

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
# NBVAL_IGNORE_OUTPUT
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
res.filter(variable="Surface Air Temperature Change").plumeplot(ax=ax, **plot_kwargs)
ax.axhline(1.1)
ax.axvline(2018)

# %%
# NBVAL_IGNORE_OUTPUT
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
res.filter(variable="Atmospheric Concentrations|CO2").plumeplot(ax=ax, **plot_kwargs)

# %%
# NBVAL_IGNORE_OUTPUT
ax = plt.figure(figsize=(12, 7)).add_subplot(111)
ax, legend_items = res.filter(
    variable="Effective Radiative Forcing*",
    scenario="ssp245",
    year=range(2000, 2030),
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
ax.legend(handles=legend_items, ncol=2, loc="center right")
