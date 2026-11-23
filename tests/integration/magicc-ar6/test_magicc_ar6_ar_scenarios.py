"""
Integration tests: the MAGICC AR6 adapters for AR scenarios
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from openscm_runner.adapters.magicc_ar6 import (
    MAGICCAR6AdapterAR6Scenario,
    MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
    MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
    MAGICCAR6AdapterAR7Scenario,
    MAGICCAR6AdapterConfiguration,
)
from openscm_runner.adapters.magicc_ar6.ar_scenarios import (
    make_ar6_co2_forcing_only_experiments,
)
from openscm_runner.adapters.magicc_ar6.base import run_experiments
from openscm_runner.output_specs import OutputSpecs

from openscm_runner import (
    run_ar6_scenarios,
    run_ar6_scenarios_anthropogenic_only,
    run_ar6_scenarios_co2_forcing_only,
    run_ar7_scenarios,
)
from openscm_runner.adapter_errors import InvalidInputError

# These are the MAGICC AR6 adapters' tests (see docs/testing.md)
pytestmark = pytest.mark.magicc_ar6

TEST_DATA_DIR = Path(__file__).parents[2] / "test-data"

N_MEMBERS = 2
N_WORKERS = N_MEMBERS


def load_ar6_scenario() -> pd.DataFrame:
    """Load the test AR6 scenario"""
    out = pd.read_csv(
        TEST_DATA_DIR / "ar6-scenarios" / "ar6-aim-cge-2-2-en-npi2020-900f.csv"
    ).set_index(["model", "scenario", "region", "variable", "unit"])
    out.columns = out.columns.astype(int)

    return out


def test_ar6_scenarios_run() -> None:
    scenario = load_ar6_scenario()

    results = run_ar6_scenarios(
        (scenario,),
        adapters=(
            MAGICCAR6AdapterAR6Scenario(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=OutputSpecs(
            output_variables=(
                "Surface Air Temperature Change",
                "Effective Radiative Forcing",
            )
        ),
    )

    (output,) = results[0].outputs
    res = output.as_df()

    assert [m.ensemble_member for m in output.members] == ["0", "1"]
    assert res.columns.min() == 1750
    assert res.columns.max() == scenario.columns.max()
    # The experiment's index levels are carried through
    assert set(res.index.get_level_values("model")) == {"AIM/CGE 2.2"}
    assert set(res.index.get_level_values("scenario")) == {"EN_NPi2020_900f"}

    temperature = res.xs("Surface Air Temperature Change", level="variable")
    # Starts from zero, a sensible amount of warming by the end
    np.testing.assert_allclose(temperature[1750], 0.0)
    assert ((temperature[2100] > 1.0) & (temperature[2100] < 6.0)).all()


def test_ar6_subset_of_members_matches() -> None:
    """Running fewer members gives exactly the same result for those members"""
    scenario = load_ar6_scenario()
    output_specs = OutputSpecs(output_variables=("Surface Air Temperature Change",))

    (two,) = MAGICCAR6AdapterAR6Scenario(
        configuration=MAGICCAR6AdapterConfiguration.from_environment(
            testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
        )
    )((scenario,), output_specs=output_specs)
    (one,) = MAGICCAR6AdapterAR6Scenario(
        configuration=MAGICCAR6AdapterConfiguration.from_environment(
            testing_only_n_members=1, n_workers=1
        )
    )((scenario,), output_specs=output_specs)

    pd.testing.assert_frame_equal(one.members[0].data, two.members[0].data)


def test_ar6_adapter_verifies_inputs() -> None:
    """The adapter offers the same checks as `run_ar6_scenarios`"""
    adapter = MAGICCAR6AdapterAR6Scenario(
        configuration=MAGICCAR6AdapterConfiguration(
            magicc_root=Path("not-used"),
            ar6_probabilistic_distribution=Path("not-used"),
        )
    )
    with pytest.raises(InvalidInputError, match="first year must be 2015"):
        adapter(
            (load_ar6_scenario().loc[:, 2016:],),
            output_specs=OutputSpecs(output_variables=("Effective Radiative Forcing",)),
        )


def test_ar7_not_implemented() -> None:
    results = run_ar7_scenarios(
        (load_ar6_scenario().loc[:, 2023:],),
        adapters=(MAGICCAR6AdapterAR7Scenario(),),
        output_specs=OutputSpecs(output_variables=("Effective Radiative Forcing",)),
        run_checks=False,
    )
    with pytest.raises(NotImplementedError):
        _ = results[0].outputs


def run_ar6_variant(
    run: Callable[..., Any], adapter_cls: type, output_variables: tuple[str, ...]
) -> pd.DataFrame:
    """Run the test AR6 scenario with an AR6 scenario variant adapter"""
    results = run(
        (load_ar6_scenario(),),
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=OutputSpecs(output_variables=output_variables),
    )
    (output,) = results[0].outputs

    return output.as_df()


def test_ar6_anthropogenic_only() -> None:
    """The total forcing is the anthropogenic forcing"""
    res = run_ar6_variant(
        run_ar6_scenarios_anthropogenic_only,
        MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
        (
            "Surface Air Temperature Change",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Anthropogenic",
        ),
    )

    np.testing.assert_allclose(
        res.xs("Effective Radiative Forcing", level="variable").to_numpy(),
        res.xs(
            "Effective Radiative Forcing|Anthropogenic", level="variable"
        ).to_numpy(),
    )


def test_ar6_co2_forcing_only() -> None:
    """The total forcing is the CO2 forcing"""
    output_variables = (
        "Surface Air Temperature Change",
        "Effective Radiative Forcing",
        "Effective Radiative Forcing|CO2",
        "Atmospheric Concentrations|CO2",
        "Atmospheric Concentrations|CH4",
        "Atmospheric Concentrations|N2O",
    )
    scenario = load_ar6_scenario()
    co2_emissions = scenario.loc[
        scenario.index.get_level_values("variable").str.startswith("Emissions|CO2|")
    ]
    results = run_ar6_scenarios_co2_forcing_only(
        (co2_emissions,),
        adapters=(
            MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=OutputSpecs(output_variables=output_variables),
    )
    (output,) = results[0].outputs
    res = output.as_df()
    full = run_ar6_variant(
        run_ar6_scenarios,
        MAGICCAR6AdapterAR6Scenario,
        ("Surface Air Temperature Change", "Atmospheric Concentrations|CO2"),
    )

    np.testing.assert_allclose(
        res.xs("Effective Radiative Forcing", level="variable").to_numpy(),
        res.xs("Effective Radiative Forcing|CO2", level="variable").to_numpy(),
    )
    # Everything except CO2 is at pre-industrial (1750) for the whole run
    # (MAGICC's history's 1750 values)
    for gas, pi in (("CH4", 731.406), ("N2O", 273.865)):
        np.testing.assert_allclose(
            res.xs(f"Atmospheric Concentrations|{gas}", level="variable").to_numpy(),
            pi,
            atol=0.01,
            err_msg=gas,
        )

    # The CO2 history is the usual one
    co2 = res.xs("Atmospheric Concentrations|CO2", level="variable")
    full_co2 = full.xs("Atmospheric Concentrations|CO2", level="variable")
    np.testing.assert_allclose(co2.loc[:, :2014], full_co2.loc[:, :2014])

    # A different run from the full one
    # (whether there is more or less warming depends on the member,
    # because the sign of the non-CO2 forcing does)
    temperature = res.xs("Surface Air Temperature Change", level="variable")
    full_temperature = full.xs("Surface Air Temperature Change", level="variable")
    assert not np.allclose(temperature.to_numpy(), full_temperature.to_numpy())


@pytest.mark.parametrize(
    "adapter_cls, variable",
    (
        pytest.param(
            MAGICCAR6AdapterAR6ScenarioAnthropogenicOnly,
            "Effective Radiative Forcing|Solar",
            id="anthropogenic-only",
        ),
        pytest.param(
            MAGICCAR6AdapterAR6ScenarioCO2ForcingOnly,
            "Effective Radiative Forcing|Land-use Change",
            id="co2-forcing-only",
        ),
    ),
)
def test_ar6_variants_dont_offer_forcing_they_leave_out(
    adapter_cls: type, variable: str
) -> None:
    """MAGICC still reports these, but they aren't part of the run"""
    adapter = adapter_cls(
        configuration=MAGICCAR6AdapterConfiguration(
            magicc_root=Path("not-used"),
            ar6_probabilistic_distribution=Path("not-used"),
            run_checks=False,
        )
    )
    with pytest.raises(ValueError, match="aren't supported by this adapter"):
        adapter(
            (load_ar6_scenario(),),
            output_specs=OutputSpecs(output_variables=(variable,)),
        )


