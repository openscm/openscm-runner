# Architecture

The code is the reference: start with the
[package docstring][openscm_runner].
This page gives the overview and the reasoning behind it.
To add a model, see [implementing an adapter](../how-to-guides/implementing-an-adapter.md).

## Goals and non-goals

Goals:

- One explicit `run_*` function per kind of experiment
  (e.g. [`run_ar7_scenarios`][openscm_runner.ar_scenarios.running.run_ar7_scenarios]).
  There are lots of ways to run these experiments and it is easy to get them wrong,
  so the differences must be explicit at the entry points, not assumed.
- Clear protocols, so a model team knows exactly what to implement.
- Make scientific behaviour discoverable before a run
  (experiment, supported outputs, configuration).
- Callers may select scientific configuration (calibration etc.)
  when constructing an adapter.
  Keep this choice explicit and separate from operational settings
  (resource locations, worker counts).
  Later, we will likely want a layer for non-expert users
  which locks runs to a default scientific configuration (decision [B14][b14]).
- Keep the package importable without any model installed
  (cheap installation if desired and imports without surprises).
  Adapters import their model's dependencies lazily
  (see [openscm_runner.optional_dependencies][]),
  so importing [`openscm_runner`][openscm_runner] never requires them,
  they are only needed if the adapter is actually used.
- Shared helpers (validation, names, units, test helpers) are available
  to adapter implementers, but not imposed.
  There is no execution engine or inheritance hierarchy.
- Errors are early, contextual and testable; requests are never silently dropped.

Non-goals:

- A general-purpose config-dictionary API (as v0.13 and before had).
- Calibration fitting, scenario harmonisation and infilling
  (they belong in other packages, e.g. gcages, aneris, silicone).
- A workflow scheduler, a distributed execution framework or plugin discovery.
- Combining outputs from different models into one table,
  or statistics across models (needs a design for identifying models
  and ensemble members first, decision [B10][b10],
  and is generally application specific).

## Layers

```text
Applications (e.g. assessment workflows)
    prepare inputs, create adapters, combine results
                         |
run_* functions: verify inputs once, run each adapter, return RunResults
input definitions: type alias + verify_* function per kind of input
                         |
Adapters: implement one protocol each (model-specific)
                         |
Model library or isolated external executable
```

For each kind of experiment there is:

- a type alias for the input (e.g. `AR7Scenario`)
- a `verify_*` function which defines the input's shape
  (e.g. [`verify_ar7_scenarios`][openscm_runner.ar_scenarios.inputs.verify_ar7_scenarios]).
  Data-based type hinting isn't a thing, so the verify function is the definition.
- an adapter protocol (e.g. `AdapterAR7Scenario`),
  implemented structurally (no inheritance needed)
- a `run_*` function (e.g. [`run_ar7_scenarios`][openscm_runner.ar_scenarios.running.run_ar7_scenarios]), which is what users call.
  It verifies the inputs, then runs each adapter.

Users create the adapters they want and pass them in.
There is no registry or factory:
we don't have a use case which would let us design one well yet
(decision [A1][a1]; a higher-level interface for novice users is decision [B14][b14]).
Expert users can call adapters directly
(e.g. to wrap them in their own parallel set-up)
and call the `verify_*` functions themselves.

mypy can catch some mistakes, e.g. passing an ERF adapter to [`run_ar7_scenarios`][openscm_runner.ar_scenarios.running.run_ar7_scenarios],
because each protocol uses a different argument name for its input
and the `run_*` functions call adapters by keyword.
It can't tell the CMIP6 and CMIP7 variants of the same experiment apart.
We accept this.

Options considered and not chosen:

- Wrapping a model core in a shared checked adapter,
  built by a `make_...` function per experiment.
  Every adapter then had to know about the wrapper,
  which was lots of indirection for what is really
  "call verify before calling the model".
- One callable protocol with experiment names as data.
  Loses the explicit entry points and drifts back towards config dictionaries.
- One abstract base class per model with a method per experiment.
  Forces every model to implement (or stub) every experiment.

## Experiments

See the experiment subpackages
(`ar_scenarios`, `cmip_pre_industrial_branch`, `erf`)
for the full definitions.

| Experiment | Input | Start year |
| --- | --- | --- |
| AR7 scenario | AR7 scenario emissions (all other inputs come from the adapter) | 2023 (add decision cross-ref, this is TBD) |
| AR6 scenario, plus anthropogenic-only | As above | 2015 |
| AR6 scenario, CO2-forcing-only (definition under discussion: [B16][b16], [B17][b17]) | Fossil and biosphere CO2 emissions | 2015 |
| CO2 concentration-driven, from CMIP7 or CMIP6 pre-industrial | CO2 concentrations | 1850 |
| Concentration-driven, from CMIP7 or CMIP6 pre-industrial | GHG concentrations, natural forcing, aerosol and ozone precursor emissions | 1850 |
| CO2 emission-driven, from CMIP7 or CMIP6 pre-industrial | Fossil CO2 emissions (no land-use emissions, these are meant to mirror idealised runs with land-use forcing off) | 1850 |
| esm-style, from CMIP7 or CMIP6 pre-industrial | CO2 emissions, other GHG concentrations, natural forcing, aerosol and ozone precursor emissions | 1850 |
| esm-allGHG-style, from CMIP7 or CMIP6 pre-industrial | Emissions of all GHGs, natural forcing, aerosol and ozone precursor emissions | 1850 |
| ERF from equilibrium | Total ERF | Any |

