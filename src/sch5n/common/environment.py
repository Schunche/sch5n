# Copyright (c) 2026 Schunche
"""Experimental software."""

from enum import StrEnum

from sch5n import __author__
from sch5n import __package__ as _package

_FLAG_PREFIX: str = _package.upper() if _package is not None else __author__


class EnvironmentFlag(StrEnum):
    SERVER = _FLAG_PREFIX + "_SERVER"
    DEVELOPER = _FLAG_PREFIX + "_DEVELOPER"
