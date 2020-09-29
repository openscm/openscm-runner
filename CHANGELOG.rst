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


master
------

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
