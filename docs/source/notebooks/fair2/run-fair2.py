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
# # Minimal OpenSCM-Runner example with FaIR 2.x
#
# This notebook walks through the modern adapter shape introduced with
# the FaIR 2.x integration. Two things distinguish it from the FaIR 1.6
# example:
#
# 1. The adapter is constructed via
#    :meth:`FAIR2.from_native_distribution`, which reads a calibration
#    directory laid out like FaIR's Zenodo-published calibration
#    bundles (parameter posterior CSV + species_configs + historical
#    emissions + single solar / volcanic / land-use / irrigation
#    forcing files).
# 2. The driving mode is passed via the top-level :class:`RunMode`
#    enum, set at adapter construction time. The adapter declares its
#    supported modes (``EMISSIONS_DRIVEN`` and ``CONCENTRATION_DRIVEN``
#    for ``FAIR2``) and raises ``NotImplementedError`` for anything
#    else.

# %%
import openscm_runner

# %%
openscm_runner.__version__

# %%
from pathlib import Path

import matplotlib.pyplot as plt
from scmdata import ScmRun

import openscm_runner.run
from openscm_runner import RunMode
from openscm_runner.adapters import FAIR2

# %% [markdown]
# ## Locate the calibration directory
#
# In CI we ship a trimmed 2-member fixture under
# ``tests/test-data/fair2-mini-bundle/``. For real use you'd point at
# a downloaded Zenodo bundle (FaIR's published calibrations live at
# the URLs documented in the FaIR README).

# %%
test_data_dir = (
    Path("..") / ".." / ".." / ".." / "tests" / "test-data"
)
fair2_bundle = test_data_dir / "fair2-mini-bundle"
assert fair2_bundle.is_dir(), f"bundle not found at {fair2_bundle}"

# %% [markdown]
# ## Construct an adapter for emissions-driven runs

# %%
fair2 = FAIR2.from_native_distribution(
    fair2_bundle,
    mode=RunMode.EMISSIONS_DRIVEN,
    output_variables=(
        "Surface Air Temperature Change",
        "Effective Radiative Forcing",
    ),
)
fair2.get_version()

# %% [markdown]
# ## Load scenarios
#
# Scenarios use openscm-runner's canonical emissions naming convention.
# Anything in ``openscm_runner.KNOWN_EMISSIONS_VARIABLES`` is accepted;
# the wrapper raises ``ValueError`` on unknown names before any model
# runs. For translation from IAMC, RCMIP or CMIP7 naming, do that
# upstream of the wrapper (see :mod:`gcages`).

# %%
input_scenarios = ScmRun(
    str(test_data_dir / "rcmip_scen_ssp_world_emissions.csv"),
    lowercase_cols=True,
)
input_scenarios.head(10)

# %% [markdown]
# ## Run

# %%
res_run = openscm_runner.run.run(
    [fair2],
    scenarios=input_scenarios.filter(scenario="ssp245"),
)

# %%
res_run.get_unique_meta("climate_model", no_duplicates=True)

# %%
res_run.get_unique_meta("variable")

# %% [markdown]
# ## Plot

# %%
plot_kwargs = dict(
    hue_var="scenario",
    style_var="model",
    style_label="IAM",
    time_axis="year",
)

# %%
ax = plt.figure(figsize=(12, 6)).add_subplot(111)
res_run.filter(variable="Surface Air Temperature Change").lineplot(
    ax=ax, **plot_kwargs
)
plt.tight_layout()
plt.show()

# %% [markdown]
# ## Concentration-driven mode
#
# For CD runs, pass ``mode=RunMode.CONCENTRATION_DRIVEN`` and supply
# ``Atmospheric Concentrations|*`` rows in the scenarios DataFrame.
# When the scenarios DataFrame doesn't carry concentrations, the
# adapter can fall back to a CICERO-format bundle directory via the
# ``fair2_conc_bundle_dir`` cfg key (see the adapter docstring), but
# the scenarios-supplied path is the recommended one.

# %%
fair2_cd = FAIR2.from_native_distribution(
    fair2_bundle,
    mode=RunMode.CONCENTRATION_DRIVEN,
    output_variables=("Surface Air Temperature Change",),
)
fair2_cd.supported_modes