For the experiments branching off CMIP pre-industrial,
some elements are still under discussion,
e.g. what the pre-industrial values are ([B06][b06], [B19][b19]),
which forcings are excluded ([B07][b07]),
which feedbacks and chemistry are on ([B16][b16], [B18][b18])
and how CO2 emissions inputs are handled ([A6][a6]).

Not written yet:
an experiment starting in 1750,
experiments branching off CMIP historical runs,
AR7 anthropogenic-only and CO2-forcing-only scenarios (decision [B12][b12]).

## Inputs

Each input's associated `verify_*` function defines its shape,
so new experiments can make different choices.
Many of the current experiments share common rules
(see [`openscm_runner.verification.verify_wide_timeseries_inputs`][openscm_runner.verification.verify_wide_timeseries_inputs]).

All problems are reported together in one [`InvalidInputError`][openscm_runner.errors.InvalidInputError].
Units aren't checked yet (planned: openscm-units, roadmap [W04][w04]).

## Outputs and failures

The `run_*` functions return a [`RunResults`][openscm_runner.output.RunResults] container:

- [`RunResults`][openscm_runner.output.RunResults]: one [`AdapterRunResult`][openscm_runner.output.AdapterRunResult] per adapter, in adapter order
- [`AdapterRunResult`][openscm_runner.output.AdapterRunResult]: the adapter's outputs (one [`OpenSCMRunnerOutput`][openscm_runner.output.OpenSCMRunnerOutput] per input,
  in input order), or its error if it failed as a whole
- [`OpenSCMRunnerOutput`][openscm_runner.output.OpenSCMRunnerOutput]: one [`EnsembleMemberResult`][openscm_runner.output.EnsembleMemberResult] per ensemble member,
  each holding that member's data or its error.
  `as_df()` combines the members, with an `ensemble_member` index level.

There are two ways for things to go wrong:

- an adapter fails as a whole (e.g. it raises),
  so it has no outputs, only an error
  (`has_outputs` on [`AdapterRunResult`][openscm_runner.output.AdapterRunResult],
  `all_have_outputs` and `without_outputs` on [`RunResults`][openscm_runner.output.RunResults])
- an adapter returns outputs, but some of their ensemble members failed.

`all_succeeded`, `failures` and `raise_if_any_failed()` cover both,
at every level, so `results.raise_if_any_failed()` checks everything.

There are dedicated accessors which raise if anything failed,
so failures can't be silently ignored.
We recommend using them.

Output requests are an explicit per-call `output_specs` argument.
Adapters declare `supported_output_variables`.
With checks on, an unsupported request is recorded as [`UnsupportedOutputError`][openscm_runner.errors.UnsupportedOutputError]
for that adapter without calling it; other adapters still run.
Whatever `run_checks` is, the `run_*` functions check each adapter
returned a tuple of one [`OpenSCMRunnerOutput`][openscm_runner.output.OpenSCMRunnerOutput] per input
(otherwise [`AdapterOutputError`][openscm_runner.output.AdapterOutputError]).
`run_checks=False` skips the input and output-request checks.
What else should be checked, and when, is still open (decision [A4][a4]).

## Scientific conventions

Proposed, probably agreed, but not yet decided in case we missed something
(decision [B04][b04]):

- Time axis: inputs and outputs are annual means,
  labelled with the year they are the mean of
  (still to check: should inputs be annual means for everything?).
  Scenario outputs cover the input's years only;
  adapters keep history internally.
- Temperature baseline: each model's native reference,
  no anchoring or hidden re-zeroing.

Decided:

- AR7 scenario land-use/irrigation forcing (decision [A9][a9]):
  `(LAND_USE_ALBEDO_ERF + IRRIGATION_ERF) *
  (cumulative_AFOLU(year) - ref_value) / scaling_value` W/m^2,
  with the AR7 FOD defaults `LAND_USE_ALBEDO_ERF = -0.11`
  and `IRRIGATION_ERF = 0.00` W/m^2,
  cumulative AFOLU emissions accumulated annually (inclusive), no clipping,
  `ref_value` initially `cumulative_AFOLU(1750)`
  from the CMIP7 historical AFOLU CO2 emissions
  and `scaling_value` initially `cumulative_AFOLU(2023) - cumulative_AFOLU(1750)`
  from the CMIP7 historical AFOLU CO2 emissions.

Other scientific choices are still open, see [decisions](decisions.md)
(e.g. [B05][b05]-[B07][b07], [B16][b16]-[B19][b19]).

## Packaging

One package (`pip install openscm-runner`), with an optional extra per model.
Model-specific code stays out of shared code:
each model gets its own subpackage of [`openscm_runner.adapters`][openscm_runner.adapters]
(see [implementing an adapter](../how-to-guides/implementing-an-adapter.md#6-packaging-and-ci)).
