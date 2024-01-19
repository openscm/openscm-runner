# OpenSCM-Runner

TODO:

- Change to using pytest-regressions for handling expected values
  - next PR as too hard to do with confidence when there are so many moving parts
- Update notebook tests i.e. just make sure docs building covers them
- TODO: work out how to handle package data
- get version to include dirty/commits when being created
- fix deprecated API warning in scmdata for both seaborn and pandas (seaborn b/c of "ci" usage, pandas because of something in concat, run the FaIR notebook to see them both)
- add PHONY to help in copier
- add conda support via copier somewhere (might not need to be too complicated though as the only thing you really need to test is installation and then you just add the badges, the rest is just handled by conda-forge)
- add AUTHORS in copier
- fill out contributing docs more fully in copier
- add sidebar back into docs in copier
- add feature request issue template to copier
- add feature-request label to both GitHub and GitLab orgs (if they don't exist, otherwise update feature request template to match existing name)
- add contributor docs about how to contribute in different ways to copier, e.g.
  - tutorials
  - docs
  - bug reports
  - bug fixes
  - feature requests
  - pull requests
- add contributor info re workflows
  - only push to your own branches (semi-enforced by GitHub's forking workflow but a good reminder)
  - tools we use
  - small MRs

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

## Installation

<!--- sec-begin-installation -->

OpenSCM-Runner can be installed with conda or pip:

```bash
pip install openscm-runner
conda install -c conda-forge openscm-runner
```

Additional dependencies can be installed using

```bash
# To add notebook dependencies
pip install openscm-runner[notebooks]

# To add dependencies for all models
pip install openscm-runner[models]

# To add dependencies for MAGICC
pip install openscm-runner[magicc]

# To add dependencies for FaIR
pip install openscm-runner[fair]

# CICERO-SCM's Fortran binary requires no additional dependencies to be
# installed

# To add dependencies for CICERO-SCM's Python port
pip install openscm-runner[ciceroscmpy]

# If you are installing with conda, we recommend
# installing the extras by hand because there is no stable
# solution yet (issue here: https://github.com/conda/conda/issues/7502)
```

<!--- sec-end-installation -->

### For developers

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
