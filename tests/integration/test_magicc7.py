import os.path
from pathlib import Path

import pandas as pd
import pymagicc.io
import pytest
from scmdata import ScmRun

import openscm_runner.run
from openscm_runner import RunMode
from openscm_runner.adapters import MAGICC7
from openscm_runner.testing import _AdapterTester
from openscm_runner.utils import calculate_quantiles

RCMIP3_MINI_BUNDLE = (
    Path(__file__).parent.parent / "test-data" / "rcmip3-mini"
)
# Variant bundle that also ships a few F-gas / Montreal-halocarbon ssp245
# concentration trajectories, for exercising the bundled-array path.
RCMIP3_MINI_HALO_BUNDLE = (
    Path(__file__).parent.parent / "test-data" / "rcmip3-mini-halo"
)


@pytest.mark.magicc
class TestMagicc7Adapter(_AdapterTester):
    def test_run(
        self,
        test_scenarios,
        num_regression,
    ):
        res = openscm_runner.run.run(
            climate_models_cfgs={
                "MAGICC7": [
                    {
                        "core_climatesensitivity": 3,
                        "rf_soxi_dir_wm2": -0.2,
                        "out_temperature": 1,
                        "out_forcing": 1,
                        "out_dynamic_vars": [
                            "DAT_AEROSOL_ERF",
                            "DAT_HEATCONTENT_AGGREG_TOTAL",
                            "DAT_CO2_AIR2LAND_FLUX",
                        ],
                        "out_ascii_binary": "BINARY",
                        "out_binary_format": 2,
                    },
                    {
                        "core_climatesensitivity": 2,
                        "rf_soxi_dir_wm2": -0.1,
                        "out_temperature": 1,
                        "out_forcing": 1,
                        "out_ascii_binary": "BINARY",
                        "out_binary_format": 2,
                    },
                    {
                        "core_climatesensitivity": 5,
                        "rf_soxi_dir_wm2": -0.35,
                        "out_temperature": 1,
                        "out_forcing": 1,
                        "out_ascii_binary": "BINARY",
                        "out_binary_format": 2,
                    },
                ],
            },
            scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
            output_variables=(
                "Surface Air Temperature Change",
                "Effective Radiative Forcing",
                "Effective Radiative Forcing|Aerosols",
                "Effective Radiative Forcing|CO2",
                "Heat Content",
                "Heat Content|Ocean",
                "Heat Uptake",
                "Heat Uptake|Ocean",
                "Net Atmosphere to Land Flux|CO2",
            ),
        )

        assert isinstance(res, ScmRun)
        assert res["run_id"].min() == 0
        assert res["run_id"].max() == 8
        assert (
            res.get_unique_meta("climate_model", no_duplicates=True)
            == f"MAGICC{MAGICC7.get_version()}"
        )
        assert set(res.get_unique_meta("variable")) == {
            "Surface Air Temperature Change",
            "Effective Radiative Forcing",
            "Effective Radiative Forcing|Aerosols",
            "Effective Radiative Forcing|CO2",
            "Heat Content",
            "Heat Content|Ocean",
            "Heat Uptake",
            "Heat Uptake|Ocean",
            "Net Atmosphere to Land Flux|CO2",
        }

        # check we can also calcluate quantiles
        assert "run_id" in res.meta
        quantiles = calculate_quantiles(res, [0, 0.05, 0.17, 0.5, 0.83, 0.95, 1])
        assert "run_id" not in quantiles.meta

        # a problem for another day...
        # self._check_heat_content_heat_uptake_consistency(res)

        outputs_to_get = {
            "MAGICCv7.5.3": [
                {
                    "variable": "Heat Content|Ocean",
                    "unit": "ZJ",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Heat Uptake|Ocean",
                    "unit": "W/m^2",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Heat Uptake",
                    "unit": "W/m^2",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Effective Radiative Forcing",
                    "unit": "W/m^2",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Net Atmosphere to Land Flux|CO2",
                    "unit": "GtC / yr",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 1,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 0,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp370",
                    "quantile": 1,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp370",
                    "quantile": 0,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 0.05,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp126",
                    "quantile": 0.95,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp370",
                    "quantile": 0.05,
                },
                {
                    "variable": "Surface Air Temperature Change",
                    "region": "World",
                    "year": 2100,
                    "scenario": "ssp370",
                    "quantile": 0.95,
                },
            ]
        }

        output_dict = self._get_output_dict(res, outputs_to_get)
        num_regression.check(output_dict, default_tolerance=dict(rtol=self._rtol))

    def test_variable_naming(self, test_scenarios):
        common_variables = self._common_variables
        res = openscm_runner.run.run(
            climate_models_cfgs={"MAGICC7": ({"core_climatesensitivity": 3},)},
            scenarios=test_scenarios.filter(scenario="ssp126"),
            output_variables=common_variables,
        )

        missing_vars = set(common_variables) - set(res["variable"])
        if missing_vars:
            raise AssertionError(missing_vars)


