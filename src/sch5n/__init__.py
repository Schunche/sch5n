# Copyright (c) 2026 Schunche
"""Experimental software."""

import tomllib
from pathlib import Path

with Path("pyproject.toml").open("rb") as f:  # ruff: ignore[non-empty-init-module]
    config = tomllib.load(f)

__package__ = config["project"]["name"]
__version__ = config["project"]["version"]
__authors__ = [author["name"] for author in config["project"]["authors"]]
__author__ = __authors__[0]
