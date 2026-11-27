# Copyright (c) 2026 Schunche
"""Package name, version and authors."""

from importlib import metadata

NAME = "sch5n"


def _read() -> tuple[str, list[str]]:
    """Read the installed package metadata.

    Returns:
        tuple[str, list[str]]: Version and authors. Placeholders when
        running from a source checkout that is not installed.

    """
    try:
        info = metadata.metadata(NAME)
    except metadata.PackageNotFoundError:
        return "0.0.0+source", ["Schunche"]
    authors = [
        author.strip()
        for author in (info["Author"] or "").split(",")
        if author.strip()
    ]
    return info["Version"], authors or ["Schunche"]


__version__, __authors__ = _read()
__author__ = __authors__[0]
