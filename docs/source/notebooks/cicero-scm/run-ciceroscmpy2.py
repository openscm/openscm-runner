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
# # Minimal OpenSCM-Runner example with CICERO-SCM v2.x
#
# This notebook walks through the modern CICEROSCMPY2 adapter, which
# wraps CICERO-SCM 2.x's :class:`ciceroscm.parallel.DistributionRun`
# ensemble API.
#
# Construction is via :meth:`CICEROSCMPY2.from_native_distribution`,
# which reads a calibration directory containing 8 canonical files
# plus a parameter posterior JSON:
#
# * ``gases_vupdate_2024_WMO_added_new.txt`` (gaspam)
# * ``historical_em_gases_vupdate_2024_WMO_added_new.txt``
# * ``historical_conc_gases_vupdate_2024_WMO_added_new.txt``
# * ``natemis_CH4_ode_method_from_March2026_vupdate_2024_WMO_added_new.txt``
# * ``natemis_N2O_ode_method_from_March2026_vupdate_2024_WMO_added_new.txt``
# * ``solar_RCMIP_historical_RCMIP3.txt``
# * ``VOLC_RCMIP_historical_RCMIP3.txt``
# * ``LUCalbedo_RCMIP_historical_RCMIP3.txt``
# * a parameter posterior JSON matching one of
#   ``calibrated_*ensemble*.json``, ``*distribution*.json``, or
#   ``draw_samples_*.json``
#
# The canonical published calibration is Sandstad v1.0.0
# (`10.5281/zenodo.20506399`), which follows this layout exactly.
# Download, unpack, and point ``from_native_distribution`` at the
# unpacked directory.
#
# Every required path is also cfg-overridable. Partial overrides skip
# the canonical-file existence check for the overridden key, so the
# caller can mix-and-match (point ``cal_dir`` at a mostly-canonical
# bundle and substitute one file from elsewhere).

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
from openscm_runner.adapters import CICEROSCMPY2

# %% [markdown]
# ## Locate the calibration directory
#
# In CI we ship a trimmed 2-member fixture under
# ``tests/test-data/ciceroscm-mini-bundle/``. The fixture was
# generated with ssp245-prefixed filenames (rather than the canonical
# ``historical_*`` names), so we use cfg overrides to point at the
# actual files. For a freshly-published Zenodo calibration the
# filenames will already match the canonical defaults and no
# overrides are needed.

# %%
test_data_dir = (
    Path("..") / ".." / ".." / ".." / "tests" / "test-data"
)
cicero_bundle = test_data_dir / "ciceroscm-mini-bundle"
assert cicero_bundle.is_dir(), f"bundle not found at {cicero_bundle}"

# %% [markdown]
# ## Construct an adapter for emissions-driven runs

# %%
cicero = CICEROSCMPY2.from_native_distribution(
    cicero_bundle,
    mode=RunMode.EMISSIONS_DRIVEN,
    output_variables=(
        "Surface Air Temperature Change",
        "Effective Radiative Forcing",
    ),
    # Mini-bundle was assembled with ssp245-prefixed filenames; supply
    # them via cfg overrides. A canonical-layout calibration directory
    # would not need this block.
    historical_em_file=str(
        cicero_bundle / "ssp245_em_gases_vupdate_2024_WMO_added_new.txt"
    ),
    historical_conc_file=str(
        cicero_bundle / "ssp245_conc_gases_vupdate_2024_WMO_added_new.txt"
    ),
    rf_solar_file=str(cicero_bundle / "solar_RCMIP_ssp245_RCMIP3.txt"),
    rf_volc_file=str(cicero_bundle / "VOLC_RCMIP_ssp245_RCMIP3.txt"),
    rf_luc_file=str(cicero_bundle / "LUCalbedo_RCMIP_ssp245_RCMIP3.txt"),
)
cicero.get_version()

# %% [markdown]
# ## Load scenarios

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
    [cicero],
    scenarios=input_scenarios.filter(scenario="ssp245"),
)

# %%
res_run.get_unique_meta("climate_model", no_duplicates=True)

# %% [markdown]
# ## Plot

# %%
ax = plt.figure(figsize=(12, 6)).add_subplot(111)
res_run.filter(variable="Surface Air Temperature Change").lineplot(
    ax=ax, time_axis="year", hue="scenario", style="model",
)
ax.set_title("CICERO-SCM v2.x - ssp245 Surface Air Temperature Change")
plt.tight_layout()
plt.show()

# %% [markdown]
# ## Concentration-driven mode
#
# For CD runs, pass ``mode=RunMode.CONCENTRATION_DRIVEN`` and supply
# ``Atmospheric Concentrations|*`` rows in the scenarios DataFrame.
# When the scenarios DataFrame doesn't carry concentrations, the
# adapter uses the calibration's ``historical_conc`` baseline as a
# fallback.

# %%
cicero_cd = CICEROSCMPY2.from_native_distribution(
    cicero_bundle,
    mode=RunMode.CONCENTRATION_DRIVEN,
    output_variables=("Surface Air Temperature Change",),
    historical_em_file=str(
        cicero_bundle / "ssp245_em_gases_vupdate_2024_WMO_added_new.txt"
    ),
    historical_conc_file=str(
        cicero_bundle / "ssp245_conc_gases_vupdate_2024_WMO_added_new.txt"
    ),
    rf_solar_file=str(cicero_bundle / "solar_RCMIP_ssp245_RCMIP3.txt"),
    rf_volc_file=str(cicero_bundle / "VOLC_RCMIP_ssp245_RCMIP3.txt"),
    rf_luc_file=str(cicero_bundle / "LUCalbedo_RCMIP_ssp245_RCMIP3.txt"),
)
cicero_cd.supported_modes
