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

# %%
from pathlib import Path
import pint
import openscm_units
import pandas_openscm
import pandas_openscm.io
import pooch
import pandas_indexing as pix
import numpy as np
from pymagicc.definitions import convert_magicc7_to_openscm_variables
from pymagicc.io import MAGICCData
from gcages.renaming import SupportedNamingConventions, convert_variable_name
from gcages.scm_running import (
    convert_openscm_runner_output_names_to_magicc_output_names,
    run_scms,
)
import tqdm.auto
import platform
import os
from typing import Any
import json
import multiprocessing
from functools import partial
import warnings

# %%
# Ignore pandas warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# %%
pandas_openscm.register_pandas_accessors()

# %%
# Obviously have to adjust to your own context
MAGICC_BASE_DIR = Path("bin/magicc/magicc-v7.5.3")

# %%
MAGICC_EXE_PATH = MAGICC_BASE_DIR / "bin"
MAGICC_EXE_PATH.exists()

# %%
MAGICC_PROB_SET = Path("bin/magicc/magicc-ar6-0fd0f62-f023edb-drawnset/0fd0f62-derived-metrics-id-f023edb-drawnset.json")
MAGICC_PROB_SET.exists()

# %%
# Setup pint
pint.set_application_registry(openscm_units.unit_registry)

# %%
# pandas_openscm.register_pandas_accessor()

# %%
SCENARIO_TO_RUN = "ssp245"

# %%
rcmip_concentrations_file = pooch.retrieve(
    url="https://rcmip-protocols-au.s3-ap-southeast-2.amazonaws.com/v5.1.0/rcmip-concentrations-annual-means-v5-1-0.csv",
    known_hash="b6749ea32cc36eb0badc5d028b5b7b7bbcc56606144155fa2c0c3f9ceeac18c9",
    path=Path("data/rcmip/"),
    progressbar=True,
)
rcmip_concentrations = pandas_openscm.io.load_timeseries_csv(
    rcmip_concentrations_file,
    index_columns=[
        "model",
        "scenario",
        "variable",
        "region",
        "unit",
        "mip_era",
        "activity_id",
    ],
    out_columns_type=int,
)
rcmip_concentrations = rcmip_concentrations.loc[
    pix.isin(scenario=SCENARIO_TO_RUN, region="World")
]

# %% [markdown]
# ## Write MAGICC concentration files