def test_ar6_co2_forcing_only_has_no_ch4_oxidation() -> None:
    """
    No CO2 from the oxidation of the scenario's (or history's) CH4

    The only CO2 from CH4 oxidation is from the CH4 permafrost releases
    as it warms (see the adapter's docstring).
    Checked with MAGICC's own diagnostics,
    which the adapter doesn't offer as outputs.
    """
    scenario = load_ar6_scenario()
    co2_emissions = scenario.loc[
        scenario.index.get_level_values("variable").str.startswith("Emissions|CO2|")
    ]
    configuration = MAGICCAR6AdapterConfiguration.from_environment(
        testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
    )
    experiments = make_ar6_co2_forcing_only_experiments(
        (co2_emissions,),
        output_variables={
            "CH4 oxidation": "DAT_CH4_2CO2_OXIDISATION_EMIS",
            "Permafrost CH4": "DAT_CH4PF_EMIS",
            "Fossil CO2": "DAT_CO2I_EMIS",
        },
        installation=configuration.installation,
    )
    (output,) = run_experiments(experiments, configuration=configuration)
    res = output.as_df()
    oxidation = res.xs("CH4 oxidation", level="variable")
    permafrost = res.xs("Permafrost CH4", level="variable")

    # No oxidation until permafrost starts releasing CH4
    no_permafrost = (permafrost.cumsum(axis="columns") == 0.0).to_numpy()
    assert no_permafrost[:, : 1900 - 1750].all()
    np.testing.assert_allclose(oxidation.to_numpy()[no_permafrost], 0.0, atol=1e-12)
    # Then only a little (fossil CO2 emissions are several GtC/yr)
    assert (oxidation.to_numpy() < 0.05).all()
    assert (res.xs("Fossil CO2", level="variable")[2020] > 5.0).all()
