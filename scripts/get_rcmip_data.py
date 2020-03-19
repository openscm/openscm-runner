import os.path
import requests

import pyam
import pymagicc.definitions

RCMIP_EMISSIONS_URL = "https://drive.google.com/u/0/uc?id=1krA0lficstXqahlNCko7nbfqgjKrd_Sa&export=download"
DATA_FILE_RAW_NAME = "rcmip_emissions.csv"
DATA_FILE_OUT_NAME = "rcmip_scen_ssp_world_emissions.csv"

data_file_raw = os.path.join(os.path.dirname(__file__), DATA_FILE_RAW_NAME)
data_file_out = os.path.join(os.path.dirname(__file__), DATA_FILE_OUT_NAME)

if not os.path.isfile(data_file_raw):
    request = requests.get(RCMIP_EMISSIONS_URL, allow_redirects=True)
    with open(data_file_raw, "wb") as fh:
        fh.write(request.content)

keep_vars = pymagicc.definitions.convert_magicc7_to_openscm_variables(
    [
        "{}_EMIS".format(v)
        for v in pymagicc.definitions.PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1
    ]
)
keep_vars = [
    v.replace("HFC4310", "HFC4310mee").replace("SOx", "Sulfur").replace("NMVOC", "VOC")
    for v in keep_vars
]
data = pyam.IamDataFrame(data_file_raw)
data_out = data.filter(
    scenario="ssp*", region="World", year=range(2015, 2101)
).timeseries()
data_out.index = data_out.index.droplevel(["activity_id", "mip_era"])
data_out = data_out.reset_index()
data_out["variable"] = data_out["variable"].apply(
    lambda x: x.replace("Montreal Gases|", "")
    .replace("F-Gases|HFC|", "")
    .replace("F-Gases|PFC|", "")
    .replace("F-Gases|CFC|", "")
    .replace("F-Gases|", "")
    .replace("CFC|", "")
)

data_out = pyam.IamDataFrame(data_out).filter(variable=keep_vars)
data_out.to_csv(data_file_out)
