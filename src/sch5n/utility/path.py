# Copyright (c) 2026 Schunche
"""Experimental software."""

from os import getenv
from pathlib import Path
from typing import Protocol

import platformdirs

from sch5n import __author__, __version__
from sch5n import __package__ as _package

_DEV_DIR = Path.cwd()
_DEV_USER_DIR = _DEV_DIR / "user"
_DEV_SITE_DIR = _DEV_DIR / "site"


class PlatformDirs(Protocol):
    """Base class for platform specific directories."""


class DevPlatformDirs(platformdirs.PlatformDirs):
    """Custom directory for developers."""


_args = (_package, __author__, __version__, False, False, True, False, False)

_SERVER_PLATFORM_DIRS = DevPlatformDirs(*_args)
_CLIENT_PLATFORM_DIRS = platformdirs.PlatformDirs(*_args)


def get_platformdirs() -> PlatformDirs:
    """Get platformdirs. Use it wisely.

    Returns:
        platformdirs.api.PlatformDirs: -//-

    """
    return (
        _SERVER_PLATFORM_DIRS
        if getenv("SCH5N_DEV", "0") == "1"
        else _CLIENT_PLATFORM_DIRS
    )
