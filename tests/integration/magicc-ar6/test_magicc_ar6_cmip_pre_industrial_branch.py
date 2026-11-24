"""
Integration tests: the MAGICC AR6 adapters for CMIP experiments
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from openscm_units import unit_registry

from openscm_runner import (
    run_co2_concentration_driven_from_cmip6_pre_industrial,
    run_co2_concentration_driven_from_cmip7_pre_industrial,
    run_co2_emission_driven_from_cmip6_pre_industrial,
    run_co2_emission_driven_from_cmip7_pre_industrial,
    run_concentration_driven_from_cmip6_pre_industrial,
    run_concentration_driven_from_cmip7_pre_industrial,
    run_esm_all_ghg_from_cmip6_pre_industrial,
    run_esm_all_ghg_from_cmip7_pre_industrial,
    run_esm_from_cmip6_pre_industrial,
    run_esm_from_cmip7_pre_industrial,
)
from openscm_runner.adapters.magicc_ar6 import (
    MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
    MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
    MAGICCAR6AdapterConfiguration,
    MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial,
    MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial,
    MAGICCAR6AdapterESMFromCMIP6PreIndustrial,
    MAGICCAR6AdapterESMFromCMIP7PreIndustrial,
)
from openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch import (
    EMISSIONS_DRIVEN_FILE_RULES,
    SUPPORTED_OUTPUT_VARIABLES,
    derive_emissions_driven_files,
    load_historical_emissions,
    make_history_files,
    run_pre_industrial_branch_experiments,
)
from openscm_runner.adapters.magicc_ar6.io import read_namelist, read_tabular_file
from openscm_runner.adapters.magicc_ar6.naming import (
    CONCENTRATION_UNITS,
    EMISSIONS_VARIABLES,
    FGAS_NAMES,
    MHALO_NAMES,
    to_magicc_gas,
)
from openscm_runner.adapters.magicc_ar6.pre_industrial import (
    CMIP6_PRE_INDUSTRIAL,
    CMIP7_PRE_INDUSTRIAL,
    PreIndustrialValues,
)
from openscm_runner.cmip_pre_industrial_branch.inputs import (
    CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES,
    CMIP7_CO2_ESM_EMISSION_VARIABLES,
    CMIP7_CONCENTRATION_VARIABLES,
    CMIP7_GHG_EMISSION_VARIABLES,
    CMIP7_NATURAL_FORCING_VARIABLES,
)
from openscm_runner.output_specs import OutputSpecs

# These are the MAGICC AR6 adapters' tests (see docs/development/testing.md)
pytestmark = pytest.mark.magicc_ar6

TEST_DATA_DIR = Path(__file__).parents[2] / "test-data"

N_MEMBERS = 2
N_WORKERS = N_MEMBERS


def load_ar6_scenario() -> pd.DataFrame:
    out = pd.read_csv(
        TEST_DATA_DIR / "ar6-scenarios" / "ar6-aim-cge-2-2-en-npi2020-900f.csv"
    ).set_index(["model", "scenario", "region", "variable", "unit"])
    out.columns = out.columns.astype(int)

    return out


GHG_ERF_COMPONENTS = (
    "Effective Radiative Forcing|CO2",
    "Effective Radiative Forcing|CH4",
    "Effective Radiative Forcing|N2O",
    "Effective Radiative Forcing|F-Gases",
    "Effective Radiative Forcing|Montreal Protocol Halogen Gases",
)

HELD_AT_PI_CONTROL_ERF_COMPONENTS = (
    "Effective Radiative Forcing|Aerosols",
    "Effective Radiative Forcing|Land-use Change",
)
"""ERF components which stay at zero unless emissions change"""


def get_pi_control_emissions(
    pre_industrial: PreIndustrialValues, variable: str
) -> tuple[str, float]:
    """
    Get the emissions we use as piControl emissions (unit, value)

    The CMIP era's historical emissions in 1850
    (see `PreIndustrialValues.pi_control_emissions` and decision B19),
    in MAGICC's units.
    """
    spec = EMISSIONS_VARIABLES[variable]
    if spec.gas not in pre_industrial.pi_control_emissions:
        return spec.unit, 0.0

    value, unit = pre_industrial.pi_control_emissions[spec.gas]

    return unit, value


def get_pi_control_emissions_in_unit(
    pre_industrial: PreIndustrialValues, gas: str, unit: str
) -> float:
    """
    Get `PreIndustrialValues.pi_control_emissions` of `gas` in `unit`

    These are the CMIP era's historical emissions in 1850.
    For CO2, they aren't what the adapters use as piControl (zero, see decision B19).
    """
    value, value_unit = pre_industrial.pi_control_emissions[gas]

    return float(unit_registry.Quantity(value, value_unit).to(unit).magnitude)


CMIP_OUTPUTS = OutputSpecs(output_variables=SUPPORTED_OUTPUT_VARIABLES)


def make_concentrations(  # noqa: PLR0913
    pre_industrial: PreIndustrialValues,
    *,
    co2_only: bool,
    co2_growth_rate: float = 0.01,
    n_years: int = 140,
    solar: float | np.ndarray[Any, Any] = 0.0,
    volcanic: float | np.ndarray[Any, Any] = 0.0,
    ch4_growth_rate: float = 0.0,
    emissions_growth_rates: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Make 1pctCO2-style input: every species at piControl, except CO2

    Parameters
    ----------
    pre_industrial
        Pre-industrial values to start from

    co2_only
        Only return CO2 (input for the CO2-only adapters)

    co2_growth_rate
        Annual CO2 growth rate (0.0 gives a piControl run)

    n_years
        Number of years

    solar
        Solar ERF (not included if `co2_only`)

    volcanic
        Volcanic ERF (not included if `co2_only`)

    ch4_growth_rate
        Annual CH4 growth rate (only used if not `co2_only`)

    emissions_growth_rates
        Annual growth rate of aerosol emissions, keyed by variable
        (only used if not `co2_only`, default all zero)
    """
    years = list(range(1850, 1850 + n_years))
    variables = (
        ["Atmospheric Concentrations|CO2"]
        if co2_only
        else sorted(CMIP7_CONCENTRATION_VARIABLES)
    )
    growth_rates = {"CO2": co2_growth_rate, "CH4": ch4_growth_rate}
    rows = {}
    for variable in variables:
        gas = to_magicc_gas(variable.split("|")[1])
        pi = pre_industrial.pi_control_concentrations[gas]
        values = pi * (1 + growth_rates.get(gas, 0.0)) ** np.arange(n_years)
        rows[("1pctCO2", variable, "World", CONCENTRATION_UNITS[gas])] = values

    if not co2_only:
        for variable, value in (
            ("Effective Radiative Forcing|Solar", solar),
            ("Effective Radiative Forcing|Volcanic", volcanic),
        ):
            rows[("1pctCO2", variable, "World", "W/m^2")] = np.broadcast_to(
                value, n_years
            )

        emissions_growth_rates = emissions_growth_rates or {}
        for variable in sorted(CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES):
            unit, value = get_pi_control_emissions(pre_industrial, variable)
            rows[("1pctCO2", variable, "World", unit)] = value * (
                1 + emissions_growth_rates.get(variable, 0.0)
            ) ** np.arange(n_years)

    return pd.DataFrame(
        list(rows.values()),
        index=pd.MultiIndex.from_tuples(
            list(rows), names=["scenario", "variable", "region", "unit"]
        ),
        columns=years,
    )


