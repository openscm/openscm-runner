"""
Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""
from functools import wraps

from sphinxcontrib_autodocgen import AutoDocGen

import openscm_runner

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "OpenSCM-Runner"
# put the authors in their own variable, so they can be reused later
authors = ", ".join(
    ["Zebedee Nicholls", "Robert Gieseke", "Jared Lewis", "Sven Willner"]
)
# add a copyright year variable, we can extend this over time in future as
# needed
copyright_year = "2020-2024"
copyright = f"{copyright_year}, {authors}"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    # create documentation automatically from source code
    # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html
    "sphinx.ext.autodoc",
    # automatic summary
    "sphinx.ext.autosummary",
    # automatic summary with better control
    "sphinxcontrib_autodocgen",
    # tell sphinx that we're using numpy style docstrings
    # https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html
    "sphinx.ext.napoleon",
    # add support for type hints too (so type hints are included next to
    # argument and return types in docs)
    # https://github.com/tox-dev/sphinx-autodoc-typehints
    # this must come after napoleon
    # in the list for things to work properly
    # https://github.com/tox-dev/sphinx-autodoc-typehints#compatibility-with-sphinxextnapoleon
    "sphinx_autodoc_typehints",
    # jupytext rendered notebook support (also loads myst_parser)
    "myst_nb",
    # links to other docs
    "sphinx.ext.intersphinx",
    # add source code to docs
    "sphinx.ext.viewcode",
    # add copy code button to code examples
    "sphinx_copybutton",
    # math support
    "sphinx.ext.mathjax",
]

# general sphinx settings
# https://www.sphinx-doc.org/en/master/usage/configuration.html
# Don't include module names in object names (can also be left on,
# depends a bit how your project is structured and what you prefer)
add_module_names = False
# Other global settings which we've never used but are included by default
templates_path = ["_templates"]
# Avoid sphinx thinking that conf.py is a source file because we use .py
# endings for notebooks
exclude_patterns = ["conf.py"]
# Stop sphinx doing funny things with byte order markers
source_encoding = "utf-8"

# configure default settings for autodoc directives
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directives
autodoc_default_options = {
    # Show the inheritance of classes
    "show-inheritance": True,
}

# autosummary with autodocgen
# make sure autosummary doesn't interfere
autosummary_generate = True
autosummary_generate_overwrite = False

autodocgen_config = [
    {
        "modules": [openscm_runner],
        "generated_source_dir": "docs/source/api",
        # choose a different title for specific modules, e.g. the toplevel one
        "module_title_decider": lambda modulename: "API Reference"
        if modulename == "openscm_runner"
        else modulename,
    }
]

# monkey patch to remove leading newlines
generate_module_rst_orig = AutoDocGen.generate_module_rst


@wraps(generate_module_rst_orig)
def _generate_module_rst_new(*args, **kwargs):
    default = generate_module_rst_orig(*args, **kwargs)
    out = default.lstrip("\n")
    if not out.endswith("\n"):
        out = f"{out}\n"

    return out


AutoDocGen.generate_module_rst = _generate_module_rst_new

# napoleon extension settings
# https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html
# We use numpy style docstrings
napoleon_numpy_docstring = True
# We don't use google docstrings
napoleon_google_docstring = False
# Don't use separate rtype for the return documentation
napoleon_use_rtype = False

# autodoc type hints settings
# https://github.com/tox-dev/sphinx-autodoc-typehints
# include full name of classes when expanding type hints?
typehints_fully_qualified = True
# Add rtype directive if needed
typehints_document_rtype = True
# Put the return type as part of the return documentation
typehints_use_rtype = False

# Left-align maths equations
mathjax3_config = {"chtml": {"displayAlign": "center"}}

# myst configuration
myst_enable_extensions = ["amsmath", "dollarmath"]
# cache because we save our notebooks as `.py` files i.e. without output
# stored so auto doesn't work (it just ends up being run every time)
nb_execution_mode = "cache"
nb_execution_raise_on_error = True
nb_execution_show_tb = True
nb_execution_timeout = 300  # long to handle slow builds on rtd
nb_custom_formats = {".py": ["jupytext.reads", {"fmt": "py:percent"}]}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Pick your theme for html output, we typically use the read the docs theme
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]


# Ignore ipynb files when building (see https://github.com/executablebooks/MyST-NB/issues/363).
def setup(app):
    """
    Set up the Sphinx app
    """
    app.registry.source_suffix.pop(".ipynb", None)


# Intersphinx mapping
intersphinx_mapping = {
    "numpy": ("https://docs.scipy.org/doc/numpy", None),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable", None),
    "python": ("https://docs.python.org/3", None),
    "pyam": ("https://pyam-iamc.readthedocs.io/en/latest", None),
    "scmdata": ("https://scmdata.readthedocs.io/en/latest", None),
    "xarray": ("http://xarray.pydata.org/en/stable", None),
    "pint": (
        "https://pint.readthedocs.io/en/latest",
        None,
    ),
}
