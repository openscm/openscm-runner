import logging
import os
import os.path

import matplotlib.pyplot as plt
import pyam
import seaborn as sns

from openscm_runner import run
from openscm_runner.adapters import MAGICC7


UPDATE = True  # Should we update the regression data?
PLOT = True  # Do you want to see a plot?
EXPECTED_MAGICC_VERSION = "v7.1.0-beta.2-27-g584b06ce"

DATA_FILE_SCENARIOS_NAME = "rcmip_scen_ssp_world_emissions.csv"
DATA_FILE_REGRESSION_NAME = "magicc7_regression.csv"

data_file_scenarios = os.path.join(os.path.dirname(__file__), DATA_FILE_SCENARIOS_NAME)
data_file_regression = os.path.join(
    os.path.dirname(__file__), DATA_FILE_REGRESSION_NAME
)


logger = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(threadName)s - %(levelname)s:  %(message)s")
stdoutHandler = logging.StreamHandler()
stdoutHandler.setFormatter(logFormatter)
logging.getLogger().addHandler(stdoutHandler)


scenarios = pyam.IamDataFrame(data_file_scenarios)

assert MAGICC7.get_version() == EXPECTED_MAGICC_VERSION

res = run(
    climate_models_cfgs={
        "MAGICC7": [
            {
                "core_climatesensitivity": 3,
                "rf_soxi_dir_wm2": -0.2,
                "out_temperature": 1,
            },
            {
                "core_climatesensitivity": 2,
                "rf_soxi_dir_wm2": -0.1,
                "out_temperature": 1,
            },
            {
                "core_climatesensitivity": 5,
                "rf_soxi_dir_wm2": -0.35,
                "out_temperature": 1,
            },
        ],
    },
    scenarios=scenarios,
)

if UPDATE:
    res.to_csv(data_file_regression)
else:
    expected_res = pyam.IamDataFrame(data_file_regression)
    pyam.assert_iamframe_equal(res, expected_res)

if PLOT:
    fig, axes = plt.subplots(ncols=2, sharey=True, sharex=True)
    pdf = res.filter(variable="Surface Temperature")
    pdf.line_plot(color="scenario", linewidth=0.25, ax=axes[0])

    sns_df = pdf.data
    sns.lineplot(
        data=sns_df, x="year", y="value", hue="scenario", ci="sd", ax=axes[1],
    )
    plt.show()
