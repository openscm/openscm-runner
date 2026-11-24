# Roadmap

What we're working on and what's next.
Decisions (made, active and in the backlog) are in [decisions](../further-background/decisions.md).
Work which depends on an open decision must not silently settle it.

Work items have IDs so other pages can refer to them.
IDs never change and aren't re-used.

## Now

- [](#w01){#w01}**W01** Merge the MAGICC AR6 adapters (PR link TBD).
- [](#w02){#w02}**W02** CICERO AR7 (PR lnk TBD).

## Next

- [](#w13){#w13}**W13** Decide what to work on next:
  which of the items under "Later" to move here,
  and how to make progress on the [active decisions](../further-background/decisions.md#active).

## Later

Candidates for "Next", not yet prioritised.

- [](#w03){#w03}**W03** Acceptance tests for the MAGICC AR6 CMIP adapters
  (`MAGICCAR6Adapter*From{CMIP6,CMIP7}PreIndustrial`).
  They won't be released in the public openscm-runner repo until we have these
  (see [testing](testing.md#acceptance-tests)).
- [](#w04){#w04}**W04** Check units in the verify functions (openscm-units).
  The check will need `"unit"` to be a timeseries level
  (use `ensure_timeseries_level` in `verification.py`, as the variable and region checks do).
- [](#w05){#w05}**W05** Check harmonisation to history in the AR6/AR7 verify functions
  (gcages/pandas-openscm functions, or ported in; tolerances are [B05][b05]).
- [](#w06){#w06}**W06** Talk to the remaining carbon budget team
  about which AR7 scenario variants they need ([B12][b12]).
- [](#w07){#w07}**W07** Confirm species to use for AR6 workflow and AR7 ([A5][a5]).
- [](#w08){#w08}**W08** A thin multi-model test: a combination of models (chosen by us)
  in one environment, checking that installing them together
  doesn't break any individual model's behaviour.
  It runs as its own CI job.
  Waits for a second model (CICERO-SCM, [W02][w02]).
- [](#w09){#w09}**W09** Experiment-specific scientific checks, as integration tests
  (to discuss before writing, some depend on open decisions, e.g. [B16][b16]-[B20][b20]):
    - full scenarios: exact historical splice and agreed future natural forcing;
      land-use treatment responds to biosphere emissions as specified
    - anthropogenic-only: natural forcing disabled over the approved period;
      anthropogenic land-use remains enabled
      (not implemented by subtracting a natural-only temperature trajectory
      from a nonlinear full run)
    - CO2-forcing-only scenario: uses scenario history, not the idealised initial state;
      non-CO2 and land-use radiative contributions absent under the approved definition;
      biosphere carbon-cycle effects tested separately
    - idealised CO2 concentration: reference concentration is independent of the first sample;
      abrupt-4xCO2 and 1pctCO2 relative to the approved reference
    - idealised CO2 emissions: zero-emissions control and flat10;
      no unintended scenario history, AFOLU effects or natural perturbation
    - ERF: exactly the supplied total ERF,
      without added natural forcing or implicitly reapplied efficacies
      (zero ERF is already tested, `tests/integration/test_erf_zero.py`)
    - CMIP concentration/esm/allGHG: correct species are concentration- versus emissions-driven,
      prescribed natural ERF is honoured, AFOLU-derived land-use treatment is correct
      (the MAGICC AR6 integration tests already do much of this for MAGICC)

    Where model APIs expose component diagnostics, test native flags and drivers
    as well as final temperature,
    rather than inferring all forcing isolation from one aggregate output.
- [](#w10){#w10}**W10** Runtime and coverage targets for the shared tests
  (measure before claiming them):
  unit tests under 60 seconds offline,
  the standard PR suite under 10 minutes with small ensembles,
  at least 95% branch coverage of shared code.
  While writing tests, deliberately break one unit conversion, one ordering path
  and one historical splice, and check the relevant tests fail.
- [](#w11){#w11}**W11** Keep [implementing an adapter](../how-to-guides/implementing-an-adapter.md) up to date
  (e.g. the minimum outputs ([A7][a7]), the CICERO-SCM links ([W02][w02])
  and how to document running adapters ([B21][b21])).
- [](#w12){#w12}**W12** An experiment that starts in 1750.
- [](#w14){#w14}**W14** A better interface for per-variable tolerances
  on top of `pandas_openscm.comparison.compare_close`
  (see [testing](testing.md#4-comparison-rules); tolerances are decision [B08][b08]).
- [](#w15){#w15}**W15** Discuss and prioritise the candidate test cases in
  [testing](testing.md#5-candidate-test-cases-to-discuss-before-writing)
  (alongside [W09][w09]).
- [](#w16){#w16}**W16** A more informative type hint for ensemble members' output data
  (`EnsembleMemberResult.data_if_succeeded`, currently a plain `pd.DataFrame`),
  so it's clear from the type how the data should be shaped.
- [](#w17){#w17}**W17** Let users choose where the ensemble member level goes in the index
  in `OpenSCMRunnerOutput.as_df` (it's always the first level at the moment).
- [](#w18){#w18}**W18** Combine the results from all adapters into a single dataframe
  (`RunResults`). Needs an index level that identifies the adapter/model,
  which waits for decisions [B10][b10] and [A3][a3].
- [](#w19){#w19}**W19** Add definitions of the standard output variables
  alongside their names (`STANDARD_OUTPUT_VARIABLES` in `output_specs.py`),
  and consider storing them as a `frozenset` rather than a tuple.
  Related to the minimum outputs (decision [A7][a7]).
- [](#w20){#w20}**W20** Check that adapters' outputs contain all the requested variables
  (in `verify_adapter_outputs`).
  Whether `run_checks=False` skips this is decision [A4][a4].
- [](#w21){#w21}**W21** Report input problems as structured objects rather than plain strings
  (in `verification.py`), so code can inspect them (e.g. via an attribute on
  `InvalidInputError`) instead of parsing the error message.
- [](#w22){#w22}**W22** Get all the RCMIP phase 3 data from its Zenodo release
  (https://doi.org/10.5281/zenodo.23347317) once the ScenarioMIP files are released there.
  `tests/test-data/cmip-pre-industrial-branch/generate_data.py` still downloads
  from GitLab (tag v3.0.1) because it needs
  `ScenarioMIP/rcmip_phase3_{concentrations,forcing}_ScenarioMIP_v3.0.1.csv`,
  which aren't in the Zenodo bundle (v3.0.1) yet.
  `scripts/get-rcmip3-pre-industrial-values.py` already uses the Zenodo release.
