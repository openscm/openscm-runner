import numpy.testing as npt

from openscm_runner.adapters.fair_adapter._scmdf_to_emissions import scmdf_to_emissions


# All emissions that are not covered by FaIR (see
# EMISSIONS_SPECIES_UNITS_CONTEXT) should be ignored, e.g.
# 'Emissions|CO2' (which is the sum of any sub-categories)
def test_emissions_to_ignore(test_scenario_ssp370_world):
    emissions = scmdf_to_emissions(test_scenario_ssp370_world)

    npt.assert_allclose(
        emissions[0, 1], 2.59244179e-03, rtol=1e-5,
    )
    assert emissions.shape[1] == 40
