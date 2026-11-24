# Implementing an adapter

An adapter runs one kind of experiment with one model.
This page is the checklist for adding adapters for your model.
The interfaces are meant to be clear enough that, for the details,
we can mostly point you at the code.

Worked examples:

- MAGICC AR6:
  [`openscm_runner.adapters.magicc_ar6`][openscm_runner.adapters.magicc_ar6]
  (start with its module docstring, which describes its layers)
<!-- - CICERO-SCM: placeholder, to be done -->

## Before you start

We can take on a model (and keep it working) if it has:

1. a responsible scientific reviewer and a maintainable native API
1. reproducible inputs, member selection and accessible calibration/forcing data
1. a model team who can provide acceptance test data
1. a way to run in CI (ideally public pull request CI, so a public model is easiest)

## 1. Pick the experiments you support

Each kind of experiment has
an input definition (a type alias plus the `verify_*` function which defines the input data),
an adapter protocol (what you need to meet when you implement)
and a `run_*` function.
They live in one subpackage per group of experiments:

- [`ar_scenarios`][openscm_runner.ar_scenarios]:
  AR6 and AR7 scenarios (and their variants;
  which further AR7 variants to add is decision B12 [add cross-ref to decisions page])
- [`cmip_pre_industrial_branch`][openscm_runner.cmip_pre_industrial_branch]:
  CMIP-style experiments branching off CMIP6 or CMIP7 pre-industrial
- [`erf`][openscm_runner.erf]:
  ERF-driven experiments

The input definitions are in each subpackage's `inputs.py`,
the protocols and `run_*` functions in its `running.py`.
Implement the protocols for the experiments you support, you don't need to provide anything else.
If an experiment you need doesn't exist yet, talk to us first
(see the [roadmap](../further-background/roadmap.md)
and [decisions](../further-background/decisions.md)).

## 2. Implement the protocol

A protocol is satisfied structurally: no base class, no registration.
An adapter is a callable which takes a tuple of inputs
(each element is exactly one experiment to run) and an `output_specs`,
and declares the outputs it supports (`supported_output_variables`).
See the protocols for the exact signatures, e.g.
[`AdapterAR6Scenario`][openscm_runner.ar_scenarios.running.AdapterAR6Scenario],
and
[`MAGICCAR6AdapterAR6Scenario`][openscm_runner.adapters.magicc_ar6.ar_scenarios.MAGICCAR6AdapterAR6Scenario]
for an implementation.

The rules:

- **You don't have to rely on verifying inputs yourself.**
  The `run_*` functions verify the inputs before calling any adapter.
  You may offer your own checks for people who call your adapter directly
  (e.g. MAGICC AR6's `run_checks` configuration option).
- **Return exactly one output per input, in input order.**
  E.g. MAGICC AR6's
  [`run_experiments`][openscm_runner.adapters.magicc_ar6.base.run_experiments]
  runs all the inputs at once and returns one output per input, in order.
  To use all the workers even with one input,
  [`run_magicc`][openscm_runner.adapters.magicc_ar6.running.run_magicc]
  splits each input's ensemble into contiguous chunks
  and runs each chunk as a separate task.
  It keeps the tasks' results in the order the tasks were made
  (whatever order they finish in),
  so concatenating each input's chunks gives its members back in order.
- **One result per ensemble member, with an ID.**
  Each output is an
  [`OpenSCMRunnerOutput`][openscm_runner.output.OpenSCMRunnerOutput]
  which holds one `EnsembleMemberResult` per model run (i.e. per ensemble member).
  If a member fails, record its error
  (`EnsembleMemberResult.from_failure`) rather than raising,
  so the other members' results are kept too.
  Don't invent results for members which didn't run.
  The exact member naming scheme is still to be agreed (decision A3),
  but you should already have enough details to implement your adapter in full
  (any future changes needed to adopt decision A3 should be small).
- **Add everything the input doesn't supply**, e.g. history and natural forcing,
  in line with the experiment's definition (see the protocol's docstring).
  How much we rely on adapters for this, vs. checking it ourselves, is decision B20.
- **Make the scientific configuration explicit at construction**
  (model version, calibration etc.), separate from operational settings
  (paths, number of workers).
  Never silently fall back to a different calibration.
- **Don't read configuration from the environment implicitly.**
  Configuration is passed explicitly in Python.
  You can offer an opt-in way to read it from environment variables
  (e.g. `MAGICCAR6AdapterConfiguration.from_environment`, which the tests use),
  but nothing should read environment variables (or a `.env` file) behind the user's back.
- **Check the checksums of your resources** (calibration, history etc.)
  against expected values before running.
- **Keep imports cheap.** Importing `openscm_runner` must not import your model.
  Import your model's library only when your adapter is used,
  with a clear error if it isn't installed
  ([`openscm_runner.optional_dependencies`][openscm_runner.optional_dependencies]
  does this for you, e.g. see how MAGICC AR6's
  [`io`][openscm_runner.adapters.magicc_ar6.io] module uses it).
- **Don't change caller data or affect other adapters**.
  For example, run external executables in isolated temporary directories
  rather than in the user's home folder
  (and ideally also give the user a way to specify where to make the temporary directories,
  in case the default location is not a good choice for them).
  It's also polite to tell users that this will be required in your adapter docstrings.
  TODO: add this warning for MAGICC AR6

