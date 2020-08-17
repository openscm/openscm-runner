import numpy.testing as npt
from scmdata import ScmDataFrame

from openscm_runner import run
from openscm_runner.adapters import MAGICC7
from openscm_runner.utils import calculate_quantiles


RTOL = 1e-5


def magicc7_is_available():
    try:
        magicc_version = MAGICC7.get_version()
        if magicc_version != "v7.4.0":
            raise AssertionError("Wrong MAGICC version for tests ({})".format(magicc_version))
        return True


def test_magicc7_run(test_scenarios, magicc7_is_available):
    res = run(
        climate_models_cfgs={
            "MAGICC7": [
                {
                    "core_climatesensitivity": 3,
                    "rf_soxi_dir_wm2": -0.2,
                    "out_temperature": 1,
                    "out_forcing": 1,
                    "out_dynamic_vars": ["DAT_AEROSOL_ERF"],
                },
                {
                    "core_climatesensitivity": 2,
                    "rf_soxi_dir_wm2": -0.1,
                    "out_temperature": 1,
                    "out_forcing": 1,
                },
                {
                    "core_climatesensitivity": 5,
                    "rf_soxi_dir_wm2": -0.35,
                    "out_temperature": 1,
                    "out_forcing": 1,
                },
            ],
        },
        scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
        output_variables=(
            "Surface Temperature",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
            # "CO2 Air to Land Flux",  # todo: add this back in
        ),
        full_config=False,
    )

    assert isinstance(res, ScmDataFrame)
    assert res["run_id"].min() == 0
    assert res["run_id"].max() == 8
    assert res.get_unique_meta(
        "climate_model", no_duplicates=True
    ) == "MAGICC{}".format(MAGICC7.get_version())
    assert set(res.get_unique_meta("variable")) == set(
        [
            "Surface Temperature",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
        ]
    )

    npt.assert_allclose(
        2.6126502,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp126"
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        1.4454666,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp126"
        ).values.min(),
        rtol=RTOL,
    )

    npt.assert_allclose(
        5.5218109,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp370"
        ).values.max(),
        rtol=RTOL,
    )
    npt.assert_allclose(
        2.7332273999999996,
        res.filter(
            variable="Surface Temperature", region="World", year=2100, scenario="ssp370"
        ).values.min(),
        rtol=RTOL,
    )

    # check we can also calcluate quantiles
    quantiles = calculate_quantiles(res, [0.05, 0.17, 0.5, 0.83, 0.95])

    npt.assert_allclose(
        1.4932964,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.05,
        ).values,
        rtol=RTOL,
    )
    npt.assert_allclose(
        2.54376164,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp126",
            quantile=0.95,
        ).values,
        rtol=RTOL,
    )

    npt.assert_allclose(
        2.8361154,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.05,
        ).values,
        rtol=RTOL,
    )
    npt.assert_allclose(
        5.34584055,
        quantiles.filter(
            variable="Surface Temperature",
            region="World",
            year=2100,
            scenario="ssp370",
            quantile=0.95,
        ).values,
        rtol=RTOL,
    )
