# Copyright (c) 2026 Schunche
"""Experimental software."""

from importlib import metadata as _metadata

__package__ = "sch5n"

try:  # ruff: ignore[non-empty-init-module]
    __version__ = _metadata.version(__package__)
    __authors__ = [
        author.strip()
        for author in (_metadata.metadata(__package__)["Author"] or "").split(
            ","
        )
        if author.strip()
    ] or ["Schunche"]
except _metadata.PackageNotFoundError:  # Running from a source checkout.
    __version__ = "0.0.0+source"
    __authors__ = ["Schunche"]

__author__ = __authors__[0]
