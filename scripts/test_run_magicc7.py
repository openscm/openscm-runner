import os
import os.path

import pyam

from openscm_runner import run
from openscm_runner.adapters import MAGICC7

UPDATE = True  # Should we update the regression data?
EXPECTED_MAGICC_VERSION = "v7.1.0-beta.2-27-g584b06ce"

DATA_FILE_SCENARIOS_NAME = "rcmip_scen_ssp_world_emissions.csv"
DATA_FILE_REGRESSION_NAME = "magicc7_regression.csv"

data_file_scenarios = os.path.join(os.path.dirname(__file__), DATA_FILE_SCENARIOS_NAME)
data_file_regression = os.path.join(
    os.path.dirname(__file__), DATA_FILE_REGRESSION_NAME
)


scenarios = pyam.IamDataFrame(data_file_scenarios)

assert MAGICC7.get_version() == EXPECTED_MAGICC_VERSION

res = run(
    climate_models_cfgs={
        "MAGICC7": [
            {"core_climatesensitivity": 3, "rf_soxi_dir_wm2": -0.2},
            {"core_climatesensitivity": 2, "rf_soxi_dir_wm2": -0.1},
            {"core_climatesensitivity": 5, "rf_soxi_dir_wm2": -0.35},
        ],
    },
    scenarios=scenarios,
)

if UPDATE:
    res.to_csv(data_file_regression)
else:
    expected_res = pyam.IamDataFrame(data_file_regression)
    pyam.assert_iamframe_equal(res, expected_res)
