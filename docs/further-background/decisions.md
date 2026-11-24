# Decisions

Every decision, made and still to make.
The work that implements them is in the [roadmap](roadmap.md).

- **Active**: being worked on (around five at a time;
  don't add more without a need).
- **Decided**: made; links to where it is implemented.
- **Backlog**: decisions we don't want to forget, not being worked on yet.
  Nothing here is decided or next.

IDs never change and aren't re-used.
A IDs started as active decisions, B IDs in the backlog.
New decisions take the next free number in either series.

## Active

| ID | Decision | Current proposal |
| --- | --- | --- |
| A6 | CO2 emissions inputs across adapters | `Emissions\|CO2\|Fossil` is the canonical name of the CO2 emissions input for the idealised (CMIP-style) experiments, which take fossil CO2 only. The AR6 CO2-forcing-only scenario takes fossil and biosphere CO2 emissions (B17). The MAGICC AR6 implementation showed it isn't clear how adapters should handle these, e.g. MAGICC treats biosphere (land-use) CO2 emissions very differently from fossil ones. Decide one approach for all adapters. CICERO's fossil/biosphere, sulfur and VOC mappings then need aligning with the input definitions (roadmap W02) |
| A7 | Minimum outputs every adapter must support | To agree (Marit and Zeb). At the moment, adapters declare `supported_output_variables` and requests are checked against them. `STANDARD_OUTPUT_VARIABLES` (in `output_specs.py`) lists the outputs we expect to be common, but no adapter has to support any of them. Outputs are global (`World`) only |
| B04 | Annual time semantics, output windows and temperature baselines | Probably agreed, but kept as proposed in case we missed something. Proposed: inputs and outputs are annual means, labelled with the year they are the mean of. Scenario outputs cover the input's years only, adapters keep history internally (this is what "output windows" means). Temperatures are relative to each model's native reference, with no anchoring or hidden re-zeroing (re-baselining goes in separate post-processing, as it is trivial). Still to check: should inputs be annual means for everything? |
| B06 | Pre-industrial state and reference enforcement | Needs assessment/model owners. Tricky decision although numerical effects will probably not be that large |
| B16 | Which feedbacks should CO2-only runs include? | See [below](#b16) |
| B17 | Should CO2-forcing-only runs take fossil CO2 emissions only, or both fossil and biosphere CO2 emissions? | See [below](#b17) |
| B18 | When should simple climate models' chemistry (and other feedbacks) be on, and when off? | See [below](#b18) |
| B19 | What values should we use as pre-industrial (piControl)? | See [below](#b19) |
| B20 | How much do we rely on adapters to add what the inputs don't supply (history, natural forcing etc.), vs. checking it ourselves? | At the moment, adapters add these in line with each experiment's definition and we rely on the acceptance (and integration) tests to catch mistakes. Options for checking more ourselves: shared helpers which provide history and natural forcing, or requiring adapters to report what they used (e.g. as outputs, so shared integration tests can check the splice with history). See also roadmap W09 |
| A13 | If and how to support progress bars | Proposed: one shared progress display built on rich (optional extra), drawn only by the main process; adapters report progress to it rather than making their own bars. See [below](#a13) |

## Decided

| ID | Decision | Outcome | Date | Implemented in |
| --- | --- | --- | --- | --- |
| A1 | Interface for running experiments | One explicit `run_*` function per kind of experiment. Adapters implement one protocol per experiment structurally. No registry or factory | 2026-11-11 | [Architecture](architecture.md) |
| A2 | Output requests | Explicit per-call `output_specs`. Every experiment protocol requires adapters to declare the outputs they support. With checks on, each adapter's support is checked before calling it; unsupported requests are recorded as that adapter's failure and the other adapters still run. What `run_checks=False` turns off is A4 | 2026-11-11 | [Architecture](architecture.md#outputs-and-failures), `output_specs.py` |
| A5 | Species in the AR6/AR7 emissions inputs | AR6 scenarios: the 52 AR6 species, including Halon1202 (gcages naming), so AR6 scenario data (which includes it, all zero) can be used as it is. AR7 scenarios: drop Halon1202 (51 species). Still to confirm that gcages' AR6 workflow uses the same species (roadmap W07). The CO2 inputs are A6 | | `ar_scenarios/inputs.py` |
| A8 | Kinds of tests | Unit, integration (properties every adapter for an experiment must have) and acceptance tests. Acceptance data comes from the model team, not regression baselines we generate (MAGICC AR6 is the exception). Every adapter needs acceptance tests, and the tests marked for an adapter group give 100% coverage of its modules | 2026-11-11 | [Testing](testing.md) |
| A9 | AR7 scenario land-use/irrigation forcing | The formula in [architecture](architecture.md#scientific-conventions) | | `ar_scenarios` |
| A10 | Scientific configuration | Callers may select scientific configuration (calibration etc.) when constructing an adapter, both for their own advanced use and for testing (e.g. MAGICC AR6's `testing_only_n_members`). Keep it explicit and separate from operational settings; no hidden calibration selection or fallback. Record enough information to reproduce the selected configuration, not just the runner package version (B09). We will eventually want a simplified layer that forces default calibrations and scientific configuration, so non-expert users get easily reproducible results (B14) | 2026-11-11 | [Implementing an adapter](../how-to-guides/implementing-an-adapter.md#2-implement-the-protocol) |
| A11 | First models | MAGICC AR6 and CICERO AR7, implemented in parallel. This doesn't certify their scientific configuration or numerical output | 2026-11-11 | Roadmap W01 and W02 |
| A12 | Development tooling | The copier template's uv/Makefile setup, replacing Pixi. The rest of the template was adopted later (B15) | 2026-11-11 | `Makefile`, `pyproject.toml`, `.github/workflows` |
| B15 | Further template tooling | Adopted: the repository is generated from the copier template with Copier, so we have everything it provides, including requirements exports, testing with the lowest-direct and latest dependencies, release automation (bump, release and PyPI deploy workflows, towncrier changelog; PyPI uses trusted publishing, no release credentials in the repository), Copier updates and documentation hosting on Read the Docs | 2026-11-23 | `.copier-answers.yml`, `.github/workflows`, `.readthedocs.yaml` |

## Backlog

| ID | Decision | Notes |
| --- | --- | --- |
| A3 | Ensemble member identity | Adapters provide member IDs in each `EnsembleMemberResult` (plain strings for now); `as_df()` adds an `ensemble_member` level. Still to agree: one naming scheme (i.e. do we call this `ensemble_member` everywhere, something else? How do we handle model names when creating DataFrames) applied everywhere, enforced by tests |
| A4 | What `run_checks=False` turns off | When the checks are off, shared input and capability checks are skipped but the output count/type checks and container invariants remain. We need to decide our policy on this, and apply it to additional future output checks when implementing them. Also: whether adapters' own checks (e.g. of their resources' checksums) should follow `run_checks` |
| B02 | Distribution/import naming and release ownership | Proposed: keep `openscm-runner` / `openscm_runner`. All of core team should be able to do releases |
| B03 | Python floor, platforms and model versions | Proposed: Ideally follow copier template, but will be constrained by what the models support |
| B05 | Historical overlap and harmonisation tolerances | Proposed: follow gcages |
| B07 | Forcing exclusions during spin-up and the run (land-use/carbon-cycle interpretation) | Needs model owners, see B06 |
| B08 | Acceptance test tolerances and data access/licensing | Per model, approved by its owners |
| B09 | Public provenance surface | Caller-selected scientific configuration (A10) means the runner version alone is insufficient for now. In future we will want a mode of running that fixes these especially for non-expert users and for the standard projections, but for now we will keep it open for ease of implementation and transparency. Decide where model/configuration/resource identifiers are exposed; result containers are a candidate. |
| B10 | Combining results across adapters into one table | Needs A3 first |
| B11 | Parallelism across adapters | Left to adapters/experts to wrap themselves for now |
| B12 | Other experiments: AR7 anthropogenic-only, AR7 CO2-forcing-only, branching off CMIP historical | Add when there is a user. For the AR7 variants, decide based on conversations with the remaining carbon budget team about what they need (roadmap W06). Note that the scientific underpinning for these (via the remaining carbon budget assessment workflow) is becoming less clear the more Zeb thinks about it, so we definitely need to clarify |
| B13 | GWP and additional idealised land-use/natural modes | Deferred, takes care to define then are fiddly to do |
| B14 | A higher-level interface for novice users (e.g. strings in, results out) | Wait until we know the use case: no point building something based on a guess, especially as we won't use it ourselves at first (we'll initialise adapters ourselves). Our first higher-level function can be based on that experience |
| B21 | User documentation | What do we offer for getting started, running a specific model and running multiple models? And what should adapter implementers document about running their adapters? |

### A13

**If and how to support progress bars**

It is easy to make a mess of progress bars (and we have before),
so we want one common way of doing it which every adapter uses,
rather than each model team doing its own thing.

Criteria, in order of importance:

1. they work with parallel workers
   (including executors users give us, e.g. MAGICC AR6's `executor`)
1. bars which are updated at the same time don't overlap each other
1. they look OK

Plus: no required dependency (an optional extra, imported lazily),
easy to turn off, and no animation in CI or logs.

What we've seen:

- Old openscm-runner made tqdm a required dependency
  and created bars at several levels independently
  (one for the climate models in `run.py`,
  more inside the adapters and its parallel helper),
  with nothing coordinating them, so nested bars overwrote each other.
- pandas-openscm (`pandas_openscm.parallelisation`, also used by gcages)
  uses `tqdm.auto` as an optional dependency, injected as a `ProgressLike` factory,
  with an `Executor`.
  Bars are only drawn in the main process, one for submitting and one for results,
  so they don't overlap.
  But progress is only as fine as the futures (nothing from inside a worker)
  and, as its docstring says, nested bars aren't handled.
- continuous-timeseries uses `tqdm.auto` with `position=`,
  which is the fragile way of stopping tqdm bars overlapping.

Proposal:

- **Only the main process draws.**
  Workers never touch the terminal: progress comes back to the main process.
  This is what makes parallel workers work, whatever the library.
- **Progress comes back via the futures**, so it works with any
  `concurrent.futures.Executor` (a `multiprocessing.Manager` queue,
  the other common approach, doesn't work with e.g. dask's executors).
  So adapters need tasks fine enough to give useful progress.
  E.g. MAGICC AR6 currently splits each input into one chunk per worker,
  so with two workers a bar would jump from 0% to 50% to 100%.
  It would need to split into smaller chunks
  (cheap: setting up a run directory costs little compared to running MAGICC).
- **Adapters don't create bars.**
  They take a progress-reporting callback from us
  (e.g. "this many of this input's ensemble members are done") and call it.
  A shared helper in `openscm_runner` owns the display:
  one display with a task per adapter and input,
  which the `run_*` functions can set up and pass to each adapter.
  We enforce this with tests (e.g. adapters don't import a progress bar library)
  and say so in [implementing an adapter](../how-to-guides/implementing-an-adapter.md).
- **Use rich (`rich.progress`), not tqdm.**
  rich draws any number of tasks in one live display, rendered by one process,
  so bars don't overlap by design (criterion 2), and it looks good (criterion 3),
  about as close to uv's bars as we can get in Python
  (uv's come from Rust's indicatif, which we can't use).
  It works in notebooks and doesn't animate when output isn't a terminal.
  The costs are a few dependencies (e.g. pygments, markdown-it-py) and a slower import,
  both fine for an optional extra imported only when progress is asked for.

Why probably not tqdm, even though pandas-openscm, gcages
and continuous-timeseries use it:

- tqdm draws each bar independently.
  Several bars updating at once only avoid overlapping if you manage
  each bar's `position` by hand, which glitches in terminals
  (e.g. when bars finish or something else prints)
  and is ignored in notebooks (where each bar is a separate widget).
  This is criterion 2, and how we made a mess before.
- Drawing from worker processes needs tqdm's lock to be shared with the workers
  (`tqdm.set_lock` plus a pool `initializer`),
  which is awkward with the spawn start method,
  out of our hands with executors users give us (we don't create their pools)
  and doesn't work for notebook widgets.
  (With "only the main process draws" this matters less,
  but then tqdm has no advantage left beyond familiarity.)
- Consistency with our other packages matters less here:
  users don't configure the bars, they just turn them on or off,
  so it doesn't matter to them which library draws them.

Still to check (e.g. with a quick prototype before deciding):
rich's display with a spawn process pool and several simultaneous tasks,
in a terminal, in a notebook and in CI.

### B16

**Which feedbacks should CO2-only runs include, e.g. the CO2 from the oxidation of fossil CH4 or the ozone forcing due to temperature? (Part of the wider question in B18)**

The AR6 CO2-forcing-only input is CO2 emissions only and the MAGICC AR6 adapter holds everything else at pre-industrial (1750) for the whole run, with zero fossil CH4 emissions, so there is no CO2 from the oxidation of the scenario's (or history's) CH4 (only from the CH4 MAGICC's permafrost feedback releases). Clarify what the experiment should mean, then adjust the input definition if needed.

The same question applies to MAGICC's ozone forcing due to temperature (`OZDUETOTEMPERATURE_SCALE` times the warming, about -0.04 W/m^2/K): CMIP models with prescribed ozone wouldn't have it, CMIP models with interactive chemistry probably would. For now, the MAGICC AR6 CO2-only CMIP adapters turn it off (`NO_OZONE_DUE_TO_TEMPERATURE`). We might make the opposite choice, or offer both (a prescribed-ozone-like and an interactive-chemistry-like adapter), but that opens up a huge number of cases to support, so it's unlikely to be what we do. The same question applies to the other MAGICC AR6 CMIP adapters (e.g. the full concentration-driven ones), which include this forcing at the moment but should probably follow the same logic. At the moment the two conflict: the full concentration-driven adapters act like a model with interactive chemistry, the CO2-only concentration-driven adapters like a model with prescribed ozone. Deciding what we want is one thing, working out if and how MAGICC can do it is another (e.g. in the full adapters, tropospheric ozone forcing also responds to CH4 concentrations and ozone precursor emissions, so turning off the ozone forcing due to temperature wouldn't be enough to make them act like a model with prescribed ozone)

### B17

**Should CO2-forcing-only runs take fossil CO2 emissions only, or both fossil and biosphere CO2 emissions?**

At the moment the AR6 CO2-forcing-only input is both (`AR6_SCENARIO_CO2_EMISSIONS_VARIABLES`). It matters for MAGICC, which treats biosphere (land-use) CO2 emissions very differently from fossil ones. Quick test (MAGICC AR6, first 20 members, AIM/CGE 2.2 EN_NPi2020_900f, its total CO2 put all in fossil, 50:50 or all in biosphere): compared to the scenario's own split (cumulative 2015-2100: 1160 GtCO2 fossil, -62 GtCO2 biosphere), the median member's 2100 warming changes by +0.002 K (all fossil), -0.025 K (50:50) and -0.087 K (all biosphere), but some members change a lot (down to -0.93 K for 50:50 and -2.55 K for all biosphere, where CO2 falls to 179 ppm by 2100, below pre-industrial). Decide which emissions the experiment takes (and what happens to the other ones), then adjust the input definition if needed

### B18

**When should simple climate models' chemistry (and other feedbacks) be on, and when off?**

This applies to all the adapters, not just CO2-only runs (B16). Simple climate models generally don't have a concept of prescribed ozone: in effect, they all have interactive chemistry (or no chemistry). So the question of when that chemistry should be on and when it should be off pervades all the adapters. It mostly only bites for the CMIP-style adapters, because they're the ones where we might want to turn things off (the scenario adapters always want everything on). E.g. at the moment, the MAGICC AR6 full concentration-driven CMIP adapters act like a model with interactive chemistry, the CO2-only ones like a model with prescribed ozone (see B16). Decide what each experiment should do, then work out if and how each model can do it

### B19

**What values should we use as pre-industrial (piControl)?**

CMIP's guidance usually says something like 'repeat the 1850 values' (although it can be more complicated, e.g. for volcanic or solar forcing). RCMIP phase 3's protocol doesn't always follow that. We need to decide what we are trying to replicate. Where we currently make a choice (MAGICC AR6 CMIP adapters and their tests, compared with RCMIP phase 3, see `scripts/get-rcmip3-pre-industrial-values.py`): (1) CO2 emissions: the adapters use zero (as RCMIP phase 3's CMIP6 esm-piControl does, it has none for CMIP7), but the 1850 historical emissions aren't zero (fossil ~0.05 GtC/yr, AFOLU 0.50 (CMIP6) or 0.72 (CMIP7) GtC/yr); (2) aerosol and aerosol/ozone precursor emissions: the adapters hard-code each CMIP era's 1850 historical emissions from RCMIP phase 3 as the piControl emissions (`historical_emissions_1850`, for CMIP7 these are also its esm-piControl values), which differ between CMIP6 and CMIP7, e.g. NOx 20.2 (CMIP7) vs 13.5 (CMIP6) Mt NO2/yr, BC 2.81 vs 2.57 Mt/yr (there was an issue with CMIP6's NOx emissions, which explains part of the NOx difference); (3) natural forcing: the input is defined relative to piControl (zero in piControl), but RCMIP phase 3's natural ERF isn't zero in 1850 (e.g. volcanic 0.18 (CMIP6) or 0.21 (CMIP7) W/m^2) and CMIP's piControl uses averages (e.g. the CMIP6 1850-2014 mean volcanic ERF is 0.05 W/m^2 in RCMIP phase 3), so what zero means needs to be decided; (4) GHG emissions: the adapters hard-code each CMIP era's 1850 historical emissions from RCMIP phase 3 as the piControl emissions, which differ (e.g. CH3Cl 4554 vs 4268 kt/yr, CH3Br 112 vs 105 kt/yr, natural CF4 0.0145 vs 0.0101 kt/yr, and N2O 1232 vs 559 kt/yr in RCMIP phase 3, which looks like a difference in what is included), and piControl emissions need to be in balance with the piControl concentrations given each model's lifetimes (otherwise concentrations drift); (5) concentrations: RCMIP phase 3's CMIP7 piControl and CMIP6 historical 1850 values (it has no CMIP6 piControl concentrations), i.e. 'repeat 1850'; (6) land-use albedo forcing: zero at piControl (RCMIP phase 3's 1850 value relative to 1750 is -0.03 (CMIP6) or -0.04 (CMIP7) W/m^2), consistent with the concentrations, but worth confirming