@pytest.mark.magicc
def test_conc_driven_writes_conc_in_files_and_patches_cfgs(
    tmp_path, monkeypatch,
):
    """Focused test of the conc-file-writing path.

    Builds an adapter in CONCENTRATION_DRIVEN mode, runs
    ``_write_conc_in_files_and_cfg_updates`` directly with
    ``out_directory=tmp_path`` (so we don't need ``_run_dir()`` and a
    real MAGICC install), and verifies that:

    - The per-(scenario, model) patch sets ``file_co2_conc``,
      ``file_ch4_conc``, ``file_n2o_conc`` to paths of written
      ``.IN`` files (RCMIP3-mini's ssp245 baseline supplies all
      three).
    - The matching ``*_switchfromconc2emis_year`` flags default to
      9999.
    - User-supplied ``Atmospheric Concentrations|CO2`` rows shadow
      the baseline CO2 trajectory in the written file.
    """
    monkeypatch.setattr(
        MAGICC7, "get_version", classmethod(lambda cls: "v7.5.3"),
    )

    user_run = ScmRun(pd.DataFrame({
        "model": ["test-model"],
        "scenario": ["ssp245"],
        "region": ["World"],
        "variable": ["Atmospheric Concentrations|CO2"],
        "unit": ["ppm"],
        2050: [999.0],
        2100: [999.0],
    }))

    adapter = MAGICC7(
        cfgs=[
            {
                "core_climatesensitivity": 3,
                "rcmip3_bundle_path": str(RCMIP3_MINI_BUNDLE),
                "scenario": "ssp245",
                "model": "test-model",
            },
        ],
        mode=RunMode.CONCENTRATION_DRIVEN,
        output_variables=("Surface Air Temperature Change",),
    )

    patches = adapter._write_conc_in_files_and_cfg_updates(
        scenarios=user_run,
        cfgs=adapter.cfgs,
        out_directory=str(tmp_path),
    )

    assert ("ssp245", "test-model") in patches
    patch = patches[("ssp245", "test-model")]
    for gas in ("co2", "ch4", "n2o"):
        assert patch[f"{gas}_switchfromconc2emis_year"] == 9999
        path = patch[f"file_{gas}_conc"]
        assert os.path.exists(path), path
        assert path.endswith(f"_{gas.upper()}_CONC.IN")

    # User CO2 trajectory survived into the written file.
    co2_data = pymagicc.io.MAGICCData(patch["file_co2_conc"])
    co2_ts = co2_data.timeseries(time_axis="year")
    assert co2_ts.iloc[0].loc[2050] == pytest.approx(999.0)
    assert co2_ts.iloc[0].loc[2100] == pytest.approx(999.0)

    # MAGICC reads CONC.IN as a contiguous annual series over its full
    # internal window; a sparse / truncated file trips a Fortran
    # end-of-file error at runtime. Assert the writer resampled the
    # (here sparse) bundle onto the annual 1700-2500 grid.
    years = co2_ts.columns.astype(int)
    assert years.min() == 1700
    assert years.max() == 2500
    assert list(years) == list(range(1700, 2501))
    # Values are held constant beyond the last supplied year (2100).
    assert co2_ts.iloc[0].loc[2500] == pytest.approx(999.0)


