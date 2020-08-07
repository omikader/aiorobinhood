import pathlib
import re
import sys

from setuptools import setup

if sys.version_info < (3, 7):
    raise RuntimeError("aiorobinhood requires Python 3.7+")


HERE = pathlib.Path(__file__).parent
txt = (HERE / "aiorobinhood" / "__init__.py").read_text("utf-8")
try:
    version = re.findall(r'^__version__ = "([^\']+)"\r?$', txt, re.M)[0]
except IndexError:
    raise RuntimeError("Unable to determine version.")


def get_long_description() -> str:
    readme = HERE / "README.md"
    with readme.open("r") as f:
        return f.read()


setup(
    name="aiorobinhood",
    version=version,
    description="Asynchronous Robinhood HTTP client",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Omar Abdelkader",
    author_email="omikader@gmail.com",
    url="https://github.com/omikader/aiorobinhood",
    packages=["aiorobinhood"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    license="MIT",
    keywords=["robinhood", "asyncio", "python3", "stocks"],
    install_requires=["aiohttp>=3.6,<4.0", "yarl>=1.4,<2.0"],
    extras_require={
        "dev": [
            "black",
            "cryptography",
            "flake8",
            "isort",
            "mypy",
            "pytest",
            "pytest-aiohttp",
            "pytest-asyncio",
            "pytest-cov",
        ],
        "docs": ["sphinx", "sphinx-autodoc-typehints"],
    },
    python_requires=">=3.7",
)
