import os
import os.path

import pyam

from openscm_runner import run

UPDATE = True  # Should we update the regression data?
DATA_FILE_SCENARIOS_NAME = "rcmip_scen_ssp_world_emissions.csv"
DATA_FILE_REGRESSION_NAME = "magicc7_regression.csv"

data_file_scenarios = os.path.join(os.path.dirname(__file__), DATA_FILE_SCENARIOS_NAME)
data_file_regression = os.path.join(
    os.path.dirname(__file__), DATA_FILE_REGRESSION_NAME
)


scenarios = pyam.IamDataFrame(data_file_scenarios)

assert False, "Check MAGICC7 version"

res = run(
    {
        "MAGICC7": [
            {"core_climatesensitivity": 3, "rf_soxi_dir_wm2": -0.2},
            {"core_climatesensitivity": 2, "rf_soxi_dir_wm2": -0.1},
            {"core_climatesensitivity": 5, "rf_soxi_dir_wm2": -0.35},
        ],
    },
)

if UPDATE:
    res.to_csv(data_file_regression)
else:
    expected_res = pyam.IamDataFrame(data_file_regression)
    pyam.assert_iamframe_equal(res, expected_res)
