# Idealised experiments and the non-conc-species baseline

Concentration-driven runs (`RunMode.CONCENTRATION_DRIVEN`) only drive the species
you supply as `Atmospheric Concentrations|*`. **Every other species still needs an
emissions input** — aerosol precursors (Sulfur, BC, OC, …), ozone precursors (NOx,
CO, VOC, NH3), and any greenhouse gas you did not supply a concentration for. What
each adapter does for those "non-conc" species differs, and it matters most for the
**idealised CMIP experiments** (`abrupt-4xCO2`, `1pctCO2`, `esm-flat10*`), where the
intent is "nothing but CO2 changes; everything else stays at pre-industrial (PI)".

## Per-adapter behaviour

| Adapter | Non-conc species (general conc-driven) | Idealised experiments |
|---|---|---|
| **MAGICC7** | Requires `Emissions\|*` for species it cannot concentration-drive (written to the SCEN7 file). Missing species fall back to MAGICC's built-in defaults. | No idealised auto-detection — you must supply the non-CO2 emissions you want (e.g. an `esm-piControl` overlay). |
| **FaIR2** | Non-idealised scenarios inherit the canonical RCMIP3 emissions baseline (forward-filled from the last historical year). | Idealised = `protocol_natural_forcing="off"` **and** `protocol_land_use_forcing="constant_zero"` (or a name match like `abrupt-*` / `1pctCO2*`). Natural (solar/volcanic) and land-use forcing are zeroed, and non-CO2 emissions-mode species are **held at their `baseline_emissions`** so their PI forcing is ~0. |
| **CICEROSCMPY2** | Non-supplied species inherit the `historical_em_file` (emissions) / `historical_conc_file` (concentrations) baseline. | Non-supplied emissions are zeroed (`zero_unsupplied`); non-supplied concentrations are held at PI (`hold_unsupplied_at_pi`). |

```{note}
FaIR2 holds idealised non-CO2 species at `baseline_emissions` rather than at zero
emissions. FaIR evaluates emissions-driven forcing (aerosols especially) *relative
to* `baseline_emissions`, so zeroing emissions would leave a constant spurious ERF
(~1 W/m² of aerosol forcing) instead of the intended PI zero.
```

## Recommended pattern: supply the PI baseline explicitly

The per-adapter idealised defaults differ, and MAGICC7 does no auto-detection at all.
For reproducible cross-model idealised runs, **supply the non-CO2 baseline you want
explicitly** rather than relying on per-adapter behaviour. The canonical choice is the
`esm-piControl` emissions from the RCMIP3 bundle:

```python
import scmdata
from openscm_runner import RunMode, run
from openscm_runner.io import load_rcmip3_emissions, canonicalise_rcmip3_variable

# 1. Idealised conc-driven scenario (e.g. abrupt-4xCO2 CO2 concentrations).
conc_scen = ...  # ScmRun with Atmospheric Concentrations|* rows

# 2. esm-piControl emissions for the non-CO2 species, relabelled onto the
#    idealised scenario name. Drop CO2 sources (CO2 is concentration-driven).
pi = load_rcmip3_emissions(RCMIP3_BUNDLE, scenarios=["esm-piControl"])
pi["Variable"] = pi["Variable"].map(canonicalise_rcmip3_variable)
pi = pi[~pi["Variable"].str.startswith("Emissions|CO2")]
pi_overlay = relabel_scenario(pi, "abrupt-4xCO2")  # set scenario meta + protocol_* flags

# 3. Merge and dispatch.
scenarios = scmdata.run_append([conc_scen, pi_overlay])
run(climate_models_cfgs=..., scenarios=scenarios,
    output_variables=("Effective Radiative Forcing",),
    mode=RunMode.CONCENTRATION_DRIVEN)
```

For FaIR2 and CICEROSCMPY2 the explicit overlay reproduces what their idealised
auto-detection already does; for MAGICC7 it is the only way to get correct PI
behaviour for the non-CO2 species.
```{note}
Supplying a user `Emissions|*` overlay for an idealised scenario also exercises the
FaIR2 emissions splice; that path is fixed so an empty RCMIP3 baseline (which every
idealised scenario has) no longer errors.
```
