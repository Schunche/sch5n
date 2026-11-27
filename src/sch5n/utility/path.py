# Copyright (c) 2026 Schunche
"""Filesystem locations used by the program."""

from os import getenv
from pathlib import Path

import platformdirs

from sch5n import __author__, __version__
from sch5n import __package__ as _package

ASSETS_ENV_VAR = "SCH5N_ASSETS"
"""Environment variable overriding the assets directory."""


class DevPlatformDirs(platformdirs.PlatformDirs):
    """Custom directory for developers."""


_args = (_package, __author__, __version__, False, False, True, False, False)

_SERVER_PLATFORM_DIRS = DevPlatformDirs(*_args)
_CLIENT_PLATFORM_DIRS = platformdirs.PlatformDirs(*_args)


def get_platformdirs() -> platformdirs.PlatformDirs:
    """Get platform specific directories.

    Returns:
        platformdirs.PlatformDirs: Directories for user data, logs, etc.

    """
    return (
        _SERVER_PLATFORM_DIRS
        if getenv("SCH5N_DEV", "0") == "1"
        else _CLIENT_PLATFORM_DIRS
    )


def find_assets_dir(start: Path | None = None) -> Path:
    """Locate the `assets` directory.

    Resolution order: the `SCH5N_ASSETS` environment variable, then the
    first `assets` directory found walking up from `start` (defaults to
    this file), then `./assets`.

    Returns:
        Path: The assets directory.

    """
    env = getenv(ASSETS_ENV_VAR)
    if env:
        return Path(env)

    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        candidate = parent / "assets"
        if (candidate / "base").is_dir():
            return candidate

    return Path.cwd() / "assets"


ASSETS_DIR = find_assets_dir()
BASE_DIR = ASSETS_DIR / "base"
"""The base game content pack."""
DATA_DIR = BASE_DIR / "data"
TEXTURES_DIR = BASE_DIR / "textures"
MAPS_DIR = BASE_DIR / "maps"
CONFIG_DIR = BASE_DIR / "config"
SHADER_DIR = ASSETS_DIR / "shader"
