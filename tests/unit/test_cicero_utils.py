import numpy.testing as npt

from openscm_runner.adapters.utils.cicero_utils import make_scenario_common


def test_make_scenario_common():
    npt.assert_allclose(
        3.0 / 11.0 * 1000.0,
        make_scenario_common._unit_conv_factor("Gg CO2/yr", "Mg C/ yr"),
    )
    npt.assert_allclose(
        28 / 44 / 1.0e12,
        make_scenario_common._unit_conv_factor("kg N2O / yr", "Pg N2ON / yr"),
    )
    npt.assert_allclose(
        14 / 46 / 1.0e12,
        make_scenario_common._unit_conv_factor("kt NOx / yr", "Pt N / yr"),
    )
    npt.assert_allclose(
        0.5,
        make_scenario_common._unit_conv_factor("Tg SO2 / yr", "Tg S / yr"),
    )
    npt.assert_allclose(
        1.0,
        make_scenario_common._unit_conv_factor("Gg  Halon1211 / yr", "GgH1211 / yr"),
    )
    npt.assert_allclose(
        1.0,
        make_scenario_common._unit_conv_factor("Gg  Halon2402 / yr", "GgH2402 / yr"),
    )
