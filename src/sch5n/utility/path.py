# Copyright (c) 2026 Schunche
"""Filesystem locations used by the program."""

from dataclasses import dataclass
from os import getenv
from pathlib import Path

import platformdirs

from sch5n.about import NAME, __author__

ASSETS_ENV_VAR = "SCH5N_ASSETS"
"""Environment variable overriding the assets directory."""
DATA_ENV_VAR = "SCH5N_DATA"
"""Environment variable overriding the data directory."""
DEV_ENV_VAR = "SCH5N_DEV"
"""`1` keeps everything the game writes in the game folder, `0` uses the
user's folders. Unset, a git checkout counts as developing."""


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
        if (candidate / "textures").is_dir():
            return candidate

    return Path.cwd() / "assets"


ASSETS_DIR = find_assets_dir()
"""Pictures and shaders: what draws the game."""
TEXTURES_DIR = ASSETS_DIR / "textures"
SHADER_DIR = ASSETS_DIR / "shaders"
FONTS_DIR = ASSETS_DIR / "fonts"
"""Fonts to choose from, with their licenses. Listed in `ui.json`."""
DATA_DIR = Path(getenv(DATA_ENV_VAR) or ASSETS_DIR.parent / "data")
"""Game rules, blocks, items, UI and default settings: what defines the
game. Next to `assets`."""
MAPS_DIR = DATA_DIR / "maps"
"""Maps that come with the game, and the ones made with the editor."""


GAME_DIR = ASSETS_DIR.parent
"""The game folder, holding `assets` and `data`."""
DEV_USER_DIR = GAME_DIR / "dev" / "user"
"""Where a developer's settings, worlds and logs go, inside the game
folder and ignored by git."""


def is_developing() -> bool:
    """Whether the game runs for development.

    Developers work in a git checkout; players download the game without
    `.git`. `SCH5N_DEV` decides instead when set.

    Returns:
        bool: True to keep everything inside the game folder.

    """
    match getenv(DEV_ENV_VAR):
        case "1":
            return True
        case "0":
            return False
        case _:
            return (GAME_DIR / ".git").exists()


@dataclass(frozen=True, slots=True)
class UserDirs:
    """Where the game writes: the user's settings, worlds and logs."""

    config: Path
    data: Path
    logs: Path


def user_dirs() -> UserDirs:
    """Get the directories the game writes to.

    While developing they are inside the game folder, so nothing gets
    outside it. Otherwise they are the user's own, unversioned so they
    carry over between releases.

    Returns:
        UserDirs: Config, data and log directories.

    """
    if is_developing():
        return UserDirs(
            DEV_USER_DIR / "config",
            DEV_USER_DIR / "data",
            DEV_USER_DIR / "logs",
        )
    dirs = platformdirs.PlatformDirs(appname=NAME, appauthor=__author__)
    return UserDirs(
        dirs.user_config_path, dirs.user_data_path, dirs.user_log_path
    )


def user_logging_file() -> Path:
    """Locate the user's logging configuration, made on first start.

    Returns:
        Path: A file in the per-user config directory.

    """
    return user_dirs().config / "logging.json"


LATEST_LOG = "latest.log.jsonl"
"""The log of the running (or last) start. Older ones are named after
when they were written."""


def user_log_file() -> Path:
    """Where the game writes its log by default.

    Returns:
        Path: A file in the per-user log directory.

    """
    return user_dirs().logs / LATEST_LOG


def user_settings_file() -> Path:
    """Where the user's own settings are saved.

    Returns:
        Path: A file in the per-user config directory.

    """
    return user_dirs().config / "settings.json"
