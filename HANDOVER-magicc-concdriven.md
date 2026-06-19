# Handover — MAGICC7 concentration-driven mode

Branch: `magicc_concdriven`. This file is a handover for picking the
work up on a machine that can actually run the MAGICC7 binary.

## Goal

Bring MAGICC7 to parity with the FaIR2 / CICEROSCMPY2 adapters'
`RunMode.CONCENTRATION_DRIVEN` support, so a single `openscm_runner.run.run`
call can drive all three models from `Atmospheric Concentrations|*`
inputs.

## Scope decisions (confirmed with the user)

- Extend the existing pymagicc-backed adapter at
  [src/openscm_runner/adapters/magicc7/](src/openscm_runner/adapters/magicc7/).
  The open-source MAGICC at gitlab.com/magicc was considered but
  rejected for now (alpha-stage, separate larger initiative).
- Hybrid baseline + overlay: load the per-scenario RCMIP3 baseline
  and overlay user-supplied `Atmospheric Concentrations|*` rows on
  top (year-by-year merge, user values win where supplied).
- Per-gas mixed mode (mirrors FaIR2): a gas is driven by concentration
  only when every scenario in the batch supplies it; other gases stay
  emissions-driven via the existing SCEN7 path.
- `rcmip3_bundle_path` is **required** for conc-driven runs (matches
  FaIR2 / CICEROSCMPY2 — explicit version pinning, no dependence on
  the binary's bundled historical data).

## v1 scope reduction (made during implementation)

After inspecting [the real `MAGCFG_DEFAULTALL.CFG`](file:///Users/bensan/Downloads/magicc-v7.5.3/run/MAGCFG_DEFAULTALL.CFG):

- v1 supports **CO2 / CH4 / N2O only**. These are the three species
  MAGICC7 exposes via per-gas `FILE_<gas>_CONC` + `<gas>_SWITCHFROMCONC2EMIS_YEAR`
  cfg flags.
- F-gases (23 species, `FGAS_NAMES`) and Montreal halocarbons (18,
  `MHALO_NAMES`) use **bundled-array** cfg flags
  (`FGAS_FILES_CONC` / `MHALO_FILES_CONC` indexed positionally by
  `FGAS_NAMES` / `MHALO_NAMES`, each sharing a single
  `*_SWITCHFROMCONC2EMIS_YEAR`). Supporting them needs a separate
  code path (write all N files, build the positional array, set one
  switch-year). Deferred — see "Follow-up work" below.
- User overlay rows for unsupported species are logged at INFO and
  fall through to the SCEN7 emissions-driven path.

This restriction is appropriate because `tests/test-data/rcmip3-mini/`
only ships CO2 / CH4 / N2O concentrations anyway, and ESM-style
conc-driven experiments overwhelmingly care about WMGHGs.

## Files in this branch

Modified:

- [src/openscm_runner/adapters/magicc7/magicc7.py](src/openscm_runner/adapters/magicc7/magicc7.py)
  — declared `supported_modes`, added `_with_mode_applied`,
  `_write_conc_in_files_and_cfg_updates`, `_merge_conc_patch`,
  `_resolve_rcmip3_bundle_path`. `_run()` now filters emissions
  before the variable rename so `Atmospheric Concentrations|*` rows
  pass through unmangled, then conditionally augments `full_cfgs`
  with conc patches when `self.mode == CONCENTRATION_DRIVEN`.
- [src/openscm_runner/adapters/magicc7/_run_magicc_parallel.py](src/openscm_runner/adapters/magicc7/_run_magicc_parallel.py)
  — `_run_func` pops the two new adapter-internal cfg keys
  (`magicc_conc_driven`, `rcmip3_bundle_path`) before
  `magicc.run(**cfg)` so they don't leak into the MAGICC namelist.
- [tests/integration/test_magicc7.py](tests/integration/test_magicc7.py)
  — added two `@pytest.mark.magicc` tests: the conc-file-writing
  smoke (monkeypatches `get_version`, uses `tmp_path`, verifies
  cfg shape + .IN files + user trajectory survival) and a guard
  that `rcmip3_bundle_path` is required.

Added:

- [src/openscm_runner/adapters/magicc7/_concentrations_translator.py](src/openscm_runner/adapters/magicc7/_concentrations_translator.py)
  — new module: `RCMIP_TO_MAGICC_SPECIES` rename table,
  `SUPPORTED_PER_GAS_CONC_SPECIES = {"CO2", "CH4", "N2O"}`,
  `cfg_keys_for_species`, `build_concentrations_overlay`,
  `write_conc_in_file`. Single source of truth for the cfg-flag
  convention.
- [tests/unit/adapters/test_magicc7_concentrations.py](tests/unit/adapters/test_magicc7_concentrations.py)
  — pure-Python unit tests (no pymagicc / no binary needed) for
  cfg-key naming, the F-gas rejection path, baseline-only overlay,
  year-by-year merge, and the mixed-mode drop filter.

No `changelog/*.md` entry yet — needs the MR/PR number, add after opening one.

## Verified

- The cfg-key naming (`file_co2_conc`, `co2_switchfromconc2emis_year`,
  etc.) matches MAGICC's real `MAGCFG_DEFAULTALL.CFG` (probed on the
  v7.5.3 distribution at `~/Downloads/magicc-v7.5.3/run/`).
- Pure-Python syntax of every changed file (via `ast.parse`).
- Existing emissions-driven tests are untouched — the
  `Emissions|*` filter is a no-op when the input has no
  concentration rows (verified by checking the
  `tests/test-data/rcmip_scen_ssp_world_emissions.csv` fixture).

## Not yet verified (blocked on this machine)

- Running the unit tests under a real pytest (no pixi/poetry env
  available, no system python with scmdata installed).
- Running the integration test under a real pytest + pymagicc.
- End-to-end run against the MAGICC binary (unsigned binary
  restriction on this machine; the binary at
  `~/Downloads/magicc-v7.5.3/bin/magicc-darwin-arm64` cannot
  execute).

## Pick up on another machine

1. **Fast: unit tests, no pymagicc, no binary**

   ```sh
   poetry install --with tests
   poetry run pytest tests/unit/adapters/test_magicc7_concentrations.py -v
   ```

   Expected: five tests pass, exercising cfg-key naming + overlay
   merge semantics + the F-gas rejection path against the
   `rcmip3-mini` bundle.

2. **Integration: writes real `.IN` files, monkeypatches the binary call**

   ```sh
   poetry install --with tests --extras magicc
   poetry run pytest tests/integration/test_magicc7.py -k conc_driven -v
   ```

   Expected: the conc-driven tests pass. These need pymagicc but NOT
   the MAGICC binary (`get_version` is monkeypatched, the binary
   call inside `_run_dir()` is bypassed by passing `out_directory`
   directly, `run_magicc_parallel` is never called).

3. **End-to-end: real MAGICC run, conc-driven CO2 vs emissions-driven**

   ```sh
   export MAGICC_EXECUTABLE_7=/path/to/magicc7
   poetry run python -c "
   from pathlib import Path
   import scmdata
   import openscm_runner.run
   from openscm_runner import RunMode
   from openscm_runner.adapters import MAGICC7

   scenarios = scmdata.ScmRun(
       'tests/test-data/rcmip_scen_ssp_world_emissions.csv',
       lowercase_cols=True,
   ).filter(scenario='ssp245')

   for mode in (RunMode.EMISSIONS_DRIVEN, RunMode.CONCENTRATION_DRIVEN):
       adapter = MAGICC7(
           cfgs=[{
               'core_climatesensitivity': 3,
               'rcmip3_bundle_path': str(Path('tests/test-data/rcmip3-mini')),
           }],
           mode=mode,
           output_variables=('Surface Air Temperature Change',),
       )
       result = openscm_runner.run.run([adapter], scenarios=scenarios)
       print(mode, '2100 GSAT:', float(result.filter(
           variable='Surface Air Temperature Change', year=2100,
       ).values))
   "
   ```

   What to look for: GSAT at 2100 should be in the same ballpark
   between the two modes for ssp245 (the bundle's CO2/CH4/N2O
   trajectories are physically consistent with the bundle's
   emissions, so both modes should converge to similar warming).
   A large divergence indicates the cfg patch isn't taking effect.

   Cross-check by inspecting one of the written `.IN` files:

   ```sh
   ls $(dirname $MAGICC_EXECUTABLE_7)/../run/openscm-runner/*_CO2_CONC.IN
   head -25 $(dirname $MAGICC_EXECUTABLE_7)/../run/openscm-runner/*_CO2_CONC.IN
   ```

   Should look like the bundled `~/Downloads/magicc-v7.5.3/run/SSP245_CO2_CONC.IN`
   reference: header + namelist + `VARIABLE: CO2_CONC`, `TODO: SET`,
   `UNITS: ppm`, `YEARS: WORLD`, then year/value rows.

## Open items to check during the end-to-end run

1. **`get_version()[1]` round-trip.** The conc-file writer passes
   `magicc_version=self.get_version()[1]` (mirroring the existing
   SCEN7 writer at [magicc7.py:322](src/openscm_runner/adapters/magicc7/magicc7.py#L322)).
   On v7.5.3 this slices `"v7.5.3"` to `"7"`, which is what pymagicc
   wants. If the binary returns a differently-formatted version
   string, the slice fails silently — easy to spot in the written
   `.IN` header.
2. **Switch-year acceptance.** The default patch sets
   `<gas>_switchfromconc2emis_year = 9999` for the gases we drive
   by concentration. Verify MAGICC accepts 9999 (or whether it
   needs a more specific value like the actual final year). The
   existing default in `MAGCFG_DEFAULTALL.CFG` is 2015, so 9999 is
   the "never switch" sentinel — typically accepted.
3. **`.IN` REGIONMODE.** pymagicc writes
   `THISFILE_REGIONMODE = 'FOURBOX'` for single-region World data
   (per `~/Downloads/magicc-v7.5.3/run/SSP245_CO2_CONC.IN`). My
   writer relies on pymagicc to set this correctly. Worth eyeballing
   one written file.

## Follow-up work (out of scope for v1)

- **F-gas / Montreal-halocarbon support** via bundled-array flags
  (`FGAS_FILES_CONC`, `MHALO_FILES_CONC`). Needs:
  1. Write all 23 F-gas / 18 MHALO `.IN` files per (scenario, model),
     even if only one or two species have user overrides — the
     bundled-array flag has to be a complete positional list.
  2. Match index order against `FGAS_NAMES` / `MHALO_NAMES` from
     `MAGCFG_DEFAULTALL.CFG` (the order is **not** alphabetical).
  3. Set `fgas_switchfromconc2emis_year = 9999` (single shared flag)
     for the F-gas bundle; same for `mhalo_switchfromconc2emis_year`.
  4. Decide what to do for species the RCMIP3 bundle does NOT
     supply concentrations for (probably: keep MAGICC's shipped
     defaults; do NOT include them in our written-files array).
- **Adapter for open-source MAGICC** at gitlab.com/magicc — separate
  initiative, alpha-stage upstream, see the original plan file at
  `~/.claude/plans/ok-let-s-look-composed-pillow.md` for the
  comparison notes.
- **Multi-model cross-check fixture** comparing GSAT at 2100 across
  FaIR2 / CICEROSCMPY2 / MAGICC7 in conc-driven mode on ssp245.
  Useful as a sanity check for the whole modern-adapter family but
  needs all three binaries / Python packages installed
  simultaneously.

## Useful references

- `MAGCFG_DEFAULTALL.CFG` cfg-key conventions:
  `~/Downloads/magicc-v7.5.3/run/MAGCFG_DEFAULTALL.CFG`
- Reference `.IN` file shape:
  `~/Downloads/magicc-v7.5.3/run/SSP245_CO2_CONC.IN`
- FaIR2 mixed-mode reference (intersection-over-scenarios filter):
  [src/openscm_runner/adapters/fair2_adapter/fair2_adapter.py:719-786](src/openscm_runner/adapters/fair2_adapter/fair2_adapter.py#L719-L786)
- FaIR2 `_with_mode_applied` reference:
  [src/openscm_runner/adapters/fair2_adapter/fair2_adapter.py:223-232](src/openscm_runner/adapters/fair2_adapter/fair2_adapter.py#L223-L232)
- RCMIP3 reader entry point:
  [src/openscm_runner/io/rcmip3.py](src/openscm_runner/io/rcmip3.py)
- AR6 drawnset (for end-to-end MAGICC config):
  `~/Downloads/magicc-ar6-0fd0f62-f023edb-drawnset/0fd0f62-derived-metrics-id-f023edb-drawnset.json`