# %%
CONC_MAGICC_FLAG_MAP = {
    "Atmospheric Concentrations|CO2": "file_co2_conc",
    "Atmospheric Concentrations|CH4": "file_ch4_conc",
    "Atmospheric Concentrations|N2O": "file_n2o_conc",
    "Atmospheric Concentrations|CF4": "fgas_files_conc__0",
    "Atmospheric Concentrations|C2F6": "fgas_files_conc__1",
    "Atmospheric Concentrations|C3F8": "fgas_files_conc__2",
    "Atmospheric Concentrations|C4F10": "fgas_files_conc__3",
    "Atmospheric Concentrations|C5F12": "fgas_files_conc__4",
    "Atmospheric Concentrations|C6F14": "fgas_files_conc__5",
    "Atmospheric Concentrations|C7F16": "fgas_files_conc__6",
    "Atmospheric Concentrations|C8F18": "fgas_files_conc__7",
    "Atmospheric Concentrations|cC4F8": "fgas_files_conc__8",
    "Atmospheric Concentrations|HFC23": "fgas_files_conc__9",
    "Atmospheric Concentrations|HFC32": "fgas_files_conc__10",
    "Atmospheric Concentrations|HFC4310": "fgas_files_conc__11",
    "Atmospheric Concentrations|HFC125": "fgas_files_conc__12",
    "Atmospheric Concentrations|HFC134a": "fgas_files_conc__13",
    "Atmospheric Concentrations|HFC143a": "fgas_files_conc__14",
    "Atmospheric Concentrations|HFC152a": "fgas_files_conc__15",
    "Atmospheric Concentrations|HFC227ea": "fgas_files_conc__16",
    "Atmospheric Concentrations|HFC236fa": "fgas_files_conc__17",
    "Atmospheric Concentrations|HFC245fa": "fgas_files_conc__18",
    "Atmospheric Concentrations|HFC365mfc": "fgas_files_conc__19",
    "Atmospheric Concentrations|NF3": "fgas_files_conc__20",
    "Atmospheric Concentrations|SF6": "fgas_files_conc__21",
    "Atmospheric Concentrations|SO2F2": "fgas_files_conc__22",
    "Atmospheric Concentrations|CFC11": "mhalo_files_conc__0",
    "Atmospheric Concentrations|CFC12": "mhalo_files_conc__1",
    "Atmospheric Concentrations|CFC113": "mhalo_files_conc__2",
    "Atmospheric Concentrations|CFC114": "mhalo_files_conc__3",
    "Atmospheric Concentrations|CFC115": "mhalo_files_conc__4",
    "Atmospheric Concentrations|HCFC22": "mhalo_files_conc__5",
    "Atmospheric Concentrations|HCFC141b": "mhalo_files_conc__6",
    "Atmospheric Concentrations|HCFC142b": "mhalo_files_conc__7",
    "Atmospheric Concentrations|CH3CCl3": "mhalo_files_conc__8",
    "Atmospheric Concentrations|CCl4": "mhalo_files_conc__9",
    "Atmospheric Concentrations|CH3Cl": "mhalo_files_conc__10",
    "Atmospheric Concentrations|CH2Cl2": "mhalo_files_conc__11",
    "Atmospheric Concentrations|CHCl3": "mhalo_files_conc__12",
    "Atmospheric Concentrations|CH3Br": "mhalo_files_conc__13",
    "Atmospheric Concentrations|Halon1211": "mhalo_files_conc__14",
    "Atmospheric Concentrations|Halon1301": "mhalo_files_conc__15",
    "Atmospheric Concentrations|Halon2402": "mhalo_files_conc__16",
    "Atmospheric Concentrations|Halon1202": "mhalo_files_conc__17",
}

# %%
magicc_run_dir = MAGICC_EXE_PATH.parents[0] / "run"
magicc_file_dir = magicc_run_dir / "rcmip-ghgs"
magicc_file_dir.mkdir(exist_ok=True, parents=True)

# %%
magicc_concentration_cfg = {
    "file_co2_conc": None,
    "co2_switchfromconc2emis_year": 10000,
    "file_ch4_conc": None,
    "ch4_switchfromconc2emis_year": 10000,
    "file_n2o_conc": None,
    "n2o_switchfromconc2emis_year": 10000,
    "fgas_files_conc": [None] * 23,
    "fgas_switchfromconc2emis_year": 10000,
    "mhalo_files_conc": [None] * 18,
    "mhalo_switchfromconc2emis_year": 10000,
}
# Halon1202, just ignore
magicc_concentration_cfg["mhalo_files_conc"][17] = ""

# %%
for ghg, ghgdf in tqdm.auto.tqdm(rcmip_concentrations.groupby("variable")):
    ghg_magicc = (
        ghg.replace("HFC4310mee", "HFC4310")
        .replace("HFC|", "")
        .replace("F-Gases|", "")
        .replace("CFC|", "")
        .replace("PFC|", "")
        .replace("Montreal Gases|", "")
    )
    ghg_magicc_fn = ghg_magicc.replace("Atmospheric Concentrations|", "")

    openscm_runner_variable = convert_magicc7_to_openscm_variables(
        f"{ghg_magicc_fn}_conc".upper()
    )

    # Check data is annual, but can skip here as we already know it's annual
    exp_years = np.arange(ghgdf.columns.min(), ghgdf.columns.max() + 1)
    np.testing.assert_equal(
        ghgdf.columns.values,
        exp_years,
    )

    writer = MAGICCData(ghgdf.copy())
    writer["todo"] = "SET"
    writer["variable"] = ghg_magicc
    writer.metadata = {
        "header": f"tmp {SCENARIO_TO_RUN}",
        # TODO: better provenance
        "source": SCENARIO_TO_RUN,
    }

    fn = magicc_file_dir / f"{SCENARIO_TO_RUN}_{ghg_magicc_fn}_CONC.IN".upper()
    writer.write(str(fn), magicc_version=7)

    magicc_flag = CONC_MAGICC_FLAG_MAP[openscm_runner_variable]
    if "__" in magicc_flag:
        key, index = magicc_flag.split("__")
        magicc_concentration_cfg[key][int(index)] = str(fn.relative_to(magicc_run_dir))

    else:
        magicc_concentration_cfg[magicc_flag] = str(fn.relative_to(magicc_run_dir))
