# Roadmap

What we're working on and what's next.
Decisions (made, active and in the backlog) are in [decisions](decisions.md).
Work which depends on an open decision must not silently settle it.

Work items have IDs so other pages can refer to them.
IDs never change and aren't re-used.

## Now

- **W01** Merge the MAGICC AR6 adapters (PR link TBD).
- **W02** CICERO AR7 (PR lnk TBD).

## Next

- **W13** Decide what to work on next:
  which of the items under "Later" to move here,
  and how to make progress on the [active decisions](decisions.md#active).

## Later

Candidates for "Next", not yet prioritised.

- **W03** Acceptance tests for the MAGICC AR6 CMIP adapters
  (`MAGICCAR6Adapter*From{CMIP6,CMIP7}PreIndustrial`).
  They won't be released in the public openscm-runner repo until we have these
  (see [testing](testing.md#acceptance-tests)).
- **W04** Check units in the verify functions (openscm-units).
- **W05** Check harmonisation to history in the AR6/AR7 verify functions
  (gcages/pandas-openscm functions, or ported in; tolerances are B05).
- **W06** Talk to the remaining carbon budget team
  about which AR7 scenario variants they need (B12).
- **W07** Confirm species to use for AR6 workflow and AR7 (A5).
- **W08** A thin multi-model test: a combination of models (chosen by us)
  in one environment, checking that installing them together
  doesn't break any individual model's behaviour.
- **W09** Experiment-specific scientific checks, as integration tests
  (to discuss before writing, some depend on open decisions, e.g. B16-B20):
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
- **W10** Runtime and coverage targets for the shared tests
  (measure before claiming them):
  unit tests under 60 seconds offline,
  the standard PR suite under 10 minutes with small ensembles,
  at least 95% branch coverage of shared code.
  While writing tests, deliberately break one unit conversion, one ordering path
  and one historical splice, and check the relevant tests fail.
- **W11** Keep [implementing an adapter](implementing-an-adapter.md) up to date
  (e.g. the minimum outputs (A7), the CICERO-SCM links (W02)
  and how to document running adapters (B21)).
- **W12** An experiment that starts in 1750.
