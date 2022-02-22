Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_, and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

The changes listed in this file are categorised as follows:

    - Added: new features
    - Changed: changes in existing functionality
    - Deprecated: soon-to-be removed features
    - Removed: now removed features
    - Fixed: any bug fixes
    - Security: in case of vulnerabilities.

v0.9.3 - 2022-01-19
-------------------

Fixed
~~~~~

- (`#57 <https://github.com/openscm/openscm-runner/pull/57>`_) Updated CICERO-SCM fortran binary which confused OHC and OHC down to 700 meters in output and added missing components to radiative imbalance.

v0.9.2 - 2021-12-23
-------------------

Added
~~~~~

- (`#59 <https://github.com/openscm/openscm-runner/pull/59>`_) Conda install instructions


Changed
~~~~~~~

- (`#58 <https://github.com/openscm/openscm-runner/pull/58>`_) Update README for FaIR conda install

Fixed
~~~~~

- (`#61 <https://github.com/openscm/openscm-runner/pull/61>`_) Packaging now uses setuptools-scm and hence includes all required files in source distributions (which should also fix the conda distribution)

v0.9.1 - 2021-09-23
-------------------

Fixed
~~~~~

- (`#52 <https://github.com/openscm/openscm-runner/pull/52>`_) Fixed CICERO-SCM bugs with converting halon units and handling of very long scenario names

v0.9.0 - 2021-09-07
-------------------

Changed
~~~~~~~

- (`#55 <https://github.com/openscm/openscm-runner/pull/55>`_) Require openscm-units >= 0.5.0

v0.8.1 - 2021-08-13
-------------------

Changed
~~~~~~~

- (`#54 <https://github.com/openscm/openscm-runner/pull/54>`_) Made model dependencies optionally installable (allows conda package to be made)

v0.7.2 - 2021-07-22
-------------------

Changed
~~~~~~~

- (`#53 <https://github.com/openscm/openscm-runner/pull/53>`_) Loosened requirements and updated CI to run jobs in parallel

v0.7.1 - 2021-07-09
-------------------

Added
~~~~~

- Include LICENSE, CHANGELOG and README in distribution

v0.7.0 - 2021-07-09
-------------------

Added
~~~~~