## 3. Outputs

Output support is work in progress.
At the moment, adapters declare what they support
and the `run_*` functions check each request against that before running the adapter
(see
[`openscm_runner.output_specs`][openscm_runner.output_specs]).
`STANDARD_OUTPUT_VARIABLES` (in the same module) lists the outputs we expect to be common,
so use those names where you can.
Outputs should be annual-means (decision B04) for the global-mean/total
(i.e. a region of `World`) only.
The minimum list of outputs every adapter must support is decision A7.

## 4. Parallelisation

Put in the parallelisation that suits your model,
ideally with sensible configuration options,
e.g. MAGICC AR6's `n_workers`
(see
[`MAGICCAR6AdapterConfiguration`][openscm_runner.adapters.magicc_ar6.base.MAGICCAR6AdapterConfiguration]
and
[`run_magicc`][openscm_runner.adapters.magicc_ar6.running.run_magicc]).
Ideally, also let people give you their own pool to run with,
e.g. MAGICC AR6's `executor` (any `concurrent.futures.Executor`,
used instead of the pool MAGICC AR6 would otherwise make for each call).
Then they can re-use one pool across calls and adapters
and use whichever library suits their set-up (e.g. dask on a cluster).
The `run_*` functions run adapters one after the other,
they don't parallelise anything for you
(users can add their own parallelisation as they wish).

Keep a serial mode (e.g. MAGICC AR6 with `n_workers=1`
runs everything in the calling process),
so people can do their own parallelisation around your adapter.

## 5. Tests

See [testing](../further-background/testing.md) for the details.
In short:

- **Acceptance tests are mandatory** for every adapter (every experiment you offer):
  you provide inputs and the outputs you expect your model to produce,
  we check that running through this package reproduces them.
  See the MAGICC AR6
  [acceptance tests](https://github.com/openscm/openscm-runner/tree/main/tests/acceptance/magicc-ar6)
  for an example.
  The full-ensemble acceptance test for the AR6 scenario adapter
  (`test_ar6_scenario_full_ensemble_matches_ar6`)
  compares with published AR6 data,
  and [its README](https://github.com/openscm/openscm-runner/blob/main/tests/test-data/ar6-scenarios/README.md)
  shows how to record where data comes from.
  Otherwise, we generate the MAGICC AR6 acceptance data in this repo
  to show how this can be done
  (see [the data README](https://github.com/openscm/openscm-runner/blob/main/tests/acceptance/magicc-ar6/data/README.md))
  (MAGICC AR6 is an exception in this respect,
  normally we want you to generate the data yourselves somewhere external
  so we have a 100% independent check of adapter behaviour).
  TODO: mark all the MAGICC AR6 adapters without acceptance tests with "DELETE BEFORE MERGING",
  then delete them before we make the PR
- Add your adapters to the shared integration tests for your experiments
  (e.g. [`tests/integration/test_erf_zero.py`](https://github.com/openscm/openscm-runner/blob/main/tests/integration/test_erf_zero.py)).
  Add your own unit and integration tests for what you know can go wrong
  with your model
  (e.g. [`tests/unit/magicc-ar6`](https://github.com/openscm/openscm-runner/tree/main/tests/unit/magicc-ar6)
  and [`tests/integration/magicc-ar6`](https://github.com/openscm/openscm-runner/tree/main/tests/integration/magicc-ar6)).
- Mark all your adapters' tests with a pytest marker for your adapter group
  (e.g. `magicc_ar6`, registered in `pyproject.toml`).
  When the tests that have this marker are run,
  they must give 100% coverage of your adapters' modules.
- Tests which need your model should fail if it isn't available (rather than skipping).

## 6. Packaging and CI

- Put your adapters in their own subpackage,
  `src/openscm_runner/adapters/<model>`,
  split by group of experiments if that helps
  (as MAGICC AR6 does, mirroring the experiment subpackages).
- Put your model's dependencies in an optional extra in `pyproject.toml`
  (e.g. the optional extra `magicc` group).
  TODO update name to magicc-ar6
- Add a make target and a CI job which run your marked tests
  and enforce their coverage
  (e.g. `make test-magicc-ar6` in the
  [Makefile](https://github.com/openscm/openscm-runner/blob/main/Makefile)
  and the `tests-magicc-ar6` job in
  [CI](https://github.com/openscm/openscm-runner/blob/main/.github/workflows/ci.yaml)),
  and exclude your marker from the general test run.
  If your model or its resources are licensed,
  discuss with the package maintainers how to run them in CI.
- Document your adapters in their docstrings:
  what they do, which scientific choices they make,
  and anything users need to know (e.g. where they differ from your model's usual setup).
  Instructions about how to document actually running your adapter are to come
  (decision B21).

## Definition of done

Each adapter:

- implements the protocol(s) it claims to support
- has acceptance tests with data from the model team
- passes the integration tests for its experiments
- returns exactly one output per input, in input order,
  with ensemble member IDs
- checks the checksums of its resources before running
- makes its scientific configuration explicit at construction
  and reproducible from its recorded settings and resource identities
  (operational paths alone are not scientific provenance)
- doesn't change caller data or affect other adapters
- is covered 100% by the tests marked for its adapter group
