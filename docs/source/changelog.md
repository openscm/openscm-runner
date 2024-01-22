# Changelog

Versions follow [Semantic Versioning](https://semver.org/) (`<major>.<minor>.<patch>`).

Backward incompatible (breaking) changes will only be introduced in major versions
with advance notice in the **Deprecations** section of releases.

<!--
You should *NOT* be adding new changelog entries to this file, this
file is managed by towncrier. See changelog/README.md.

You *may* edit previous changelogs to fix problems like typo corrections or such.
To add a new changelog entry, please see
https://pip.pypa.io/en/latest/development/contributing/#news-entries,
noting that we use the `changelog` directory instead of news, md instead
of rst and use slightly different categories.
-->

<!-- towncrier release notes start -->

## openscm-runner v0.12.1 (2023-05-15)

### Features

- Added support for Python v3.10 and v3.11 ([#83](https://github.com/openscm/openscm-runner/pulls/83))

### Improvements

- Fix failing CI. `fair` is now pinned to \< 2 ([#83](https://github.com/openscm/openscm-runner/pulls/83))

## openscm-runner v0.12.0 (2023-05-12)

### Improvements

- Replaced the deprecated `np.float` for the builtin `float` (Thanks @jkikstra) ([#81](https://github.com/openscm/openscm-runner/pulls/81))
- MAGICC adapter uses `run/openscm-runner` directory to store SCEN files instead of `run` ([#80](https://github.com/openscm/openscm-runner/pulls/80))

## openscm-runner v0.11.0 (2022-08-18)

### Features

- CICERO-SCM python implementation adapter ([#78](https://github.com/openscm/openscm-runner/pulls/78))
- Run tests on macOS as part of CI ([#74](https://github.com/openscm/openscm-runner/pulls/74))
- Add notebook showing how to run MAGICC ([#72](https://github.com/openscm/openscm-runner/pulls/72))

### Improvements

- Move `_AdapterTester` to `openscm_runner.testing` ([#79](https://github.com/openscm/openscm-runner/pulls/79))
- Use environment for running CI so forks can access secrets too ([#77](https://github.com/openscm/openscm-runner/pulls/77))
- Run MAGICC as part of CI by using MAGICC binary downloaded from `magicc.org <https://magicc.org/download/magicc7>`\_ ([#71](https://github.com/openscm/openscm-runner/pulls/71))
- Updated the integration tests to use MAGICC v7.5.3 which is publicly available. ([#70](https://github.com/openscm/openscm-runner/pulls/70))
- Log MAGICC7 errors more prominently. ([#66](https://github.com/openscm/openscm-runner/pulls/66))
- MAGICC7 adapter: automatically create a temporary directory when MAGICC_WORKER_ROOT_DIR is not specified. ([#68](https://github.com/openscm/openscm-runner/pulls/68))
- Updated dependency `black` to `v22.3.0` and pin `isort` and `pylint` for consistent pull requests ([#69](https://github.com/openscm/openscm-runner/pulls/69))

## openscm-runner v0.10.0 (2022-03-15)

### Features

- Added a windows binary for cicero-scm so it can also be run on Windows ([#63](https://github.com/openscm/openscm-runner/pulls/63))
- Allow for the registration of adapters at runtime. Adapters now require a unique `model_name` ([#64](https://github.com/openscm/openscm-runner/pulls/64))

## openscm-runner v0.9.3 (2022-01-19)

### Bug Fixes

- Updated CICERO-SCM fortran binary which confused OHC and OHC down to 700 meters in output and added missing components to radiative imbalance. ([#57](https://github.com/openscm/openscm-runner/pulls/57))

## openscm-runner v0.9.2 (2021-12-23)

### Features

- Conda install instructions ([#59](https://github.com/openscm/openscm-runner/pulls/59))

### Improvements

- Update README for FaIR conda install ([#58](https://github.com/openscm/openscm-runner/pulls/58))

### Bug Fixes

- Packaging now uses setuptools-scm and hence includes all required files in source distributions (which should also fix the conda distribution) ([#61](https://github.com/openscm/openscm-runner/pulls/61))

## openscm-runner v0.9.1 (2021-09-23)

### Bug Fixes

- Fixed CICERO-SCM bugs with converting halon units and handling of very long scenario names ([#52](https://github.com/openscm/openscm-runner/pulls/52))

## openscm-runner v0.9.0 (2021-09-07)

### Improvements

- Require openscm-units >= 0.5.0 ([#55](https://github.com/openscm/openscm-runner/pulls/55))

## openscm-runner v0.8.1 (2021-08-13)

### Improvements

- Made model dependencies optionally installable (allows conda package to be made) ([#54](https://github.com/openscm/openscm-runner/pulls/54))

## openscm-runner v0.7.2 (2021-07-22)

### Improvements

- Loosened requirements and updated CI to run jobs in parallel ([#53](https://github.com/openscm/openscm-runner/pulls/53))

## openscm-runner v0.7.1 (2021-07-09)

## openscm-runner v0.7.0 (2021-07-09)

### Features

- Adapter for the CICERO-SCM model (https://doi.org/10.1088/1748-9326/aa5b0a), see `openscm_runner.adapters.CICEROSCM` ([#24](https://github.com/openscm/openscm-runner/pulls/24))

## openscm-runner v0.6.0 (2021-04-13)

### Improvements

- Changed FaIR heat uptake units to be "W/m^2" rather than "ZJ/yr" ([#50](https://github.com/openscm/openscm-runner/pulls/50))
- Moved `openscm_runner.adapters.magicc7._parallel_process` to `openscm_runner.adapters.utils._parallel_process` ([#47](https://github.com/openscm/openscm-runner/pulls/47))
- Added CI for Python3.9 and dropped required code coverage to 90%. ([#47](https://github.com/openscm/openscm-runner/pulls/47))
- Use `pytest markers <https://docs.pytest.org/en/stable/example/markers.html>`\_ for marking tests which rely on MAGICC rather than hack fixture solution ([#46](https://github.com/openscm/openscm-runner/pulls/46))
- Update regression tests so they can be more easily updated ([#45](https://github.com/openscm/openscm-runner/pulls/45))
- Updated tests to using MAGICCv7.5.1 ([#44](https://github.com/openscm/openscm-runner/pulls/44))

## openscm-runner v0.5.1 (2021-02-27)

### Improvements

- Add ability to run FaIR in parallel ([#43](https://github.com/openscm/openscm-runner/pulls/43))

### Bug Fixes

- Report correct index from FaIR as the anthropogenic total ERF ([#40](https://github.com/openscm/openscm-runner/pulls/40))

## openscm-runner v0.5.0 (2021-02-24)

### Improvements

- Use consistent setting across all progress bars ([#41](https://github.com/openscm/openscm-runner/pulls/41))
- Updated scmdata requirements to handle change to openscm-units ([#38](https://github.com/openscm/openscm-runner/pulls/38))
- Unified key variable naming across MAGICC and FaIR ([#31](https://github.com/openscm/openscm-runner/pulls/31))

### Bug Fixes

- Include parameter name in the warning message emitted when MAGICC's output config doesn't match the input config specified via OpenSCM-Runner ([#39](https://github.com/openscm/openscm-runner/pulls/39))
- Hotfix CI after pandas 1.1.5 broke pylint ([#36](https://github.com/openscm/openscm-runner/pulls/36))
- Ensure FaIR ignores emissions input in scenarios not handled by FaIR, e.g. total CO2 ([#37](https://github.com/openscm/openscm-runner/pulls/37))

## openscm-runner v0.4.4 (2020-11-12)

### Features

- Test that installation includes required package data ([#27](https://github.com/openscm/openscm-runner/pulls/27))

### Bug Fixes

- Minor smoothing for going from climate-assessment to openscm-runner to FaIR 1.6 ([#28](https://github.com/openscm/openscm-runner/pulls/28))

## openscm-runner v0.4.3 (2020-10-14)

### Bug Fixes

- Include csv files needed for running FaIR 1.6 with CMIP6 setup ([#26](https://github.com/openscm/openscm-runner/pulls/26))

## openscm-runner v0.4.2 (2020-10-13)

### Improvements

- Added flexible start date for FaIR and FaIR's scmdata to emissions converter ([#21](https://github.com/openscm/openscm-runner/pulls/21))

## openscm-runner v0.4.1 (2020-10-06)

### Features

- Test that MAGICC's carbon cycle output can be used with MAGICCv7.4.2. ([#23](https://github.com/openscm/openscm-runner/pulls/23))
- `out_config` argument to :func:`openscm_runner.run`, which allows the user to specify model configuration to include in the output's metadata. ([#22](https://github.com/openscm/openscm-runner/pulls/22))

## openscm-runner v0.4.0 (2020-09-24)

### Features

- Flexible end date for FaIR ([#18](https://github.com/openscm/openscm-runner/pulls/18))
- Support for scmdata >= 0.7.1 ([#17](https://github.com/openscm/openscm-runner/pulls/17))

### Improvements

- Configuration is now handled using `openscm_runner.settings` providing support for environment variables and dotenv files ([#19](https://github.com/openscm/openscm-runner/pulls/19))

### Bug Fixes

- Update bandit configuration ([#20](https://github.com/openscm/openscm-runner/pulls/20))

## openscm-runner v0.3.1 (2020-09-03)

### Improvements

- Added in direct aerosol forcing by species in FaIR ([#14](https://github.com/openscm/openscm-runner/pulls/14))

## openscm-runner v0.3.0 (2020-08-26)

### Improvements

- Renamed `openscm_runner.adapters.fair` to `openscm_runner.adapters.fair_adapter` and `openscm_runner.adapters.fair.fair` to `openscm_runner.adapters.fair_adapter.fair_adapter` to avoid a namespace collision with the source `fair` package ([#13](https://github.com/openscm/openscm-runner/pulls/13))

## openscm-runner v0.2.0 (2020-08-25)

### Features

- FaIR 1.6.0 adapter ([#12](https://github.com/openscm/openscm-runner/pulls/12))

### Bug Fixes

- MAGICC adapter so passed in emissions are followed (previously non-CO2 always followed SSP245) ([#11](https://github.com/openscm/openscm-runner/pulls/11))

## openscm-runner v0.1.2 (2020-07-31)

### Improvements

- Upgrade to `scmdata>=0.6.2` so that package can be installed ([#10](https://github.com/openscm/openscm-runner/pulls/10))

## openscm-runner v0.1.1 (2020-07-22)

### Improvements

- Remove unnecessary conversion to IamDataFrame when running MAGICC7 and clarify :meth:`adapters.base._Adapter.run` interface ([#9](https://github.com/openscm/openscm-runner/pulls/9))

## openscm-runner v0.1.0 (2020-07-07)

### Features

- Hotfix requirements and tests ([#7](https://github.com/openscm/openscm-runner/pulls/7))
- Add MAGICC7 adapter (also provides basis for all other adapters) ([#2](https://github.com/openscm/openscm-runner/pulls/2))
- Hot fix initial setup ([#4](https://github.com/openscm/openscm-runner/pulls/4))
- Setup repository ([#1](https://github.com/openscm/openscm-runner/pulls/1))
