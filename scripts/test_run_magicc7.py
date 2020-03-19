import pyam

from openscm_runner import run

UPDATE = True  # Should we update the regression data?
DATA_FILE_SCENARIOS = "rcmip_scen_emissions.csv"
DATA_FILE_REGRESSION = "magicc7_regression.csv"


assert False, "Check MAGICC7 version"

scenarios = pyam.IamDataFrame(DATA_FILE_SCENARIOS)


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
    res.to_csv(DATA_FILE_REGRESSION)
else:
    expected_res = pyam.IamDataFrame(DATA_FILE_REGRESSION)
    pyam.assert_iamframe_equal(res, expected_res)
