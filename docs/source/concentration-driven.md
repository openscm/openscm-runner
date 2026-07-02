# Concentration-driven runs

OpenSCM-Runner can drive its three modern adapters — **MAGICC7**, **FaIR2**
and **CICEROSCMPY2** — from prescribed atmospheric concentrations instead of
emissions, via {class}`openscm_runner.RunMode`:

```python
from openscm_runner import RunMode, run

run(
    climate_models_cfgs={"MAGICC7": ({"core_climatesensitivity": 3,
                                      "rcmip3_bundle_path": "/path/to/rcmip3"},)},
    scenarios=scenarios,            # may carry ``Atmospheric Concentrations|*`` rows
    output_variables=("Surface Air Temperature Change",
                      "Atmospheric Concentrations|CO2"),
    mode=RunMode.CONCENTRATION_DRIVEN,
)
```

All three adapters share the same contract:

- **Inputs.** Concentrations are supplied as ``Atmospheric Concentrations|<species>``
  rows in the scenarios DataFrame, overlaid year-by-year (user wins) on a
  baseline loaded from the canonical RCMIP Phase 3 Zenodo bundle (record
  `20430630`). Species the user does not supply fall back to the baseline.
- **`rcmip3_bundle_path`.** Required on the cfg for concentration-driven runs,
  so the baseline is reproducible across machines.
- **Outputs.** Each adapter can return ``Atmospheric Concentrations|<species>``
  for the driven species, so you can check that what comes out matches what was
  prescribed.

## Capability matrix

| | **MAGICC7** | **FaIR2** | **CICEROSCMPY2** |
|---|---|---|---|
| CO2 / CH4 / N2O | ✅ | ✅ | ✅ |
| F-gases (PFCs / HFCs / SF6 / NF3) | ✅ | ✅ | ✅ |
| Montreal halocarbons | ✅ | ✅ | ✅ |
| Requires `rcmip3_bundle_path` | ✅ | ✅ (or conc rows in the scenario) | ✅ |
| Hybrid baseline + user overlay | ✅ | ✅ | ✅ |
| Returns concentrations as output | ✅ | ✅ | ✅ |
| **Mode scoping** | per-scenario, per-gas (WMGHGs) / per-group (F-gas, MHalo) | per-calibration instance (auto-detected) + protocol mixed-mode | adapter-wide global flag |
| Per-gas mixed mode | WMGHGs independent; F-gas & MHalo all-or-nothing within group | protocol-strict only (CO2 emissions + non-CO2 concentration) | ❌ all-or-nothing |
| Per-scenario mixing within a batch | ✅ (no batch-consistency constraint) | batch-intersection rule applies in mixed-mode | ❌ global |

**Species coverage is at parity:** all three drive the full WMGHG +
F-gas + Montreal-halocarbon set.

## Where the adapters differ

The remaining differences are in *how finely modes can be mixed*, and they
follow each model's native interface rather than any missing feature:

- **MAGICC7** writes a separate config and ``CONC.IN`` files per
  ``(scenario, model)``, so the decision is genuinely per-scenario and, for
  CO2/CH4/N2O, per-gas. The F-gas and Montreal-halocarbon groups each share a
  single ``*_SWITCHFROMCONC2EMIS_YEAR`` flag, so within a group driving is
  all-or-nothing: the writer fills the whole group from the baseline and warns
  on any unexpected empty slot. ``HALON1202`` has no RCMIP3 trajectory and
  falls back to MAGICC's built-in default.
- **FaIR2** uses a per-species ``input_mode`` that is shared across the whole
  FaIR *instance* (all scenarios in a calibration). It therefore keeps a
  batch-consistency rule: its protocol mixed-mode (CO2 emissions-driven,
  non-CO2 concentration-driven) only engages when every scenario in the batch
  supplies the concentrations.
- **CICEROSCMPY2** exposes a single adapter-level ``conc_run`` flag that
  applies uniformly to every scenario and species in the call.

```{note}
Because MAGICC7 drives each scenario independently, it has **no**
batch-consistency requirement: a gas can be concentration-driven in one
scenario and emissions-driven in another within the same batch. This is
intentionally more permissive than FaIR2's shared-instance constraint.
```
