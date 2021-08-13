import os.path

from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

import versioneer

PACKAGE_NAME = "openscm-runner"
AUTHORS = [
    ("Zeb Nicholls", "zebedee.nicholls@climate-energy-college.org"),
    ("Robert Gieseke", "robert.gieseke@pik-potsdam.de"),
    ("Jared Lewis", "jared.lewis@climate-energy-college.org"),
    ("Sven Willner", "sven.willner@pik-potsdam.de"),
    ("Chris Smith", "c.j.smith1@leeds.ac.uk"),
]
URL = "https://github.com/openscm/openscm-runner"

DESCRIPTION = "Thin wrapper to run simple climate models (emissions driven runs only)"
README = "README.rst"

SOURCE_DIR = "src"

REQUIREMENTS = [
    "click",
    "pyam-iamc",
    "python-dotenv",
    "scmdata>=0.7.4",
    "tqdm",
]
REQUIREMENTS_FAIR = ["fair"]
REQUIREMENTS_MAGICC = ["pymagicc>=2.0.0,<3"]
REQUIREMENTS_MODELS = REQUIREMENTS_FAIR + REQUIREMENTS_MAGICC

REQUIREMENTS_NOTEBOOKS = [
    "ipywidgets",
    "notebook",
    "seaborn",
]
REQUIREMENTS_TESTS = [
    "codecov",
    "coverage",
    "nbval",
    "pytest-cov",
    "pytest>=4.0",
    "xlrd",
]
REQUIREMENTS_DOCS = ["sphinx>=1.4", "sphinx_rtd_theme", "sphinx-click"]
REQUIREMENTS_DEPLOY = ["twine>=1.11.0", "setuptools>=41.2", "wheel>=0.31.0"]

REQUIREMENTS_DEV = [
    *[
        "bandit",
        "black==19.10b0",
        "black-nb",
        "flake8",
        "isort>5",
        "mypy",
        "nbdime",
        "pydocstyle",
        "pylint>=2.4.4",
    ],
    *REQUIREMENTS_DEPLOY,
    *REQUIREMENTS_DOCS,
    *REQUIREMENTS_NOTEBOOKS,
    *REQUIREMENTS_TESTS,
    *REQUIREMENTS_MODELS,
]

REQUIREMENTS_EXTRAS = {
    "deploy": REQUIREMENTS_DEPLOY,
    "dev": REQUIREMENTS_DEV,
    "docs": REQUIREMENTS_DOCS,
    "notebooks": REQUIREMENTS_NOTEBOOKS,
    "tests": REQUIREMENTS_TESTS,
    "fair": REQUIREMENTS_FAIR,
    "magicc": REQUIREMENTS_MAGICC,
    "models": REQUIREMENTS_MODELS,
}

# no tests/docs in `src` so don't need exclude
PACKAGES = find_packages(SOURCE_DIR)
PACKAGE_DIR = {"": SOURCE_DIR}
PACKAGE_DATA = {
    "openscm_runner": [
        os.path.join("adapters", "fair_adapter", "*.csv"),
        os.path.join("adapters", "ciceroscm_adapter", "utils_templates", "*.txt"),
        os.path.join(
            "adapters",
            "ciceroscm_adapter",
            "utils_templates",
            "pam_RCMIP_test_klimsensdefault.scm",
        ),
        os.path.join(
            "adapters", "ciceroscm_adapter", "utils_templates", "run_dir", "*.txt"
        ),
        os.path.join(
            "adapters", "ciceroscm_adapter", "utils_templates", "run_dir", "scm_vCH4fb"
        ),
        os.path.join(
            "adapters",
            "ciceroscm_adapter",
            "utils_templates",
            "run_dir",
            "input_OTHER",
            "NATEMIS",
            "*.txt",
        ),
        os.path.join(
            "adapters",
            "ciceroscm_adapter",
            "utils_templates",
            "run_dir",
            "input_RF",
            "RFLUC",
            "*.txt",
        ),
        os.path.join(
            "adapters",
            "ciceroscm_adapter",
            "utils_templates",
            "run_dir",
            "input_RF",
            "RFSUN",
            "*.txt",
        ),
        os.path.join(
            "adapters",
            "ciceroscm_adapter",
            "utils_templates",
            "run_dir",
            "input_RF",
            "RFVOLC",
            "*.txt",
        ),
    ]
}

# Get the long description from the README file
with open(README, "r") as f:
    README_LINES = ["OpenSCM-Runner", "==============", ""]
    add_line = False
    for line in f:
        if line.strip() == ".. sec-begin-long-description":
            add_line = True
        elif line.strip() == ".. sec-end-long-description":
            break
        elif add_line:
            README_LINES.append(line.strip())

if len(README_LINES) < 3:
    raise RuntimeError("Insufficient description given")


class OpenscmRunner(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest

        pytest.main(self.test_args)


cmdclass = versioneer.get_cmdclass()
cmdclass.update({"test": OpenscmRunner})

setup(
    name=PACKAGE_NAME,
    version=versioneer.get_version(),
    description=DESCRIPTION,
    long_description="\n".join(README_LINES),
    long_description_content_type="text/x-rst",
    author=", ".join([author[0] for author in AUTHORS]),
    author_email=", ".join([author[1] for author in AUTHORS]),
    url=URL,
    license="3-Clause BSD License",
    classifiers=[  # full list at https://pypi.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: BSD License",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    keywords=["openscm", "runner", "python", "repo", "simple", "climate", "model"],
    packages=PACKAGES,
    package_dir=PACKAGE_DIR,
    package_data=PACKAGE_DATA,
    include_package_data=True,
    install_requires=REQUIREMENTS,
    extras_require=REQUIREMENTS_EXTRAS,
    cmdclass=cmdclass,
    # entry_points={
    #     "console_scripts": [
    #         "openscm-runner=openscm_runner.cli:run",
    #     ]
    # },
)