#     # break


for k, v in magicc_concentration_cfg.items():
    if isinstance(v, list):
        for vv in v:
            if vv is None:
                raise AssertionError(k)

    elif v is None:
        raise AssertionError(k)

# %% [markdown]
# ## Run MAGICC

# %%
if platform.system() == "Darwin":
    if platform.processor() == "arm":
        MAGICC_EXE = MAGICC_EXE_PATH / "magicc-darwin-arm64"
        os.environ["DYLD_LIBRARY_PATH"] = "/opt/homebrew/opt/gfortran/lib/gcc/current/"

elif platform.system() == "Linux":
    MAGICC_EXE = MAGICC_EXE_PATH / "magicc"

elif platform.system() == "Windows":
    MAGICC_EXE = MAGICC_EXE_PATH / "magicc.exe"



# %%
output_variables = (
    "Surface Air Temperature Change",
    # "Surface Air Ocean Blended Temperature Change",
    "Effective Radiative Forcing",
    # "Effective Radiative Forcing|Aerosols",
    # "Effective Radiative Forcing|Aerosols|Direct Effect",
    # "Effective Radiative Forcing|Aerosols|Indirect Effect",
    # "Effective Radiative Forcing|Greenhouse Gases",
    # "Effective Radiative Forcing|CO2",
    # "Effective Radiative Forcing|Ozone",
    # "Effective Radiative Forcing|Tropospheric Ozone",
    # "Effective Radiative Forcing|Stratospheric Ozone",
    # "Effective Radiative Forcing|Solar",
    # "Effective Radiative Forcing|Volcanic",
    # "Heat Uptake",
    # "Heat Uptake|Ocean",
    # "Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O",
    # "Effective Radiative Forcing|Land-use Change",
    # "Effective Radiative Forcing|Black Carbon on Snow",
    # "Effective Radiative Forcing|Aviation|Contrail and Cirrus",
    # "Effective Radiative Forcing|Aviation|H2O",
    "Atmospheric Concentrations|CO2",
    "Atmospheric Concentrations|CH4",
    "Atmospheric Concentrations|N2O",
)


# %%
def load_magicc_cfgs(
    prob_distribution_path: Path,
    output_variables: tuple[str, ...],
    magicc_concentration_cfg: dict[str, Any],
    startyear: int = 1750,
) -> dict[str, list[dict[str, Any]]]:
    """
    Load MAGICC's configuration

    Parameters
    ----------
    prob_distribution_path
        Path to the file containing the probabilistic distribution

    output_variables
        Output variables

    startyear
        Starting year of the runs

    magicc_concentration_cfg
        Concentration configuration for MAGICC

    Returns
    -------
    :
        Config that can be used to run MAGICC
    """
    with open(prob_distribution_path) as fh:
        cfgs_raw = json.load(fh)

    cfgs_physical = [
        {
            "run_id": c["paraset_id"],
            **{k.lower(): v for k, v in c["nml_allcfgs"].items()},
        }
        for c in cfgs_raw["configurations"]
    ]

    common_cfg = {
        "startyear": startyear,
        # Note: endyear handled in gcages, which I don't love but is fine for now
        "out_dynamic_vars": convert_openscm_runner_output_names_to_magicc_output_names(
            output_variables
        ),
        "out_ascii_binary": "BINARY",
        "out_binary_format": 2,
        "rf_total_runmodus": "ALL",
        # Ensure openscm-runner doesn't muck with the settings below
        "file_tuningmodel_2": "",
        "rf_initialization_method": "ZEROSTARTSHIFT",
        # This is what actually sets the emissions file
        "file_emisscen": f"rcmip/{SCENARIO_TO_RUN.upper()}_EMMS.SCEN7",
        "file_emisscen_2": "",
        "file_emisscen_3": "",
        "file_emisscen_4": "",
        "file_emisscen_5": "",
        "file_emisscen_6": "",
        "file_emisscen_7": "",
        "file_emisscen_8": "",
    }

    run_config = [
        {**common_cfg, **magicc_concentration_cfg, **physical_cfg}
        for physical_cfg in cfgs_physical
    ]
    climate_models_cfgs = {"MAGICC7": run_config}

    return climate_models_cfgs