@pytest.mark.magicc
def test_conc_driven_writes_fgas_mhalo_bundled_arrays(tmp_path, monkeypatch):
    """F-gases / Montreal halocarbons drive via the bundled-array flags.

    The halo bundle supplies ssp245 trajectories for HFC134a (F-gas),
    SF6 (F-gas) and CFC12 (Montreal halocarbon). Verify the per-(scenario,
    model) patch builds the positional ``fgas_files_conc`` /
    ``mhalo_files_conc`` arrays in ``FGAS_NAMES`` / ``MHALO_NAMES`` order,
    fills only the supplied slots, leaves the rest (incl. HALON1202)
    empty, and sets the shared group switch year to 10000.
    """
    from openscm_runner.adapters.magicc7._concentrations_translator import (
        FGAS_NAMES,
        MHALO_NAMES,
    )

    monkeypatch.setattr(
        MAGICC7, "get_version", classmethod(lambda cls: "v7.5.3"),
    )

    adapter = MAGICC7(
        cfgs=[
            {
                "core_climatesensitivity": 3,
                "rcmip3_bundle_path": str(RCMIP3_MINI_HALO_BUNDLE),
                "scenario": "ssp245",
                "model": "test-model",
            },
        ],
        mode=RunMode.CONCENTRATION_DRIVEN,
        output_variables=("Surface Air Temperature Change",),
    )

    # No user overlay: drive purely from the halo bundle baseline.
    empty_run = ScmRun(pd.DataFrame({
        "model": ["test-model"],
        "scenario": ["ssp245"],
        "region": ["World"],
        "variable": ["Emissions|CO2|MAGICC Fossil and Industrial"],
        "unit": ["GtC / yr"],
        2050: [10.0],
        2100: [10.0],
    }))

    patches = adapter._write_conc_in_files_and_cfg_updates(
        scenarios=empty_run,
        cfgs=adapter.cfgs,
        out_directory=str(tmp_path),
    )
    patch = patches[("ssp245", "test-model")]

    # F-gas group: positional array over all 23 names, switch year 10000.
    fgas_array = patch["fgas_files_conc"]
    assert len(fgas_array) == len(FGAS_NAMES) == 23
    assert patch["fgas_switchfromconc2emis_year"] == 10000
    sf6_slot = fgas_array[FGAS_NAMES.index("SF6")]
    hfc134a_slot = fgas_array[FGAS_NAMES.index("HFC134A")]
    assert sf6_slot.endswith("_SF6_CONC.IN") and os.path.exists(sf6_slot)
    assert hfc134a_slot.endswith("_HFC134A_CONC.IN")
    assert os.path.exists(hfc134a_slot)
    # Unsupplied F-gas slots are empty (fall back to MAGICC defaults):
    assert fgas_array[FGAS_NAMES.index("CF4")] == ""

    # Montreal-halocarbon group: 18 names, CFC12 filled, HALON1202 empty.
    mhalo_array = patch["mhalo_files_conc"]
    assert len(mhalo_array) == len(MHALO_NAMES) == 18
    assert patch["mhalo_switchfromconc2emis_year"] == 10000
    cfc12_slot = mhalo_array[MHALO_NAMES.index("CFC12")]
    assert cfc12_slot.endswith("_CFC12_CONC.IN") and os.path.exists(cfc12_slot)
    assert mhalo_array[MHALO_NAMES.index("HALON1202")] == ""


@pytest.mark.magicc
def test_fgas_mhalo_name_lists_match_binary_config():
    """The hardcoded FGAS_NAMES / MHALO_NAMES must track the installed
    binary's namelist order; the positional arrays bind to it."""
    from openscm_runner.adapters.magicc7._compat import f90nml
    from openscm_runner.adapters.magicc7._concentrations_translator import (
        FGAS_NAMES,
        MHALO_NAMES,
    )

    run_dir = Path(MAGICC7()._run_dir())
    defaultall = run_dir / "MAGCFG_DEFAULTALL.CFG"
    if not defaultall.exists():
        pytest.skip(f"MAGCFG_DEFAULTALL.CFG not found at {defaultall}")

    cfg = f90nml.read(str(defaultall))["nml_allcfgs"]
    binary_fgas = tuple(s.strip().upper() for s in cfg["fgas_names"])
    binary_mhalo = tuple(s.strip().upper() for s in cfg["mhalo_names"])
    assert FGAS_NAMES == binary_fgas
    assert MHALO_NAMES == binary_mhalo


@pytest.mark.magicc
def test_conc_driven_end_to_end_runs_the_binary(test_scenarios):
    """Drive the real MAGICC binary in concentration-driven mode.

    The file-writing tests above bypass the binary, so they can't catch
    a malformed ``CONC.IN`` (e.g. a sparse / truncated grid that trips
    MAGICC's Fortran ``readdata`` end-of-file check). This runs ssp245
    through the binary in both modes and asserts conc-driven produces a
    finite GSAT in the same ballpark as emissions-driven. It also checks
    that the prescribed CO2 concentration round-trips: requested as an
    output, MAGICC should echo what was written into ``CO2_CONC.IN``.
    """
    scenarios = test_scenarios.filter(scenario="ssp245")

    gsat = {}
    for mode in (RunMode.EMISSIONS_DRIVEN, RunMode.CONCENTRATION_DRIVEN):
        adapter = MAGICC7(
            cfgs=[
                {
                    "core_climatesensitivity": 3,
                    "rcmip3_bundle_path": str(RCMIP3_MINI_BUNDLE),
                },
            ],
            mode=mode,
            output_variables=(
                "Surface Air Temperature Change",
                "Atmospheric Concentrations|CO2",
            ),
        )
        res = openscm_runner.run.run([adapter], scenarios=scenarios)
        vals = res.filter(
            variable="Surface Air Temperature Change", year=2100,
        ).values.flatten()
        assert len(vals) > 0
        assert all(pd.notna(vals))
        gsat[mode] = float(vals[0])

        if mode == RunMode.CONCENTRATION_DRIVEN:
            # Round-trip: the prescribed CO2 concentration (rcmip3-mini
            # ssp245 baseline, ~602.78 ppm at 2100) should come back out.
            co2_out = res.filter(
                variable="Atmospheric Concentrations|CO2", year=2100,
            ).values.flatten()
            assert len(co2_out) > 0
            assert co2_out[0] == pytest.approx(602.78, rel=1e-2)

    # Physically-consistent bundle: the two modes should land close.
    assert gsat[RunMode.CONCENTRATION_DRIVEN] == pytest.approx(
        gsat[RunMode.EMISSIONS_DRIVEN], abs=0.5,
    )


