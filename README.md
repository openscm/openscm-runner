# OpenSCM-Runner

<!---
Can use start-after and end-before directives in docs, see
https://myst-parser.readthedocs.io/en/latest/syntax/organising_content.html#inserting-other-documents-directly-into-the-current-document
-->

<!--- sec-begin-description -->

OpenSCM-Runner provides a unified API for running emissions scenarios with different simple climate models.

[![CI](https://github.com/openscm/openscm-runner/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/openscm/openscm-runner/actions/workflows/ci.yaml)
[![Coverage](https://codecov.io/gh/openscm/openscm-runner/branch/main/graph/badge.svg)](https://codecov.io/gh/openscm/openscm-runner)
[![Docs](https://readthedocs.org/projects/openscm-runner/badge/?version=latest)](https://openscm-runner.readthedocs.io)

**PyPI :**
[![PyPI](https://img.shields.io/pypi/v/openscm-runner.svg)](https://pypi.org/project/openscm-runner/)
[![PyPI: Supported Python versions](https://img.shields.io/pypi/pyversions/openscm-runner.svg)](https://pypi.org/project/openscm-runner/)
[![PyPI install](https://github.com/openscm/openscm-runner/actions/workflows/install.yaml/badge.svg?branch=main)](https://github.com/openscm/openscm-runner/actions/workflows/install.yaml)

**Other info :**
[![License](https://img.shields.io/github/license/openscm/openscm-runner.svg)](https://github.com/openscm/openscm-runner/blob/main/LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/openscm/openscm-runner.svg)](https://github.com/openscm/openscm-runner/commits/main)
[![Contributors](https://img.shields.io/github/contributors/openscm/openscm-runner.svg)](https://github.com/openscm/openscm-runner/graphs/contributors)

<!--- sec-end-description -->

Full documentation can be found at:
[openscm-runner.readthedocs.io](https://openscm-runner.readthedocs.io/en/latest/).
We recommend reading the docs there because the internal documentation links
don't render correctly on GitHub's viewer.

## Supported climate models and run modes

openscm-runner ships adapters for a small, fixed set of simple climate
models. Each adapter declares which driving modes it supports; the
high-level `openscm_runner.run.run` function takes a `mode` argument
(or, for the new list-form, reads the mode off each pre-constructed
adapter instance) and dispatches accordingly.

| Adapter | Model | Modes |
|---|---|---|
| `FaIR` | FaIR 1.6 | emissions-driven |
| `FaIRv2` | FaIR 2.x | emissions-driven, concentration-driven |
| `MAGICC7` | MAGICC7 | emissions-driven |
| `CiceroSCM` | CICERO-SCM 1.1.x (Fortran) | emissions-driven |
| `CiceroSCMPY` | CICERO-SCM 1.1.x (Python wrapper) | emissions-driven |
| `CICERO-SCM-PY2` | CICERO-SCM 2.x | emissions-driven, concentration-driven |

Mode is expressed via the `openscm_runner.RunMode` enum
(`EMISSIONS_DRIVEN`, `CONCENTRATION_DRIVEN`). The adapter raises
`NotImplementedError` if asked to run in a mode it does not declare
in its `supported_modes` attribute.

Adapters that ship with a native parameter distribution (FaIRv2's
Zenodo calibration, CICERO-SCM 2.x's `rcmip-march2026` bundle) expose
a `from_native_distribution` classmethod returning a fully-configured
instance. Adapters that don't have a published distribution are
configured with explicit per-cfg dicts the standard way.

Scenario inputs use the openscm-runner emissions naming convention;
the wrapper raises `ValueError` on unknown emissions variable names
(see `KNOWN_EMISSIONS_VARIABLES` and `check_variables_are_as_expected`
in the top-level namespace). Translation from other naming schemes
(IAMC, RCMIP, CMIP7 ScenarioMIP, AR6 CFC infilling) lives upstream of
the wrapper; see [`gcages`](https://github.com/openscm/gcages) for a
canonical translation table.

## Installation

<!--- sec-begin-installation -->

OpenSCM-Runner can be installed with conda or pip:

```bash
pip install openscm-runner
conda install -c conda-forge openscm-runner
```

### Optional extras

Each climate model adapter is gated behind its own pyproject extra. The
core install does not pull in any of them. Choose one or more of:

```bash
# To add notebook dependencies
pip install openscm-runner[notebooks]

# MAGICC (Fortran binary called via pymagicc)
pip install openscm-runner[magicc]

# FaIR 1.6 adapter (original)
pip install openscm-runner[fair]

# FaIR 2.x adapter
pip install openscm-runner[fair2]

# CICERO-SCM v1.1.x Python adapter
pip install openscm-runner[ciceroscmpy]

# CICERO-SCM v2.x Python adapter
pip install openscm-runner[ciceroscmpy2]

# All three legacy models in one go (FaIR 1.6 + MAGICC + CICEROSCM v1.1.x)
pip install openscm-runner[models]

# CICERO-SCM's Fortran binary requires no additional dependencies to be
# installed; it ships with the adapter package.
```

**Mutual exclusion: pick the major version that matches the adapter.**
`[fair]` and `[fair2]` install incompatible major versions of the same
`fair` PyPI package, and `[ciceroscmpy]` and `[ciceroscmpy2]` likewise
share the `ciceroscm` PyPI package. The pyproject extras leave both
options open (`fair >=1.6,<3`, `ciceroscm >=1.1,<3`); the adapter
`_compat` shims raise a clear `ImportError` at runtime if you select an
adapter whose major version is not the one you installed. Hard-pin
yourself if you need a particular minor:

```bash
pip install "openscm-runner[fair2]" "fair>=2.2,<3"
pip install "openscm-runner[ciceroscmpy2]" "ciceroscm>=2.1,<3"
```

```bash
# If you are installing with conda, we recommend
# installing the extras by hand because there is no stable
# solution yet (issue here: https://github.com/conda/conda/issues/7502)
```

<!--- sec-end-installation -->

## Programmatic API

```python
import openscm_runner.run
from openscm_runner import RunMode
from openscm_runner.adapters import FAIR2

# Dict form (back-compat): registry lookup + per-model cfg list
result = openscm_runner.run.run(
    climate_models_cfgs={"FaIRv2": [{"native_calibration": "/path/to/bundle"}]},
    scenarios=my_scmrun,
    output_variables=("Surface Air Temperature Change",),
    mode=RunMode.EMISSIONS_DRIVEN,
)

# List form: pre-constructed adapter instances. Useful for native
# parameter bundles where the dict form is awkward.
fair2 = FAIR2.from_native_distribution(
    "/path/to/calibration_bundle",
    mode=RunMode.EMISSIONS_DRIVEN,
    output_variables=("Surface Air Temperature Change",),
)
result = openscm_runner.run.run([fair2], scenarios=my_scmrun)

# Concentration-driven mode: same construction shape, different
# `mode=` and the scenarios DataFrame should carry
# `Atmospheric Concentrations|*` rows for the species you want to
# drive. See the per-adapter `_run` docstring for the calibration-
# directory layout each adapter expects.
fair2_cd = FAIR2.from_native_distribution(
    "/path/to/calibration_bundle",
    mode=RunMode.CONCENTRATION_DRIVEN,
    output_variables=("Surface Air Temperature Change",),
)
result_cd = openscm_runner.run.run([fair2_cd], scenarios=my_conc_scmrun)
```

## For developers

<!--- sec-begin-installation-dev -->

For development, we rely on [poetry](https://python-poetry.org) for all our
dependency management. To get started, you will need to make sure that poetry
is installed
([instructions here](https://python-poetry.org/docs/#installing-with-the-official-installer),
we found that pipx and pip worked better to install on a Mac).

For all of work, we use our `Makefile`.
You can read the instructions out and run the commands by hand if you wish,
but we generally discourage this because it can be error prone.
In order to create your environment, run `make virtual-environment`.

If there are any issues, the messages from the `Makefile` should guide you
through. If not, please raise an issue in the [issue tracker][issue_tracker].

For the rest of our developer docs, please see [](development-reference).

<!--- sec-end-installation-dev -->

[issue_tracker]: https://github.com/openscm/openscm-runner/issues
