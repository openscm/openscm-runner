# Testing plan

The kinds of tests (unit, integration and acceptance) are decided
([decision A8](../further-background/decisions.md#decided)).
Still to discuss: the candidate test cases in section 5,
experiment-specific scientific checks (roadmap [W09][w09])
and runtime and coverage targets for the shared tests (roadmap [W10][w10]).

## 1. The test suite of v0.13 and before

We are not carrying the test suite of v0.13 and before over.
It is misleading: numerical baselines live inside the integration tests,
the regression directory is empty,
and global fixtures probe for external models at collection time
and skip when they're missing.
It can be mined for ideas (e.g. which outputs model teams care about),
nothing more.

## 2. Kinds of tests

| Kind | What it checks | Where |
| --- | --- | --- |
| Unit | Our own logic, e.g. the verify functions catch invalid inputs via the `run_*` functions | `tests/unit/` (adapter-specific: `tests/unit/<adapter group>/`) |
| Integration | Properties every adapter for an experiment must have, e.g. CO2-only runs only have CO2 forcing, zero ERF in gives zero out | `tests/integration/` (adapter-specific: `tests/integration/<adapter group>/`) |
| Acceptance | Running an adapter through this package reproduces the outputs its model team expects | `tests/acceptance/<adapter group>/` |

An adapter group is a model, version and configuration, e.g. `magicc-ar6`.

### Unit tests

Fast, offline, no model installed.
This includes the adapter-specific ones
(e.g. the MAGICC AR6 unit tests mock the parts which need MAGICC).

### Integration tests

These check what an experiment should do,
independent of any stored numbers
(e.g. "zero ERF in gives zero out" holds for every model).
The shared ones are parametrised over the adapters that support the experiment
(e.g. `tests/integration/test_erf_zero.py`).
They run the models, so they need them installed.

Adapter implementers may also add their own integration tests,
based on what they know can go wrong with their model.
This is an extra (perhaps easier to handle) layer on top of the acceptance tests.

### Acceptance tests

The adapter writer (model team) provides inputs
and the outputs they expect their model to produce.
We check that running through this package reproduces them.

- All acceptance tests for one adapter group live in one file,
  e.g. `tests/acceptance/cicero-scm-v2-0-config-a-b-c/test_acceptance_cicero_scm.py`,
  with data in the `data/` directory next to it.
- Every adapter must be covered by at least one acceptance test.
  Temporary exception: the MAGICC AR6 CMIP adapters
  (`MAGICCAR6Adapter*From{CMIP6,CMIP7}PreIndustrial`) don't have acceptance tests
  (only integration tests, see `tests/acceptance/magicc-ar6/data/README.md`).
  They won't be released in the public openscm-runner repo until we have these acceptance tests.
  TODO: make sure this is removed when we remove these adapters
- Tests which need a model that isn't installed fail, they don't skip.
  E.g. the MAGICC AR6 tests get their configuration from
  `MAGICCAR6AdapterConfiguration.from_environment`,
  which uses the paths to MAGICC v7.5.3 and the AR6 probabilistic distribution
  if they are set, otherwise downloads the official versions with a magicc.org token
  (see `.env.sample`),
  and raises (with instructions) if neither is set.
  Environment variables which are set are used as given.
  For any which aren't set, the tests fall back to a `.env` file in the repository root
  (an autouse fixture in `tests/conftest.py` sets them with `monkeypatch`,
  so only for the duration of each test).
  The package itself never reads `.env`.

### Adapter tests, CI and coverage

Each adapter group's tests (its unit, integration and acceptance tests)
are marked with a pytest marker for the group, e.g. `magicc_ar6`.
This includes the adapter group's cases of the shared integration tests
(marked on their parameters, e.g. in `tests/integration/test_erf_zero.py`).
The marker makes it easy to select an adapter group's tests
(e.g. `pytest -m magicc_ar6`) or to opt out of them (`pytest -m "not magicc_ar6"`).

By default (via `addopts` in `pyproject.toml`),
pytest deselects every adapter group's tests and slow tests,
so `pytest` and `make test` run the shared tests without needing any models.

CI (`.github/workflows/ci.yaml`) runs on every pull request:

- the shared tests
  (everything which isn't marked as an adapter group's tests or slow, `make test`),
  with the same `-m` as `addopts`
- one job per adapter group, in an environment with only that group's extra,
  which runs all the tests marked for the group, including the slow ones
  (e.g. `make test-magicc-ar6`).
  MAGICC AR6's job gets MAGICC with a magicc.org token
  stored as a repository secret, so it fails for pull requests from forks.
  This is deliberate: a required check which can't run fails, it isn't skipped.
  It runs on Linux with the oldest and newest supported Python, and on macOS.
  A job which selects no tests fails (pytest's exit code).

The lowest-direct dependency job (`tests-resolution-strategies` in `ci.yaml`)
and the scheduled latest-upstream-dependencies workflow (`test-upstream-latest.yaml`)
run the shared tests only (the same `-m` as `addopts`, so they don't need any models).
The scheduled PyPI installation workflow (`install-pypi.yaml`)
runs everything (`-m ""`), including every adapter group's tests and the slow tests.

For now there are no path filters (every adapter job runs on every pull request)
and each adapter group's job runs its slow tests.
We may change this if CI becomes too slow.

Slow tests which aren't an adapter group's tests have no home in CI yet:
every job which runs the shared tests deselects slow tests
(only the weekly PyPI installation workflow would run them).
There aren't any at the moment.
If we add one, we need to make a CI home for them
(e.g. a job which runs `-m "slow and not magicc_ar6"`).

Adding an adapter group means adding its marker
(registered in `pyproject.toml`)
to `addopts` and the matching `-m` in CI
(the `tests` and `tests-resolution-strategies` jobs in `ci.yaml`
and `test-upstream-latest.yaml`; keep them all consistent),
plus a make target and a CI job like MAGICC AR6's.

Coverage:

- the shared tests must give at least 90% coverage of everything except the adapters
  (`fail_under` in `pyproject.toml`, the adapters are omitted from the report)
- the tests marked for an adapter group must give 100% coverage
  of the group's modules.
  The adapter group's CI job fails if they don't
  (e.g. `make test-magicc-ar6` for MAGICC AR6).
Code which can only run on some platforms is tested by mocking the platform
(e.g. MAGICC AR6's binary selection), so the coverage is the same everywhere.

#### Exception: MAGICC AR6

The MAGICC AR6 acceptance tests are in `tests/acceptance/magicc-ar6/`.
MAGICC AR6 is the exception to "the adapter writer provides the data,
we don't generate it": we generate its acceptance data ourselves.
It is there to demonstrate how acceptance data could be generated:
each data folder has a script which produces the data
(run with `uv run --script`, never importing `openscm_runner`),
whose environment is locked with PEP 723 inline script metadata
and `uv lock --script`,
so the data can be regenerated without dependency conflicts with this package.
See `tests/acceptance/magicc-ar6/data/README.md`.

`MAGICCAR6AdapterAR6Scenario` also has a full-ensemble test
which compares with AR6's published temperature percentiles.
This is the only check against an external source,
so it validates the infrastructure the other MAGICC AR6 tests rely on.
It runs all 600 ensemble members, so it is marked `slow`.
It runs with the rest of the MAGICC AR6 tests (`make test-magicc-ar6`).
If you're in a hurry, deselect it with `-m "magicc_ar6 and not slow"`.

In all cases the question is "does the adapter produce what the model team expects?",
and the model team is the one who can answer it.

### What we don't do

- Regression tests, i.e. producing expected outputs ourselves.
  We can't make baselines for models we don't know.
- A separate "contract" layer.
  The earlier plan used this name for one shared test suite
  run against every adapter (fake and real)
  to check they all follow the same API rules (ordering, no mutation etc.).
  In this design, the `run_*` functions do the shared output checks once,
  and the integration tests are parametrised over adapters,
  so there is no need for a separate layer.
- Separate packaging/CI scaffolding tests:
  the CI from the copier template covers these
  (building and checking the package, importing it without extras, installing it from PyPI).

### What we try to avoid

- Extended scientific validation (long runs, full ensembles, assessment checks).
  That usually belongs elsewhere (gcages or similar).
  However, sometimes it is our only option for external validation,
  e.g. MAGICC AR6's full-ensemble check against AR6, see above,
  which is the strongest acceptance test we have of this setup.

## 3. Guidance for acceptance test data

Adapter writers provide the data, we don't generate it
(except for MAGICC AR6, see above).
Things for them to get right:

- Freeze exactly what produced the expected outputs:
  model version, calibration identifier, history/forcing versions,
  ensemble member IDs.
- We recommend adapter writers include a README in their acceptance test data folder
  (`tests/acceptance/magicc-ar6/data/README.md` is an example)
  so there is a record of how the data was created, who to ask if there are questions etc.
  This isn't compulsory or enforced though.
- Pick inputs that exercise the model:
  e.g. a low/negative and a high emissions scenario,
  and enough ensemble members to see distinct responses.
- Compare along the full trajectory (but not necessarily every year of output),
  not just the final year or ensemble quantiles.
- Store data as wide CSV (one row per timeseries),
  with an `ensemble_member` column in the expected outputs,
  rounded to a fixed number of significant figures,
  so re-exporting doesn't create diffs from floating-point noise
  and git can track changes sensibly.
- Licensed or private data doesn't go in the repository.
  Data generated with a licensed model can be
  (e.g. the MAGICC AR6 expected outputs are committed,
  but MAGICC and the AR6 probabilistic distribution aren't).
  To run such models in CI, a custom approach is likely needed
  so discuss with the package maintainers about how to support your use case.
  For an example, see how MAGICC AR6 is run (the `tests-magicc-ar6` job in
  [CI](https://github.com/openscm/openscm-runner/blob/main/.github/workflows/ci.yaml)).

Updating expected outputs is a change that should be reviewed by the adapter writer,
explaining why the outputs changed.
Because scientific configuration is selectable at adapter construction,
each acceptance group must identify the configuration it exercises.
A passing group does not certify every possible calibration or configuration.

## 4. Comparison rules

Use `pandas_openscm.comparison.compare_close`
(it reports which timeseries/years differ),
plus variable-specific tolerances on top.
A better interface for this is roadmap [W14][w14].

- Compare labels (index levels, years, variables) exactly before values.
- Use a declared tolerance per variable:
  `abs(actual - expected) <= absolute_tolerance + relative_tolerance * abs(expected)`.
  Near-zero and sign-changing outputs need an absolute tolerance.
  Avoid blanket `rtol` for every variable.
- Tolerances must be looser than the rounding used in the stored data.
- A missing input or expected-output file is a failure, not a skip.

## 5. Candidate test cases (to discuss before writing)

The unit tests already cover the shape/schema cases for the verify functions
(empty inputs, wrong years, gaps, NaN/inf, non-numeric values, missing/extra species,
non-World regions, duplicates, more than one experiment per input, missing index levels).

Other cases from the earlier plan, to discuss before writing any tests
(roadmap [W15][w15]):

| Area | Cases |
| --- | --- |
| Units | Convertible spellings/scales, carbon vs. CO2, nitrogen vs. gas mass, incompatible units, duplicates after conversion |
| Harmonisation | Discontinuity with history caught, with species-specific tolerances |
| Batch | Single input; many uniquely tagged inputs; repeated labels across inputs; mixed lengths |
| Ordering | Exactly one result per input in input order, including with parallel adapters |
| Output selection | Requested outputs present and exact; unsupported requests rejected before running |
| Identity | Input metadata retained; SCM vs. input `model` kept distinct; ensemble member IDs stable; output rows unique |
| Non-mutation | Inputs unchanged, including after a failed run |
| Isolation | Two adapter instances don't interfere; no global working directory/environment changes |
| Failure | Missing dependency/calibration/history; checksum mismatch; native non-zero exit; one adapter failing doesn't lose the others' results |
| Imports | Importing the package works without models installed |
