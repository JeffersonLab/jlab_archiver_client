import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'jlab_archiver_client'
# noinspection PyShadowingBuiltins
# copyright = '2025, Adam Carpenter'
author = 'Adam Carpenter'
release = '1.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    'sphinx.ext.autodoc',
    "sphinx.ext.napoleon",   # if you use NumPy/Google docstrings
    "sphinx.ext.doctest",    # enables doctest
    'sphinx_autodoc_typehints',
    'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx_rtd_theme',
    "myst_parser",           # We call this parser explicitly to include the README.md
]

# Helpful MyST features (optional) - not sure if all are needed, but suggested by AI
myst_enable_extensions = [
    "colon_fence",   # ::: fences
    "deflist",
    "substitution",
    "tasklist",
]
# Stable header anchors for README sections
myst_heading_anchors = 3

autosummary_generate = True
html_theme = "sphinx_rtd_theme"

templates_path = ['_templates']
exclude_patterns = []

html_static_path = ['_static']