climate_models_cfgs = load_magicc_cfgs(
    prob_distribution_path=MAGICC_PROB_SET,
    output_variables=output_variables,
    magicc_concentration_cfg=magicc_concentration_cfg,
    # startyear=1750,
    startyear=1850,
)

# %%
badly_converted = [
    v for v in climate_models_cfgs["MAGICC7"][0]["out_dynamic_vars"] if v.upper() != v
]
if badly_converted:
    raise AssertionError(badly_converted)


# %%
n_magicc_workers = multiprocessing.cpu_count()
os.environ["MAGICC_EXECUTABLE_7"] = str(MAGICC_EXE)

# %%
# Get dummy emissions to keep openscm-runner happy
rcmip_emissions_file = pooch.retrieve(
    url="https://rcmip-protocols-au.s3-ap-southeast-2.amazonaws.com/v5.1.0/rcmip-emissions-annual-means-v5-1-0.csv",
    known_hash="2af9f90c42f9baa813199a902cdd83513fff157a0f96e1d1e6c48b58ffb8b0c1",
    path=Path("data/rcmip/"),
    progressbar=True,
)
rcmip_emissions = pandas_openscm.io.load_timeseries_csv(
    rcmip_emissions_file,
    index_columns=[
        "model",
        "scenario",
        "variable",
        "region",
        "unit",
        "mip_era",
        "activity_id",
    ],
    out_columns_type=int,
)
rcmip_emissions = rcmip_emissions.loc[pix.isin(scenario=SCENARIO_TO_RUN)]
# rcmip_emissions

complete = (
    rcmip_emissions.reset_index(["mip_era", "activity_id"], drop=True)
    .loc[
        pix.ismatch(variable="*|*")
        | pix.ismatch(variable="*|CO2|*")
        | pix.ismatch(variable="**F-Gases**")
        | pix.ismatch(variable="**Montreal Gases**")
    ]
    .loc[~pix.isin(variable="Emissions|CO2")]
    .loc[pix.isin(region="World")]
)
if len(complete.pix.unique("variable")) != 52:
    raise AssertionError

complete = complete.T.interpolate(method="index").T
# Only run until 2100 for this work
complete = complete.loc[:, :2100]

complete = complete.openscm.update_index_levels(
    {
        "variable": partial(
            convert_variable_name,
            from_convention=SupportedNamingConventions.RCMIP,
            to_convention=SupportedNamingConventions.CMIP7_SCENARIOMIP,
        )
    },
)
MAGICC_START_YEAR = 2015
complete_scenarios_only = complete.loc[
    :,
    MAGICC_START_YEAR:,
].sort_index()

complete_scenarios_only_openscm_runner = (
    complete_scenarios_only.openscm.update_index_levels(
        {
            "variable": partial(
                convert_variable_name,
                from_convention=SupportedNamingConventions.CMIP7_SCENARIOMIP,
                to_convention=SupportedNamingConventions.OPENSCM_RUNNER,
            )
        },
    )
)


complete_scenarios_only_openscm_runner

# %%
scm_results = run_scms(
    scenarios=complete_scenarios_only_openscm_runner,
    climate_models_cfgs=climate_models_cfgs,
    output_variables=output_variables,
    scenario_group_levels=["model", "scenario"],
    n_processes=n_magicc_workers,
    db=None,
    verbose=True,
    progress=True,
)


# %%
# Check against AR6 WG1 Cross-Chapter Box 7.1
tmp = scm_results.loc[pix.isin(variable=["Surface Air Temperature Change"])]
tmp.subtract(tmp.loc[:, 1995:2014].mean(axis="columns"), axis="rows").loc[
    :, 2081:2100
].mean(axis="columns").quantile([0.05, 0.5, 0.95])

# %%