@pytest.mark.magicc
def test_conc_driven_requires_rcmip3_bundle_path():
    """No rcmip3_bundle_path -> clear ValueError on conc-driven dispatch."""
    adapter = MAGICC7(
        cfgs=[{"core_climatesensitivity": 3}],
        mode=RunMode.CONCENTRATION_DRIVEN,
        output_variables=("Surface Air Temperature Change",),
    )
    with pytest.raises(ValueError, match="rcmip3_bundle_path"):
        adapter._resolve_rcmip3_bundle_path(adapter.cfgs)


@pytest.mark.magicc
def test_write_scen_files_and_make_full_cfgs(test_scenarios):
    adapter = MAGICC7()
    test_scenarios_magiccdf = pymagicc.io.MAGICCData(test_scenarios)
    res = adapter._write_scen_files_and_make_full_cfgs(
        test_scenarios_magiccdf,
        [
            {
                "file_emisscen_3": "overwritten by adapter.magicc_scenario_setup",
                "other_cfg": 12,
            }
        ],
    )

    for (model, scenario), _ in test_scenarios_magiccdf.meta.groupby(
        ["model", "scenario"]
    ):
        scen_file_name = (
            f"{scenario}_{model}.SCEN7".upper()
            .replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "-")
        )
        scen_full_filename = os.path.join(
            adapter._run_dir(), "openscm-runner", scen_file_name
        )

        scenario_cfg = [v for v in res if v["file_emisscen"] == scen_full_filename]

        assert len(scenario_cfg) == 1
        scenario_cfg = scenario_cfg[0]
        assert scenario_cfg["other_cfg"] == 12
        assert scenario_cfg["model"] == model
        assert scenario_cfg["scenario"] == scenario
        for i in range(2, 9):
            scen_flag_val = scenario_cfg[f"file_emisscen_{i}"]

            assert scen_flag_val == "NONE"


@pytest.mark.magicc
@pytest.mark.parametrize(
    "out_config",
    (
        ("core_climatesensitivity", "rf_total_runmodus"),
        ("core_climatesensitivity",),
        ("rf_total_runmodus",),
    ),
)
def test_return_config(test_scenarios, out_config):
    core_climatesensitivities = [2, 3]
    rf_total_runmoduses = ["ALL", "CO2"]

    cfgs = []
    for cs in core_climatesensitivities:
        for runmodus in rf_total_runmoduses:
            cfgs.append(
                {
                    "out_dynamic_vars": [
                        "DAT_TOTAL_INCLVOLCANIC_ERF",
                        "DAT_SURFACE_TEMP",
                    ],
                    "core_climatesensitivity": cs,
                    "rf_total_runmodus": runmodus,
                }
            )

    res = openscm_runner.run.run(
        climate_models_cfgs={"MAGICC7": cfgs},
        scenarios=test_scenarios.filter(scenario=["ssp126", "ssp245", "ssp370"]),
        output_variables=(
            "Surface Air Temperature Change",
            "Effective Radiative Forcing",
        ),
        out_config={"MAGICC7": out_config},
    )

    for k in out_config:
        assert k in res.meta.columns
        ssp126 = res.filter(scenario="ssp126")

        # check all the configs were used and check that each scenario
        # has all the configs included in the metadata too
        if k == "core_climatesensitivity":
            assert set(res.get_unique_meta(k)) == set(core_climatesensitivities)
            assert set(ssp126.get_unique_meta(k)) == set(core_climatesensitivities)
        elif k == "rf_total_runmodus":
            assert set(res.get_unique_meta(k)) == set(rf_total_runmoduses)
            assert set(ssp126.get_unique_meta(k)) == set(rf_total_runmoduses)
        else:
            raise NotImplementedError(k)


@pytest.mark.magicc
@pytest.mark.parametrize(
    "cfgs",
    (
        [{"pf_apply": 1, "PF_APPLY": 0}],
        [{"pf_apply": 1}, {"pf_apply": 1, "PF_APPLY": 0}],
    ),
)
def test_return_config_clash_error(test_scenarios, cfgs):
    with pytest.raises(ValueError):
        openscm_runner.run.run(
            climate_models_cfgs={"MAGICC7": cfgs},
            scenarios=test_scenarios.filter(scenario=["ssp126"]),
            output_variables=("Surface Air Temperature Change",),
            out_config={"MAGICC7": ("pf_apply",)},
        )