- (`#24 <https://github.com/openscm/openscm-runner/pull/24>`_) Adapter for the CICERO-SCM model (https://doi.org/10.1088/1748-9326/aa5b0a), see ``openscm_runner.adapters.CICEROSCM``

v0.6.0 - 2021-04-13
-------------------

Changed
~~~~~~~

- (`#50 <https://github.com/openscm/openscm-runner/pull/50>`_) Changed FaIR heat uptake units to be "W/m^2" rather than "ZJ/yr"
- (`#47 <https://github.com/openscm/openscm-runner/pull/47>`_) Moved ``openscm_runner.adapters.magicc7._parallel_process`` to ``openscm_runner.adapters.utils._parallel_process``
- (`#47 <https://github.com/openscm/openscm-runner/pull/47>`_) Added CI for Python3.9 and dropped required code coverage to 90%.
- (`#46 <https://github.com/openscm/openscm-runner/pull/46>`_) Use `pytest markers <https://docs.pytest.org/en/stable/example/markers.html>`_ for marking tests which rely on MAGICC rather than hack fixture solution
- (`#45 <https://github.com/openscm/openscm-runner/pull/45>`_) Update regression tests so they can be more easily updated
- (`#44 <https://github.com/openscm/openscm-runner/pull/44>`_) Updated tests to using MAGICCv7.5.1

v0.5.1 - 2021-02-27
-------------------

Changed
~~~~~~~

- (`#43 <https://github.com/openscm/openscm-runner/pull/43>`_) Add ability to run FaIR in parallel

Fixed
~~~~~

- (`#40 <https://github.com/openscm/openscm-runner/pull/40>`_) Report correct index from FaIR as the anthropogenic total ERF

v0.5.0 - 2021-02-24
-------------------

Changed
~~~~~~~

- (`#41 <https://github.com/openscm/openscm-runner/pull/41>`_) Use consistent setting across all progress bars
- (`#38 <https://github.com/openscm/openscm-runner/pull/38>`_) Updated scmdata requirements to handle change to openscm-units
- (`#31 <https://github.com/openscm/openscm-runner/pull/31>`_) Unified key variable naming across MAGICC and FaIR

Fixed
~~~~~

- (`#39 <https://github.com/openscm/openscm-runner/pull/39>`_) Include parameter name in the warning message emitted when MAGICC's output config doesn't match the input config specified via OpenSCM-Runner
- (`#36 <https://github.com/openscm/openscm-runner/pull/36>`_) Hotfix CI after pandas 1.1.5 broke pylint
- (`#37 <https://github.com/openscm/openscm-runner/pull/33>`_) Ensure FaIR ignores emissions input in scenarios not handled by FaIR, e.g. total CO2

v0.4.4 - 2020-11-12
-------------------

Added
~~~~~

- (`#27 <https://github.com/openscm/openscm-runner/pull/27>`_) Test that installation includes required package data

Fixed
~~~~~

- (`#28 <https://github.com/openscm/openscm-runner/pull/28>`_) Minor smoothing for going from climate-assessment to openscm-runner to FaIR 1.6

v0.4.3 - 2020-10-14
-------------------

Fixed
~~~~~

- (`#26 <https://github.com/openscm/openscm-runner/pull/26>`_) Include csv files needed for running FaIR 1.6 with CMIP6 setup

v0.4.2 - 2020-10-13
-------------------

Changed
~~~~~~~

- (`#21 <https://github.com/openscm/openscm-runner/pull/21>`_) Added flexible start date for FaIR and FaIR's scmdata to emissions converter

v0.4.1 - 2020-10-06
-------------------

Added
~~~~~

- (`#23 <https://github.com/openscm/openscm-runner/pull/23>`_) Test that MAGICC's carbon cycle output can be used with MAGICCv7.4.2.
- (`#22 <https://github.com/openscm/openscm-runner/pull/22>`_) ``out_config`` argument to :func:`openscm_runner.run`, which allows the user to specify model configuration to include in the output's metadata.

v0.4.0 - 2020-09-24
-------------------

Added
~~~~~

- (`#18 <https://github.com/openscm/openscm-runner/pull/18>`_) Flexible end date for FaIR
- (`#17 <https://github.com/openscm/openscm-runner/pull/17>`_) Support for scmdata >= 0.7.1

Changed
~~~~~~~

- (`#19 <https://github.com/openscm/openscm-runner/pull/19>`_) Configuration is now handled using ``openscm_runner.settings`` providing support for environment variables and dotenv files

Fixed
~~~~~

- (`#20 <https://github.com/openscm/openscm-runner/pull/20>`_) Update bandit configuration

v0.3.1 - 2020-09-03
-------------------

Changed
~~~~~~~

- (`#14 <https://github.com/openscm/openscm-runner/pull/14>`_) Added in direct aerosol forcing by species in FaIR

v0.3.0 - 2020-08-26
-------------------

Changed
~~~~~~~

- (`#13 <https://github.com/openscm/openscm-runner/pull/13>`_) Renamed ``openscm_runner.adapters.fair`` to ``openscm_runner.adapters.fair_adapter`` and ``openscm_runner.adapters.fair.fair`` to ``openscm_runner.adapters.fair_adapter.fair_adapter`` to avoid a namespace collision with the source ``fair`` package

v0.2.0 - 2020-08-25
-------------------

Added
~~~~~

- (`#12 <https://github.com/openscm/openscm-runner/pull/12>`_) FaIR 1.6.0 adapter

Fixed
~~~~~

- (`#11 <https://github.com/openscm/openscm-runner/pull/11>`_) MAGICC adapter so passed in emissions are followed (previously non-CO2 always followed SSP245)

v0.1.2 - 2020-07-31
-------------------

Changed
~~~~~~~

- (`#10 <https://github.com/openscm/openscm-runner/pull/10>`_) Upgrade to ``scmdata>=0.6.2`` so that package can be installed

v0.1.1 - 2020-07-22
-------------------

Changed
~~~~~~~

- (`#9 <https://github.com/openscm/openscm-runner/pull/9>`_) Remove unnecessary conversion to IamDataFrame when running MAGICC7 and clarify :meth:`adapters.base._Adapter.run` interface

v0.1.0 - 2020-07-07
-------------------

Added
~~~~~

- (`#7 <https://github.com/openscm/openscm-runner/pull/7>`_) Hotfix requirements and tests
- (`#2 <https://github.com/openscm/openscm-runner/pull/2>`_) Add MAGICC7 adapter (also provides basis for all other adapters)
- (`#4 <https://github.com/openscm/openscm-runner/pull/4>`_) Hot fix initial setup
- (`#1 <https://github.com/openscm/openscm-runner/pull/1>`_) Setup repository