CMIP_CONCENTRATION_CASES = (
    pytest.param(
        run_concentration_driven_from_cmip7_pre_industrial,
        MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
        CMIP7_PRE_INDUSTRIAL,
        id="cmip7",
    ),
    pytest.param(
        run_concentration_driven_from_cmip6_pre_industrial,
        MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
        CMIP6_PRE_INDUSTRIAL,
        id="cmip6",
    ),
)


CMIP_CONCENTRATION_AND_CO2_CONCENTRATION_CASES = (
    *(
        pytest.param(*case.values, False, id=case.id)
        for case in CMIP_CONCENTRATION_CASES
    ),
    pytest.param(
        run_co2_concentration_driven_from_cmip7_pre_industrial,
        MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
        CMIP7_PRE_INDUSTRIAL,
        True,
        id="co2-cmip7",
    ),
    pytest.param(
        run_co2_concentration_driven_from_cmip6_pre_industrial,
        MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
        CMIP6_PRE_INDUSTRIAL,
        True,
        id="co2-cmip6",
    ),
)
"""Concentration-driven and CO2-concentration-driven cases (last value: `co2_only`)"""


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", CMIP_CONCENTRATION_CASES)
def test_cmip_concentration_driven_runs(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    results = run(
        concentrations=(make_concentrations(pre_industrial, co2_only=False),),
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()
    assert res.columns.min() == 1850

    for _, member in res.groupby("ensemble_member"):
        member_d = member.droplevel(["ensemble_member", "scenario", "region", "unit"])
        # Starts in equilibrium (1pctCO2 has piControl CO2 in 1850)
        is_erf = member_d.index.str.startswith("Effective Radiative Forcing")
        np.testing.assert_allclose(member_d.loc[is_erf, 1850], 0.0, atol=1e-12)
        # Solar and volcanic forcing are zero, as in the input
        # (i.e. MAGICC's historical natural forcing isn't used)
        # and aerosols etc. stay at piControl levels
        # (i.e. MAGICC's historical aerosol forcing isn't used)
        np.testing.assert_allclose(
            member_d.loc[
                [
                    "Effective Radiative Forcing|Solar",
                    "Effective Radiative Forcing|Volcanic",
                    *HELD_AT_PI_CONTROL_ERF_COMPONENTS,
                ]
            ],
            0.0,
            atol=1e-12,
        )
        # CO2 forcing and warming increase
        assert member_d.loc["Effective Radiative Forcing|CO2"].iloc[-1] > 5.0
        assert member_d.loc["Surface Air Temperature Change"].iloc[-1] > 1.0
        # The total includes more than the GHGs
        # (e.g. the ozone response to warming), but not much more
        np.testing.assert_allclose(
            member_d.loc["Effective Radiative Forcing"],
            member_d.loc[list(GHG_ERF_COMPONENTS)].sum(),
            atol=0.5,
        )


@pytest.mark.parametrize(
    "run, adapter_cls, pre_industrial, co2_only",
    CMIP_CONCENTRATION_AND_CO2_CONCENTRATION_CASES,
)
def test_cmip_pi_control_stays_at_zero(
    run: Callable[..., Any],
    adapter_cls: type,
    pre_industrial: PreIndustrialValues,
    co2_only: bool,
) -> None:
    """
    Everything at piControl means no forcing and no warming, ever (exactly)

    This works because MAGICC's pre-industrial state is the piControl state
    (`RF_PREIND_REFERENCEYR` is the start year, which holds piControl,
    with `RF_INITIALIZATION_METHOD = "JUMPSTART"`),
    see the adapter's module docstring.

    It didn't with `ZEROSTARTSHIFT` and MAGICC's default (1750) reference year,
    because of two quirks of MAGICC v7.5.3:

    - ozone forcing due to N2O isn't shifted to zero,
      so piControl N2O above the 1750 reference gave a constant forcing
      (~0.003 W/m^2 for CMIP7)
    - in MAGICC's first year, tropospheric ozone forcing isn't calculated,
      but the first-year offset is still subtracted,
      giving a one-year pulse of minus the piControl state's forcing
      relative to 1750 (~0.04 W/m^2), and a drift of ~0.002 K
      (~2e-5 K with a 100-year spin-up).

    If this test starts failing, check those first.
    """
    inp = make_concentrations(
        pre_industrial, co2_only=co2_only, co2_growth_rate=0.0, n_years=200
    )
    input_kwarg = "co2_concentrations" if co2_only else "concentrations"
    results = run(
        **{input_kwarg: (inp,)},
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()

    for variable, values in res.groupby("variable"):
        if str(variable).startswith("Atmospheric Concentrations"):
            # Concentrations are at piControl, not zero
            np.testing.assert_allclose(
                values.to_numpy(),
                np.broadcast_to(values.iloc[:, [0]].to_numpy(), values.shape),
                rtol=1e-6,
            )
        else:
            np.testing.assert_allclose(
                values.to_numpy(), 0.0, atol=1e-12, err_msg=str(variable)
            )


@pytest.mark.parametrize(
    "run, adapter_cls, all_ghg_run, all_ghg_adapter_cls, pre_industrial",
    (
        pytest.param(
            run_concentration_driven_from_cmip7_pre_industrial,
            MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
            run_esm_all_ghg_from_cmip7_pre_industrial,
            MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial,
            CMIP7_PRE_INDUSTRIAL,
            id="cmip7",
        ),
        pytest.param(
            run_concentration_driven_from_cmip6_pre_industrial,
            MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
            run_esm_all_ghg_from_cmip6_pre_industrial,
            MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial,
            CMIP6_PRE_INDUSTRIAL,
            id="cmip6",
        ),
    ),
)
def test_cmip_inputs_away_from_pi_control_in_the_first_year(
    run: Callable[..., Any],
    adapter_cls: type,
    all_ghg_run: Callable[..., Any],
    all_ghg_adapter_cls: type,
    pre_industrial: PreIndustrialValues,
) -> None:
    """
    Inputs which aren't at piControl in the first year cause a response then

    The piControl state is hard-coded in the adapters
    (it isn't taken from the input's first year),
    so inputs which differ from it in 1850 change the output from 1850.
    Emissions in 1850 change the state at the start of 1851
    (e.g. concentrations of emissions-driven gases).
    """
    configuration = MAGICCAR6AdapterConfiguration.from_environment(
        testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
    )
    inp = make_concentrations(
        pre_industrial, co2_only=False, co2_growth_rate=0.0, n_years=5
    )
    variables = inp.index.get_level_values("variable")
    inp.loc[variables == "Atmospheric Concentrations|CO2"] = 500.0
    inp.loc[variables == "Emissions|SOx"] *= 2.0
    inp.loc[variables == "Effective Radiative Forcing|Solar"] = 0.2

    results = run(
        concentrations=(inp,),
        adapters=(adapter_cls(configuration=configuration),),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()

    for variable, sign in (
        ("Effective Radiative Forcing|CO2", 1.0),
        ("Effective Radiative Forcing|Aerosols", -1.0),
        ("Effective Radiative Forcing|Solar", 1.0),
    ):
        first_year = res.xs(variable, level="variable")[1850]
        assert (sign * first_year > 0.001).all(), variable

    all_ghg_inp = make_emissions_driven_input(
        pre_industrial, all_ghg=True, n_years=5, ch4_factor=2.0
    )
    results = all_ghg_run(
        esm_all_ghg_inputs=(all_ghg_inp,),
        adapters=(all_ghg_adapter_cls(configuration=configuration),),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    ch4 = output.as_df().xs("Atmospheric Concentrations|CH4", level="variable")

    np.testing.assert_allclose(
        ch4[1850], pre_industrial.pi_control_concentrations["CH4"]
    )
    assert (ch4[1851] > pre_industrial.pi_control_concentrations["CH4"] + 1.0).all()


@pytest.mark.parametrize(
    "run, adapter_cls, pre_industrial, co2_only",
    CMIP_CONCENTRATION_AND_CO2_CONCENTRATION_CASES,
)
def test_cmip_abrupt_4xco2_has_forcing_from_the_first_year(
    run: Callable[..., Any],
    adapter_cls: type,
    pre_industrial: PreIndustrialValues,
    co2_only: bool,
) -> None:
    """
    Forcing is relative to piControl, not to the input's first year

    abrupt-4xCO2 is at 4 x piControl CO2 from 1850,
    so there has to be (roughly 4xCO2) forcing in 1850.
    (A naive MAGICC setup, starting in 1850 with `ZEROSTARTSHIFT`,
    shifts this to zero.)
    """
    inp = make_concentrations(
        pre_industrial, co2_only=co2_only, co2_growth_rate=0.0, n_years=20
    )
    co2_rows = (
        inp.index.get_level_values("variable") == "Atmospheric Concentrations|CO2"
    )
    inp.loc[co2_rows] *= 4

    input_kwarg = "co2_concentrations" if co2_only else "concentrations"
    results = run(
        **{input_kwarg: (inp,)},
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()
    co2_erf = res.xs("Effective Radiative Forcing|CO2", level="variable")

    assert ((co2_erf[1850] > 6.0) & (co2_erf[1850] < 10.0)).all()
    # Constant concentrations, so constant forcing
    np.testing.assert_allclose(co2_erf[1869], co2_erf[1850])


@pytest.mark.parametrize(
    "run, adapter_cls, pre_industrial, co2_only",
    CMIP_CONCENTRATION_AND_CO2_CONCENTRATION_CASES,
)
def test_cmip_1pct_co2_forcing_increases_linearly_from_zero(
    run: Callable[..., Any],
    adapter_cls: type,
    pre_industrial: PreIndustrialValues,
    co2_only: bool,
) -> None:
    """
    Exponentially increasing CO2 gives roughly linearly increasing CO2 forcing

    Starting from zero, because CO2 starts at its piControl value.
    It isn't exactly linear: MAGICC's CO2 forcing (`OLBL` method)
    increases a bit faster than logarithmically with concentration
    (by 1990, it is ~2.5% above a straight line for 1pctCO2).
    """
    inp = make_concentrations(pre_industrial, co2_only=co2_only, n_years=140)
    input_kwarg = "co2_concentrations" if co2_only else "concentrations"
    results = run(
        **{input_kwarg: (inp,)},
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()
    co2_erf = res.xs("Effective Radiative Forcing|CO2", level="variable")

    np.testing.assert_allclose(co2_erf[1850], 0.0, atol=1e-12)
    assert (co2_erf.diff(axis="columns").iloc[:, 1:] > 0.0).all().all()

    years = co2_erf.columns.to_numpy()
    for _, member in co2_erf.iterrows():
        straight_line = member.iloc[-1] * (years - years[0]) / (years[-1] - years[0])
        np.testing.assert_allclose(
            member.to_numpy(), straight_line, atol=0.05 * member.iloc[-1]
        )


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", CMIP_CONCENTRATION_CASES)
def test_cmip_natural_forcing_comes_from_the_input(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    n_years = 30
    solar = np.full(n_years, 0.2)
    volcanic = np.zeros(n_years)
    volcanic[10] = -2.0
    results = run(
        concentrations=(
            make_concentrations(
                pre_industrial,
                co2_only=False,
                co2_growth_rate=0.0,
                n_years=n_years,
                solar=solar,
                volcanic=volcanic,
            ),
        ),
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()

    for _, member in res.groupby("ensemble_member"):
        member_d = member.droplevel(["ensemble_member", "scenario", "region", "unit"])
        solar_erf = member_d.loc["Effective Radiative Forcing|Solar"]
        volcanic_erf = member_d.loc["Effective Radiative Forcing|Volcanic"]
        # Each member scales the input (and applies its efficacy),
        # so the output isn't the input, but it is proportional to it
        assert solar_erf[1855] > 0.0
        np.testing.assert_allclose(solar_erf.loc[1851:], solar_erf[1855])
        assert volcanic_erf[1860] < -0.5
        np.testing.assert_allclose(volcanic_erf.loc[1862:], 0.0, atol=1e-12)
        temperature = member_d.loc["Surface Air Temperature Change"]
        assert temperature[1861] < temperature[1859]


CMIP_DATA_DIR = TEST_DATA_DIR / "cmip-pre-industrial-branch"

CMIP_DATA_CASES = (
    pytest.param(
        CMIP_DATA_DIR / "cmip6-ssp245.csv",
        run_concentration_driven_from_cmip6_pre_industrial,
        MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
        CMIP6_PRE_INDUSTRIAL,
        id="cmip6-ssp245",
    ),
    pytest.param(
        CMIP_DATA_DIR / "cmip7-scen7-m.csv",
        run_concentration_driven_from_cmip7_pre_industrial,
        MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
        CMIP7_PRE_INDUSTRIAL,
        id="cmip7-scen7-m",
    ),
)
"""
Input data from RCMIP phase 3, 1850-2100, and what to run it with

CMIP6: SSP2-4.5 (history then scenario).
CMIP7: the CMIP7 M scenario (`scen7-M`, history then scenario),
except the emissions, which are the history (to 2023) held constant
(RCMIP phase 3 has no emissions for the CMIP7 scenarios).
"""

ERF_COMPONENTS = tuple(
    v
    for v in SUPPORTED_OUTPUT_VARIABLES
    if v.startswith("Effective Radiative Forcing|")
    and v != "Effective Radiative Forcing|Anthropogenic"
)
"""Forcing outputs which are components (not totals)"""

GHG_ERF_COMPONENTS_AND_CHEMISTRY = (
    *GHG_ERF_COMPONENTS,
    # Responds to CH4 (MAGICC has interactive chemistry, see decision B18)
    "Effective Radiative Forcing|Tropospheric Ozone",
    # Responds to the Montreal Protocol gases
    "Effective Radiative Forcing|Stratospheric Ozone",
)

SOME_INPUTS_CASES = (
    pytest.param(
        CMIP7_NATURAL_FORCING_VARIABLES,
        (
            "Effective Radiative Forcing|Solar",
            "Effective Radiative Forcing|Volcanic",
        ),
        id="natural",
    ),
    pytest.param(
        CMIP7_CONCENTRATION_VARIABLES, GHG_ERF_COMPONENTS_AND_CHEMISTRY, id="ghg"
    ),
    pytest.param(
        CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES,
        (
            "Effective Radiative Forcing|Aerosols",
            # Responds to the ozone precursors (CO, NMVOC, NOx)
            "Effective Radiative Forcing|Tropospheric Ozone",
        ),
        id="aerosol",
    ),
    pytest.param(
        frozenset({"Atmospheric Concentrations|CO2"}),
        ("Effective Radiative Forcing|CO2",),
        id="co2",
    ),
    pytest.param(
        frozenset({"Atmospheric Concentrations|CH4"}),
        (
            "Effective Radiative Forcing|CH4",
            # Responds to CH4
            "Effective Radiative Forcing|Tropospheric Ozone",
        ),
        id="ch4",
    ),
)
"""
Variables which follow the input data and the forcing components they change

The other components should stay at zero.
"""


@pytest.mark.parametrize("variables, changed_components", SOME_INPUTS_CASES)
@pytest.mark.parametrize("data_file, run, adapter_cls, pre_industrial", CMIP_DATA_CASES)
def test_cmip_only_some_inputs_change(  # noqa: PLR0913
    data_file: Path,
    run: Callable[..., Any],
    adapter_cls: type,
    pre_industrial: PreIndustrialValues,
    variables: frozenset[str],
    changed_components: tuple[str, ...],
) -> None:
    """
    Changing only some inputs only changes the forcing they drive

    Everything at piControl, except some inputs,
    which follow the input data
    (CMIP6: SSP2-4.5, CMIP7: the M scenario, see `CMIP_DATA_CASES`),
    e.g. like hist-nat (natural forcing), hist-GHG (GHG concentrations)
    and hist-aer (aerosol emissions).
    The forcing the other inputs drive stays at zero.
    MAGICC has interactive chemistry (see decision B18),
    so ozone forcing responds to e.g. CH4 too.
    The natural forcing is RCMIP phase 3's, which isn't zero in 1850,
    i.e. it isn't relative to piControl as the input definition says
    (what zero means for natural forcing is still to be decided,
    see decision B19).
    """
    data = pd.read_csv(data_file).set_index(["scenario", "variable", "region", "unit"])
    data.columns = data.columns.astype(int)
    pi_control = make_concentrations(
        pre_industrial,
        co2_only=False,
        co2_growth_rate=0.0,
        n_years=data.shape[1],
    )
    inp = pd.concat(
        [
            pi_control.loc[
                ~pi_control.index.get_level_values("variable").isin(variables)
            ],
            data.loc[data.index.get_level_values("variable").isin(variables)].rename(
                lambda _: pi_control.index[0][0], level="scenario"
            ),
        ]
    )

    results = run(
        concentrations=(inp,),
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()

    for component in ERF_COMPONENTS:
        values = res.xs(component, level="variable")
        if component in changed_components:
            assert (values.abs().max(axis="columns") > 0.001).all(), component
        else:
            np.testing.assert_allclose(
                values.to_numpy(), 0.0, atol=1e-12, err_msg=component
            )

    temperature = res.xs("Surface Air Temperature Change", level="variable")
    assert (temperature.abs().max(axis="columns") > 0.01).all()

    if variables == CMIP7_NATURAL_FORCING_VARIABLES:
        check_natural_forcing_follows_input(inp, res)


def check_natural_forcing_follows_input(inp: pd.DataFrame, res: pd.DataFrame) -> None:
    """
    Check the output natural forcing is (proportional to) the input

    Each member scales the input (and applies its efficacy),
    so the output isn't the input, but it is proportional to it.
    MAGICC's annual volcanic forcing is an "end-of-year forcing"
    (the mean of the 12 months centred on the end of the year,
    `src/MAGICC7.f90` in MAGICC v7.5.3, around line 8538),
    so with annual input (which the adapter writes into each month),
    the output in year `t` is proportional to
    the mean of the input in years `t` and `t + 1`.
    The forcing which drives the climate is the monthly forcing.
    """
    solar = inp.xs("Effective Radiative Forcing|Solar", level="variable").iloc[0]
    volcanic = inp.xs("Effective Radiative Forcing|Volcanic", level="variable").iloc[0]
    end_of_year_volcanic = (volcanic + volcanic.shift(-1)) / 2.0
    for variable, expected_shape in (
        ("Effective Radiative Forcing|Solar", solar),
        ("Effective Radiative Forcing|Volcanic", end_of_year_volcanic.iloc[:-1]),
    ):
        for _, member in res.xs(variable, level="variable").iterrows():
            ratio = (member / expected_shape).loc[expected_shape.index]
            ratio = ratio[expected_shape.abs() > 0.001]
            np.testing.assert_allclose(ratio, ratio.iloc[0], err_msg=variable)


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", CMIP_CONCENTRATION_CASES)
def test_cmip_ozone_responds_to_methane(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """MAGICC's ozone forcing comes through (calculated from the concentrations)"""
    results = run(
        concentrations=(
            make_concentrations(
                pre_industrial,
                co2_only=False,
                co2_growth_rate=0.0,
                ch4_growth_rate=0.01,
                n_years=50,
            ),
        ),
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()
    tropospheric_ozone = res.xs(
        "Effective Radiative Forcing|Tropospheric Ozone", level="variable"
    )

    assert (tropospheric_ozone.iloc[:, -1] > 0.05).all()


@pytest.mark.xfail(
    reason=(
        "The CO2-only adapters turn off MAGICC's ozone forcing due to temperature, "
        "the full concentration-driven adapters don't "
        "(see `NO_OZONE_DUE_TO_TEMPERATURE` and decisions B16 and B18)"
    ),
    raises=AssertionError,
    strict=True,
)
@pytest.mark.parametrize(
    "co2_run, co2_adapter_cls, run, adapter_cls, pre_industrial",
    (
        pytest.param(
            run_co2_concentration_driven_from_cmip7_pre_industrial,
            MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP7PreIndustrial,
            run_concentration_driven_from_cmip7_pre_industrial,
            MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial,
            CMIP7_PRE_INDUSTRIAL,
            id="cmip7",
        ),
        pytest.param(
            run_co2_concentration_driven_from_cmip6_pre_industrial,
            MAGICCAR6AdapterCO2ConcentrationDrivenFromCMIP6PreIndustrial,
            run_concentration_driven_from_cmip6_pre_industrial,
            MAGICCAR6AdapterConcentrationDrivenFromCMIP6PreIndustrial,
            CMIP6_PRE_INDUSTRIAL,
            id="cmip6",
        ),
    ),
)
def test_cmip_co2_only_matches_full_input_at_pi_control(
    co2_run: Callable[..., Any],
    co2_adapter_cls: type,
    run: Callable[..., Any],
    adapter_cls: type,
    pre_industrial: PreIndustrialValues,
) -> None:
    """
    CO2-only input is the same as full input with everything else at piControl
    """
    co2_only_results = co2_run(
        co2_concentrations=(
            make_concentrations(pre_industrial, co2_only=True, n_years=50),
        ),
        adapters=(
            co2_adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    co2_only_results.raise_if_any_failed()
    (co2_only_output,) = co2_only_results[0].outputs
    co2_only_output.raise_if_any_failed()
    co2_only = co2_only_output.as_df()

    full_results = run(
        concentrations=(
            make_concentrations(pre_industrial, co2_only=False, n_years=50),
        ),
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    full_results.raise_if_any_failed()
    (full_output,) = full_results[0].outputs
    full_output.raise_if_any_failed()
    full = full_output.as_df()

    pd.testing.assert_frame_equal(co2_only, full)
    assert (
        co2_only.xs("Effective Radiative Forcing|CO2", level="variable").iloc[:, -1]
        > 1.0
    ).all()


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", CMIP_CONCENTRATION_CASES)
def test_cmip_ozone_responds_to_emissions(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """Tropospheric ozone forcing responds to CO and NMVOC emissions"""
    results = run(
        concentrations=(
            make_concentrations(
                pre_industrial,
                co2_only=False,
                co2_growth_rate=0.0,
                n_years=50,
                emissions_growth_rates={"Emissions|CO": 0.03, "Emissions|NMVOC": 0.03},
            ),
        ),
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()
    tropospheric_ozone = res.xs(
        "Effective Radiative Forcing|Tropospheric Ozone", level="variable"
    )
    aerosols = res.xs("Effective Radiative Forcing|Aerosols", level="variable")

    assert (tropospheric_ozone.iloc[:, -1] > 0.02).all()
    # Aerosols don't care about CO or NMVOC
    np.testing.assert_allclose(aerosols.to_numpy(), 0.0, atol=1e-12)


def run_aerosol_growth(
    growth_rates: dict[str, float], n_years: int = 30
) -> pd.DataFrame:
    """Run with aerosol emissions growing, returning the aerosol ERF"""
    results = run_concentration_driven_from_cmip7_pre_industrial(
        concentrations=(
            make_concentrations(
                CMIP7_PRE_INDUSTRIAL,
                co2_only=False,
                co2_growth_rate=0.0,
                n_years=n_years,
                emissions_growth_rates=growth_rates,
            ),
        ),
        adapters=(
            MAGICCAR6AdapterConcentrationDrivenFromCMIP7PreIndustrial(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    (output,) = results[0].outputs
    output.raise_if_any_failed()
    res = output.as_df()

    return res.xs("Effective Radiative Forcing|Aerosols", level="variable")


@pytest.mark.parametrize(
    "variable, sign",
    (
        pytest.param("Emissions|SOx", -1.0, id="SOx"),
        pytest.param("Emissions|OC", -1.0, id="OC"),
        pytest.param("Emissions|NOx", -1.0, id="NOx"),
        pytest.param("Emissions|NH3", -1.0, id="NH3"),
        pytest.param("Emissions|BC", 1.0, id="BC"),
    ),
)
def test_cmip_aerosol_forcing_responds_to_emissions(variable: str, sign: float) -> None:
    """
    Aerosol forcing responds to emissions

    See the module docstring of
    `openscm_runner.adapters.magicc_ar6.cmip_pre_industrial_branch`.
    """
    aerosols = run_aerosol_growth({variable: 0.05})

    # Emissions are ~4 times piControl by the end, so a clear response
    assert (sign * aerosols.iloc[:, -1] > 0.005).all()
    # Small at the start (not zero: MAGICC uses the average of each year's
    # and the next year's emissions, so 1850 sees half of the increase in 1851)
    assert (aerosols[1850].abs() < 0.05 * aerosols.iloc[:, -1].abs()).all()


def test_cmip_aerosol_cloud_forcing_scales_with_emissions() -> None:
    """
    More emissions, more aerosol forcing

    Without the normalisation anchor (see the module docstring),
    MAGICC v7.5.3's aerosol-cloud forcing always reaches the same value
    in the last year, whatever the emissions.
    """
    small = run_aerosol_growth({"Emissions|SOx": 0.02})
    large = run_aerosol_growth({"Emissions|SOx": 0.05})

    assert (large.iloc[:, -1] < 1.5 * small.iloc[:, -1]).all()


def test_emissions_driven_files_reproduce_history_in_1850() -> None:
    """
    Fed MAGICC's own historical emissions, the derived files match its history

    Exactly in 1850 (the pattern year), approximately in 1851
    (except for the biomass burning files, see below).
    """
    installation = MAGICCAR6AdapterConfiguration.from_environment(
        testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
    ).installation
    historical_emissions = load_historical_emissions(installation).droplevel("unit")
    defaults = read_namelist(installation.run_dir / "MAGCFG_DEFAULTALL.CFG")[
        "nml_allcfgs"
    ]

    for edf in derive_emissions_driven_files(installation):
        if edf.cumulative:
            # Tested separately below
            continue

        res = edf.values(historical_emissions.loc[:, 1840:1870])
        history, _ = read_tabular_file(installation.run_dir / defaults[edf.setting])

        np.testing.assert_allclose(
            res[1850].to_numpy(), history[1850].to_numpy(), err_msg=edf.setting
        )
        if EMISSIONS_DRIVEN_FILE_RULES[edf.setting][1] != "delta":
            # MAGICC's biomass burning history isn't smooth in its emissions
            # (which is why MAGICC uses the "delta" rule for these),
            # so we only check the others
            np.testing.assert_allclose(
                res[1851].to_numpy(),
                history[1851].to_numpy(),
                atol=0.05,
                err_msg=edf.setting,
            )


def test_halogen_order_matches_magicc() -> None:
    """
    Our F-gas and Montreal Protocol gas order is MAGICC's own

    We don't tell MAGICC the order, so it has to match its defaults.
    """
    defaults = read_namelist(
        MAGICCAR6AdapterConfiguration.from_environment(
            testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
        ).installation.run_dir
        / "MAGCFG_DEFAULTALL.CFG"
    )["nml_allcfgs"]

    assert tuple(defaults["fgas_names"]) == FGAS_NAMES
    assert tuple(defaults["mhalo_names"]) == MHALO_NAMES


def test_cumulative_emissions_driven_files() -> None:
    """
    Land use and mineral dust respond to cumulative biosphere CO2 emissions

    With zero emissions (piControl) they stay at their 1850 values.
    """
    installation = MAGICCAR6AdapterConfiguration.from_environment(
        testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
    ).installation
    cumulative_files = [
        edf for edf in derive_emissions_driven_files(installation) if edf.cumulative
    ]
    assert {edf.setting for edf in cumulative_files} == {
        "file_landuse_rf",
        "file_mineraldust_rf",
    }

    years = range(1830, 1900)
    for edf in cumulative_files:
        zero = edf.values(pd.DataFrame({y: [0.0] for y in years}, index=["CO2B"]))
        np.testing.assert_allclose(
            zero.to_numpy(),
            np.broadcast_to(np.array(edf.reference_values)[:, np.newaxis], zero.shape),
        )

        # 1 GtC/yr from 1850
        res = edf.values(
            pd.DataFrame({y: [float(y >= 1850)] for y in years}, index=["CO2B"])
        )
        # Mid-year convention: 1860 sees the average of 11 and 12 GtC
        np.testing.assert_allclose(
            res[1860].to_numpy(),
            np.array(edf.reference_values) + np.array(edf.sensitivities) * 11.5,
        )


def test_history_files_need_a_value_in_the_first_year() -> None:
    """The held files hold the installation's value in the first year"""
    installation = MAGICCAR6AdapterConfiguration.from_environment(
        testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
    ).installation

    # MAGICC's history files don't go back this far
    with pytest.raises(ValueError, match="has no value for 1000"):
        make_history_files(
            installation,
            (),
            emissions=pd.DataFrame(),
            first_year=1000,
            last_year=1900,
            anchor_years=(),
        )


def test_emissions_driven_files_can_be_given() -> None:
    """Giving the default emissions-driven files explicitly changes nothing"""
    configuration = MAGICCAR6AdapterConfiguration.from_environment(
        testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
    )
    inp = make_concentrations(
        CMIP7_PRE_INDUSTRIAL,
        co2_only=False,
        co2_growth_rate=0.0,
        n_years=30,
        emissions_growth_rates={"Emissions|SOx": 0.05},
    )

    res = {}
    for name, emissions_driven_files in (
        ("default", None),
        ("given", derive_emissions_driven_files(configuration.installation)),
    ):
        (output,) = run_pre_industrial_branch_experiments(
            (inp,),
            CMIP_OUTPUTS,
            configuration=configuration,
            pre_industrial=CMIP7_PRE_INDUSTRIAL,
            emissions_driven_files=emissions_driven_files,
        )
        output.raise_if_any_failed()
        res[name] = output.as_df()

    # The emissions change the aerosol forcing, so the files are used
    aerosols = res["default"].xs(
        "Effective Radiative Forcing|Aerosols", level="variable"
    )
    assert (aerosols.iloc[:, -1] < -0.005).all()
    pd.testing.assert_frame_equal(res["given"], res["default"])


def make_emissions_driven_input(  # noqa: PLR0913
    pre_industrial: PreIndustrialValues,
    *,
    all_ghg: bool,
    n_years: int,
    co2_fossil: float | np.ndarray[Any, Any] = 0.0,
    co2_biosphere: float | np.ndarray[Any, Any] = 0.0,
    ch4_factor: float | np.ndarray[Any, Any] = 1.0,
) -> pd.DataFrame:
    """
    Make esm-style (or esm-allGHG-style) input

    Everything at piControl except what is given.
    For esm-allGHG-style input, the piControl GHG emissions
    are MAGICC's own historical emissions in 1850.

    Parameters
    ----------
    pre_industrial
        Pre-industrial values to start from

    all_ghg
        Make esm-allGHG-style input (else esm-style)

    n_years
        Number of years

    co2_fossil
        Fossil CO2 emissions (GtC/yr)

    co2_biosphere
        Biosphere CO2 emissions (GtC/yr)

    ch4_factor
        Factor applied to piControl CH4 emissions (only used if `all_ghg`)
    """
    years = list(range(1850, 1850 + n_years))
    rows: dict[tuple[str, str, str, str], Any] = {}

    def add(variable: str, unit: str, values: Any) -> None:
        rows[("esm", variable, "World", unit)] = np.broadcast_to(values, n_years)

    add("Emissions|CO2|Fossil", "Gt C/yr", co2_fossil)
    add("Emissions|CO2|Biosphere", "Gt C/yr", co2_biosphere)

    if all_ghg:
        for variable in sorted(
            CMIP7_GHG_EMISSION_VARIABLES - CMIP7_CO2_ESM_EMISSION_VARIABLES
        ):
            unit, value = get_pi_control_emissions(pre_industrial, variable)
            if variable == "Emissions|CH4":
                value = value * ch4_factor

            add(variable, unit, value)

    else:
        for variable in CMIP7_CONCENTRATION_VARIABLES:
            if variable == "Atmospheric Concentrations|CO2":
                continue

            gas = to_magicc_gas(variable.split("|")[1])
            add(
                variable,
                CONCENTRATION_UNITS[gas],
                pre_industrial.pi_control_concentrations[gas],
            )

    for variable in (
        "Effective Radiative Forcing|Solar",
        "Effective Radiative Forcing|Volcanic",
    ):
        add(variable, "W/m^2", 0.0)

    for variable in sorted(CMIP7_AEROSOL_OZONE_PRECURSOR_EMISSIONS_VARIABLES):
        add(variable, *get_pi_control_emissions(pre_industrial, variable))

    return pd.DataFrame(
        list(rows.values()),
        index=pd.MultiIndex.from_tuples(
            list(rows), names=["scenario", "variable", "region", "unit"]
        ),
        columns=years,
    )


def run_emissions_driven(
    run: Callable[..., Any], adapter_cls: type, kwarg: str, inp: pd.DataFrame
) -> pd.DataFrame:
    """Run one emissions-driven experiment, returning the output as a dataframe"""
    results = run(
        **{kwarg: (inp,)},
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    (output,) = results[0].outputs

    return output.as_df()


ESM_CASES = (
    pytest.param(
        run_esm_from_cmip7_pre_industrial,
        MAGICCAR6AdapterESMFromCMIP7PreIndustrial,
        CMIP7_PRE_INDUSTRIAL,
        id="cmip7",
    ),
    pytest.param(
        run_esm_from_cmip6_pre_industrial,
        MAGICCAR6AdapterESMFromCMIP6PreIndustrial,
        CMIP6_PRE_INDUSTRIAL,
        id="cmip6",
    ),
)

ESM_ALL_GHG_CASES = (
    pytest.param(
        run_esm_all_ghg_from_cmip7_pre_industrial,
        MAGICCAR6AdapterESMAllGHGFromCMIP7PreIndustrial,
        CMIP7_PRE_INDUSTRIAL,
        id="cmip7",
    ),
    pytest.param(
        run_esm_all_ghg_from_cmip6_pre_industrial,
        MAGICCAR6AdapterESMAllGHGFromCMIP6PreIndustrial,
        CMIP6_PRE_INDUSTRIAL,
        id="cmip6",
    ),
)

CO2_EMISSION_CASES = (
    pytest.param(
        run_co2_emission_driven_from_cmip7_pre_industrial,
        MAGICCAR6AdapterCO2EmissionDrivenFromCMIP7PreIndustrial,
        CMIP7_PRE_INDUSTRIAL,
        id="cmip7",
    ),
    pytest.param(
        run_co2_emission_driven_from_cmip6_pre_industrial,
        MAGICCAR6AdapterCO2EmissionDrivenFromCMIP6PreIndustrial,
        CMIP6_PRE_INDUSTRIAL,
        id="cmip6",
    ),
)


def make_co2_emissions(co2_fossil: float, n_years: int) -> pd.DataFrame:
    return pd.DataFrame(
        [np.full(n_years, co2_fossil)],
        index=pd.MultiIndex.from_tuples(
            [("esm-flat10", "Emissions|CO2|Fossil", "World", "Gt C/yr")],
            names=["scenario", "variable", "region", "unit"],
        ),
        columns=range(1850, 1850 + n_years),
    )


def check_stays_near_pi_control(
    res: pd.DataFrame, pre_industrial: PreIndustrialValues
) -> None:
    """
    Check an emissions-driven piControl stays (close to) piControl

    Not exactly: e.g. MAGICC's piControl halogen emissions
    aren't quite in balance with its lifetimes,
    and the carbon cycle drifts a little (tenths of a ppm over 150 years).
    """
    for gas, atol in (("CO2", 0.5), ("CH4", 1.0), ("N2O", 0.1)):
        np.testing.assert_allclose(
            res.xs(f"Atmospheric Concentrations|{gas}", level="variable").to_numpy(),
            pre_industrial.pi_control_concentrations[gas],
            atol=atol,
            err_msg=gas,
        )

    np.testing.assert_allclose(
        res.xs("Surface Air Temperature Change", level="variable").to_numpy(),
        0.0,
        atol=0.02,
    )


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", CO2_EMISSION_CASES)
def test_co2_emission_driven_pi_control(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    res = run_emissions_driven(
        run, adapter_cls, "co2_emissions", make_co2_emissions(0.0, 150)
    )
    check_stays_near_pi_control(res, pre_industrial)


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", CO2_EMISSION_CASES)
def test_co2_emission_driven_pre_industrial_emissions(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """
    Constant pre-industrial CO2 emissions only cause CO2-induced change

    The adapter uses zero piControl CO2 emissions
    (see `test_co2_emission_driven_pi_control` and decision B19),
    but historical CO2 emissions in 1850 aren't
    (we use the CMIP era's historical fossil CO2 emissions in 1850,
    ~0.05 GtC/yr, see `PreIndustrialValues.pi_control_emissions`).
    So the model is out of equilibrium: CO2 increases and causes warming,
    while every other species stays at piControl
    and its forcing is zero (forcing from CO2 isn't).
    """
    res = run_emissions_driven(
        run,
        adapter_cls,
        "co2_emissions",
        make_co2_emissions(
            get_pi_control_emissions_in_unit(pre_industrial, "CO2I", "Gt C/yr"), 150
        ),
    )

    for gas in ("CH4", "N2O"):
        np.testing.assert_allclose(
            res.xs(f"Atmospheric Concentrations|{gas}", level="variable").to_numpy(),
            pre_industrial.pi_control_concentrations[gas],
            rtol=1e-6,
            err_msg=gas,
        )

    co2 = res.xs("Atmospheric Concentrations|CO2", level="variable")
    assert (co2.iloc[:, -1] > co2.iloc[:, 0] + 0.5).all()

    co2_erf = res.xs("Effective Radiative Forcing|CO2", level="variable")
    np.testing.assert_allclose(co2_erf[1850], 0.0, atol=1e-12)
    assert (co2_erf.iloc[:, -1] > 0.01).all()
    totals = (
        "Effective Radiative Forcing",
        "Effective Radiative Forcing|Anthropogenic",
    )
    for variable in totals:
        np.testing.assert_allclose(
            res.xs(variable, level="variable").to_numpy(),
            co2_erf.to_numpy(),
            rtol=1e-10,
            atol=1e-12,
            err_msg=variable,
        )

    # Every other forcing component is zero
    for variable, values in res.groupby("variable"):
        if not str(variable).startswith("Effective Radiative Forcing") or variable in (
            *totals,
            "Effective Radiative Forcing|CO2",
        ):
            continue

        np.testing.assert_allclose(
            values.to_numpy(), 0.0, atol=1e-12, err_msg=str(variable)
        )

    temperature = res.xs("Surface Air Temperature Change", level="variable")
    assert (temperature.iloc[:, -1] > 0.0).all()


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", CO2_EMISSION_CASES)
def test_co2_emission_driven_flat10(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """esm-flat10: 10 GtC/yr for 100 years, i.e. 1000 GtC"""
    res = run_emissions_driven(
        run, adapter_cls, "co2_emissions", make_co2_emissions(10.0, 100)
    )
    co2 = res.xs("Atmospheric Concentrations|CO2", level="variable")
    temperature = res.xs("Surface Air Temperature Change", level="variable")

    assert (
        co2.iloc[:, -1] > pre_industrial.pi_control_concentrations["CO2"] + 150
    ).all()
    # A TCRE-ish amount of warming (roughly 1-2.5 K per 1000 GtC,
    # more for the most sensitive members:
    # 3.6 K for the second member, without ozone forcing due to temperature)
    assert ((temperature.iloc[:, -1] > 0.8) & (temperature.iloc[:, -1] < 4.0)).all()


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", ESM_CASES)
def test_esm_pi_control(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    res = run_emissions_driven(
        run,
        adapter_cls,
        "esm_inputs",
        make_emissions_driven_input(pre_industrial, all_ghg=False, n_years=150),
    )
    check_stays_near_pi_control(res, pre_industrial)


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", ESM_CASES)
def test_esm_land_use_responds_to_biosphere_emissions(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """Land-use change: CO2 goes up and the land-use (albedo) forcing goes down"""
    res = run_emissions_driven(
        run,
        adapter_cls,
        "esm_inputs",
        make_emissions_driven_input(
            pre_industrial, all_ghg=False, n_years=100, co2_biosphere=1.0
        ),
    )
    co2 = res.xs("Atmospheric Concentrations|CO2", level="variable")
    land_use = res.xs("Effective Radiative Forcing|Land-use Change", level="variable")

    # 100 GtC, a good part of which the land and ocean take up
    assert (co2.iloc[:, -1] > pre_industrial.pi_control_concentrations["CO2"] + 5).all()
    assert (land_use.iloc[:, -1] < -0.01).all()


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", ESM_CASES)
def test_esm_pre_industrial_emissions(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """
    Constant pre-industrial CO2 emissions only cause CO2-induced change

    As for `test_co2_emission_driven_pre_industrial_emissions`,
    with the CMIP era's historical biosphere CO2 emissions in 1850 too.
    The only species out of equilibrium is CO2,
    so the only non-zero forcing is CO2 forcing
    and the forcing MAGICC derives from cumulative biosphere CO2 emissions:
    land-use (albedo) forcing and mineral dust forcing
    (part of aerosol forcing, `src/MAGICC7.f90` in MAGICC v7.5.3,
    around lines 4976 and 5005).
    Both are expected with this set up.
    The mineral dust forcing drift could be avoided
    by prescribing zero biosphere CO2 emissions instead
    (whether that makes sense depends on what we use as pre-industrial,
    see decision B19).
    """
    res = run_emissions_driven(
        run,
        adapter_cls,
        "esm_inputs",
        make_emissions_driven_input(
            pre_industrial,
            all_ghg=False,
            n_years=150,
            co2_fossil=get_pi_control_emissions_in_unit(
                pre_industrial, "CO2I", "Gt C/yr"
            ),
            co2_biosphere=get_pi_control_emissions_in_unit(
                pre_industrial, "CO2B", "Gt C/yr"
            ),
        ),
    )

    for gas in ("CH4", "N2O"):
        np.testing.assert_allclose(
            res.xs(f"Atmospheric Concentrations|{gas}", level="variable").to_numpy(),
            pre_industrial.pi_control_concentrations[gas],
            rtol=1e-6,
            err_msg=gas,
        )

    co2 = res.xs("Atmospheric Concentrations|CO2", level="variable")
    assert (co2.iloc[:, -1] > co2.iloc[:, 0] + 1.0).all()

    out_of_equilibrium = (
        "Effective Radiative Forcing|CO2",
        "Effective Radiative Forcing|Land-use Change",
        "Effective Radiative Forcing|Aerosols",
    )
    for variable in out_of_equilibrium:
        values = res.xs(variable, level="variable")
        assert (values.iloc[:, -1].abs() > 0.001).all(), variable

    # CO2 starts at its piControl concentration
    # (land-use and mineral dust forcing respond to the biosphere emissions
    # from the first year)
    np.testing.assert_allclose(
        res.xs("Effective Radiative Forcing|CO2", level="variable")[1850],
        0.0,
        atol=1e-12,
    )

    # Every other forcing component is zero
    # (the totals aren't checked: they include MAGICC's ozone forcing
    # due to temperature, see `NO_OZONE_DUE_TO_TEMPERATURE`)
    for variable, values in res.groupby("variable"):
        if not str(variable).startswith("Effective Radiative Forcing|") or variable in (
            *out_of_equilibrium,
            "Effective Radiative Forcing|Anthropogenic",
        ):
            continue

        np.testing.assert_allclose(
            values.to_numpy(), 0.0, atol=1e-12, err_msg=str(variable)
        )


ESM_AND_ESM_ALL_GHG_CASES = (
    *(
        pytest.param(*case.values, False, "esm_inputs", id=f"esm-{case.id}")
        for case in ESM_CASES
    ),
    *(
        pytest.param(
            *case.values, True, "esm_all_ghg_inputs", id=f"esm-all-ghg-{case.id}"
        )
        for case in ESM_ALL_GHG_CASES
    ),
)
"""esm-style and esm-allGHG-style cases (with `all_ghg` and the input argument name)"""


@pytest.mark.parametrize(
    "run, adapter_cls, pre_industrial, all_ghg, input_kwarg", ESM_AND_ESM_ALL_GHG_CASES
)
def test_esm_single_year_aerosol_emissions_change(
    run: Callable[..., Any],
    adapter_cls: type,
    pre_industrial: PreIndustrialValues,
    all_ghg: bool,
    input_kwarg: str,
) -> None:
    """
    Changing aerosol emissions in a single year only changes aerosol forcing then

    In two years (the year before and the year of the change),
    because of MAGICC's emissions averaging:
    its aerosol forcing at the start of year `t` is calculated
    from the average of the emissions in years `t` and `t + 1`
    (see `MAGICCAR6AdapterAR6Scenario`).
    Total forcing changes in later years too, through temperature feedbacks.
    Heat uptake changes in the year before those too:
    sub-annual forcing is linearly interpolated,
    so the forcing over year `y - 2` is the interpolation
    of the `y - 2` and `y - 1` values,
    and the `y - 1` value changes because of the emissions averaging.
    """
    n_years = 2023 - 1850 + 1
    base = make_emissions_driven_input(pre_industrial, all_ghg=all_ghg, n_years=n_years)
    sox = next(i for i in base.index if i[1] == "Emissions|SOx")
    # Rising SOx emissions, roughly reaching present-day levels
    base.loc[sox] = base.loc[sox].to_numpy() * 1.02 ** np.arange(n_years)

    change_years = (2005, 2010, 2015, 2019)
    inputs = [base]
    for year in change_years:
        changed = base.rename(lambda _, year=year: f"sox-{year}", level="scenario")
        changed.loc[(f"sox-{year}", *sox[1:]), year] *= 1.5
        inputs.append(changed)

    results = run(
        **{input_kwarg: tuple(inputs)},
        adapters=(
            adapter_cls(
                configuration=MAGICCAR6AdapterConfiguration.from_environment(
                    testing_only_n_members=N_MEMBERS, n_workers=N_WORKERS
                )
            ),
        ),
        output_specs=CMIP_OUTPUTS,
    )
    results.raise_if_any_failed()
    for output in results[0].outputs:
        output.raise_if_any_failed()

    base_res, *changed_res = (
        output.as_df().droplevel("scenario") for output in results[0].outputs
    )
    for year, res in zip(change_years, changed_res, strict=True):
        difference = res - base_res
        aerosols = difference.xs(
            "Effective Radiative Forcing|Aerosols", level="variable"
        )
        affected = [year - 1, year]

        # More SOx, more negative aerosol forcing, but only in those years
        assert (aerosols[affected] < -0.001).all().all(), year
        np.testing.assert_allclose(
            aerosols.drop(columns=affected).to_numpy(), 0.0, atol=1e-12, err_msg=year
        )
        # Nothing changes before (heat uptake one year earlier, see above)
        is_heat_uptake = difference.index.get_level_values("variable") == "Heat Uptake"
        np.testing.assert_allclose(
            difference.loc[~is_heat_uptake, : year - 2].to_numpy(),
            0.0,
            atol=1e-12,
            err_msg=year,
        )
        np.testing.assert_allclose(
            difference.loc[is_heat_uptake, : year - 3].to_numpy(),
            0.0,
            atol=1e-12,
            err_msg=year,
        )


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", ESM_ALL_GHG_CASES)
def test_esm_all_ghg_pre_industrial_emissions(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """
    Constant pre-industrial emissions: only species out of equilibrium force

    As for `test_esm_pre_industrial_emissions`,
    with every GHG emissions-driven (at its piControl emissions).
    CO2 is out of equilibrium (so are land-use and mineral dust forcing,
    which MAGICC derives from cumulative biosphere CO2 emissions).
    Some forcing is small but not zero:

    - CH4 and N2O (and tropospheric ozone, which responds to CH4):
      their lifetimes respond to the warming
    - Montreal Protocol gases, F-gases and stratospheric ozone:
      the piControl emissions of some halogenated gases
      (the CMIP era's 1850 historical emissions)
      aren't quite in balance with MAGICC's lifetimes,
      so their concentrations drift (see decision B19)
    """
    res = run_emissions_driven(
        run,
        adapter_cls,
        "esm_all_ghg_inputs",
        make_emissions_driven_input(
            pre_industrial,
            all_ghg=True,
            n_years=150,
            co2_fossil=get_pi_control_emissions_in_unit(
                pre_industrial, "CO2I", "Gt C/yr"
            ),
            co2_biosphere=get_pi_control_emissions_in_unit(
                pre_industrial, "CO2B", "Gt C/yr"
            ),
        ),
    )

    out_of_equilibrium = (
        "Effective Radiative Forcing|CO2",
        "Effective Radiative Forcing|Land-use Change",
        "Effective Radiative Forcing|Aerosols",
    )
    small = (
        "Effective Radiative Forcing|CH4",
        "Effective Radiative Forcing|N2O",
        "Effective Radiative Forcing|Tropospheric Ozone",
        "Effective Radiative Forcing|Montreal Protocol Halogen Gases",
        "Effective Radiative Forcing|F-Gases",
        "Effective Radiative Forcing|Stratospheric Ozone",
    )
    for component in ERF_COMPONENTS:
        values = res.xs(component, level="variable")
        if component in out_of_equilibrium:
            assert (values.iloc[:, -1].abs() > 0.001).all(), component
        elif component in small:
            assert (values.abs() < 0.005).all().all(), component
        else:
            np.testing.assert_allclose(
                values.to_numpy(), 0.0, atol=1e-12, err_msg=component
            )


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", ESM_ALL_GHG_CASES)
def test_esm_all_ghg_pi_control(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    res = run_emissions_driven(
        run,
        adapter_cls,
        "esm_all_ghg_inputs",
        make_emissions_driven_input(pre_industrial, all_ghg=True, n_years=150),
    )
    check_stays_near_pi_control(res, pre_industrial)


@pytest.mark.parametrize("run, adapter_cls, pre_industrial", ESM_ALL_GHG_CASES)
def test_esm_all_ghg_ch4_emissions(
    run: Callable[..., Any], adapter_cls: type, pre_industrial: PreIndustrialValues
) -> None:
    """Doubling CH4 emissions raises CH4 concentrations (and nothing else much)"""
    n_years = 60
    ch4_factor = np.ones(n_years)
    ch4_factor[1:] = 2.0
    res = run_emissions_driven(
        run,
        adapter_cls,
        "esm_all_ghg_inputs",
        make_emissions_driven_input(
            pre_industrial, all_ghg=True, n_years=n_years, ch4_factor=ch4_factor
        ),
    )
    ch4 = res.xs("Atmospheric Concentrations|CH4", level="variable")
    n2o = res.xs("Atmospheric Concentrations|N2O", level="variable")

    pi_ch4 = pre_industrial.pi_control_concentrations["CH4"]
    # Doubling the piControl anthropogenic emissions
    # (the natural emissions are much bigger)
    assert (ch4.iloc[:, -1] > 1.2 * pi_ch4).all()
    np.testing.assert_allclose(
        n2o.to_numpy(), pre_industrial.pi_control_concentrations["N2O"], atol=0.1
    )
