# Makefile to help automate key steps

.DEFAULT_GOAL := help
# Will likely fail on Windows, but Makefiles are in general not Windows
# compatible so we're not too worried
TEMP_FILE := $(shell mktemp)

# A helper script to get short descriptions of each target in the Makefile
define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([\$$\(\)a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-30s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT


.PHONY: help
help:  ## print short description of each target
	@python3 -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

.PHONY: checks
checks:  ## run all the linting checks of the codebase
	@echo "=== pre-commit ==="; uv run --group dev pre-commit run --all-files || echo "--- pre-commit failed ---" >&2; \
		echo "=== mypy ==="; MYPYPATH=stubs uv run --group dev mypy src || echo "--- mypy failed ---" >&2; \
		echo "=== ty ==="; uv run --group dev ty check src || echo "--- ty failed ---" >&2; \
		echo "======"

.PHONY: ruff-fixes
ruff-fixes:  ## fix the code using ruff
    # format before and after checking so that the formatted stuff is checked and
    # the fixed stuff is formatted
	uv run --group dev ruff format src tests scripts docs
	uv run --group dev ruff check src tests scripts docs --fix
	uv run --group dev ruff format src tests scripts docs

# The coverage checks match CI (`.github/workflows/ci.yaml`):
# the shared tests are checked excluding the adapters,
# each adapter group's tests must cover 100% of its modules.
# `--cov-fail-under=0` stops pytest-cov applying the global threshold
# to the whole package, the `coverage report` lines do the checking.

.PHONY: test
test:  ## run the tests (except each adapter group's tests, which need the models)
	uv run --group tests pytest src tests -r a -v --doctest-modules --doctest-report ndiff --cov=openscm_runner --cov-report= --cov-fail-under=0
	uv run --group tests coverage report --omit='*/adapters/*'

.PHONY: test-magicc-ar6
test-magicc-ar6:  ## run the MAGICC AR6 adapter tests (including the slow ones)
	uv run --group tests --extra magicc-ar6 pytest -m "magicc_ar6" src tests -r a -v --doctest-modules --doctest-report ndiff --cov=openscm_runner --cov-report= --cov-fail-under=0
	uv run --group tests coverage report --include='*/adapters/magicc_ar6/*' --show-missing --skip-covered --fail-under=100

# Note on code coverage and testing:
# You must specify cov=src.
# Otherwise, funny things happen when doctests are involved.
# If you want to debug what is going on with coverage,
# we have found that adding COVERAGE_DEBUG=trace
# to the front of the below command
# can be very helpful as it shows you
# if coverage is tracking the coverage
# of all of the expected files or not.
# We are sure that the coverage maintainers would appreciate a PR
# that improves the coverage handling when there are doctests
# and a `src` layout like ours.

.PHONY: docs
docs:  ## build the docs
	uv run --group docs properdocs build

.PHONY: docs-strict
docs-strict:  ## build the docs strictly (e.g. raise an error on warnings, this most closely mirrors what we do in the CI)
	uv run --group docs properdocs build --strict

.PHONY: docs-serve
docs-serve:  ## serve the docs locally
	uv run --group docs properdocs serve

.PHONY: changelog-draft
changelog-draft:  ## compile a draft of the next changelog
	uv run --group dev towncrier build --draft --version draft

.PHONY: licence-check
licence-check:  ## Check that licences of the dependencies are suitable
	# Will likely fail on Windows, but Makefiles are in general not Windows
	# compatible so we're not too worried
	uv export --no-dev > $(TEMP_FILE)
	uv run --group dev liccheck -r $(TEMP_FILE) -R licence-check.txt
	rm -f $(TEMP_FILE)

.PHONY: virtual-environment
virtual-environment:  ## update virtual environment, create a new one if it doesn't already exist
	uv sync --all-extras --group all-dev
	uv run --group dev pre-commit install
