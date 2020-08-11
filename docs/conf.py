# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import pathlib
import re

import aiohttp.client


# -- Module Remapping --------------------------------------------------------

aiohttp.client.ClientSession.__module__ = "aiohttp"


# -- Project information -----------------------------------------------------

HERE = pathlib.Path(__file__).parent.parent
txt = (HERE / "aiorobinhood" / "__init__.py").read_text("utf-8")
try:
    version = re.findall(r'^__version__ = "([^\']+)"\r?$', txt, re.M)[0]
except IndexError:
    raise RuntimeError("Unable to determine version.")

project = "aiorobinhood"
copyright = "2020, Omar Abdelkader"
author = "Omar Abdelkader"

# The full version, including alpha/beta/rc tags
release = version


# -- General configuration ---------------------------------------------------

# Set whether module names are prepended to all object names.
add_module_names = False

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Intersphinx configuration -----------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "aiohttp": ("https://docs.aiohttp.org/en/stable/", None),
    "yarl": ("https://yarl.readthedocs.io/en/stable/", None),
}


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "aiohttp_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Theme options are theme-specific and customize the look and feel of a theme
# further.
html_theme_options = {
    "logo": "aiorobinhood-logo.png",
    "logo_name": True,
    "description": "Thin asynchronous wrapper for the unofficial Robinhood API",
    "canonical_url": "https://aiorobinhood.readthedocs.io",
    "github_user": "omikader",
    "github_repo": "aiorobinhood",
    "github_button": True,
    "github_type": "star",
    "github_banner": True,
    "badges": [
        {
            "image": "https://github.com/omikader/aiorobinhood/workflows/build/badge.svg",  # noqa: E501
            "target": "https://github.com/omikader/aiorobinhood/actions?query=workflow%3Abuild",  # noqa: E501
            "alt": "Build status",
        },
        {
            "image": "https://codecov.io/gh/omikader/aiorobinhood/branch/master/graph/badge.svg",  # noqa: E501
            "target": "https://codecov.io/gh/omikader/aiorobinhood",
            "alt": "Code coverage status",
        },
        {
            "image": "https://pepy.tech/badge/aiorobinhood/week",
            "target": "https://pepy.tech/project/aiorobinhood/week",
            "alt": "Downloads per week",
        },
        {
            "image": "https://img.shields.io/badge/code%20style-black-000000.svg",
            "target": "https://github.com/psf/black",
            "alt": "Style",
        },
    ],
}

# The name of an image file (within the static path) to use as favicon of the
# docs. This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = "favicon.ico"

# Custom sidebar templates, maps document names to template names.
html_sidebars = {
    "**": ["about.html", "navigation.html", "searchbox.html"],
    "index": ["about.html", "navigation.html", "searchbox.html", "credits.html"],
}
