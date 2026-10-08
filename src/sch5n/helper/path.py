# Copyright (c) 2026 Schunche
"""Experimental software."""

import os
from pathlib import Path
from typing import override

import platformdirs

from sch5n import __author__, __version__
from sch5n import __package__ as _package
from sch5n.core.environment import EnvironmentFlag
from sch5n.error.exceptions import VersionError

_TARGET_PLATFORMDIRS_VERSION = "4.11.9"
if platformdirs.version.version != _TARGET_PLATFORMDIRS_VERSION:
    msg = (
        "platformdirs is of not the correct version.\n"
        "If you want to update, make sure PlatformDirs interface matches."
    )
    raise VersionError(msg)


_DEV_DIR = Path.cwd()
_DEV_USER_DIR = _DEV_DIR / "user"
_DEV_SITE_DIR = _DEV_DIR / "site"


class DevPlatformDirs(platformdirs.api.PlatformDirsABC):  # ruff: ignore[too-many-public-methods, undocumented-public-class]
    @property
    @override
    def user_data_dir(self) -> str:
        """Data directory tied to the user."""
        return str(_DEV_USER_DIR / "data")

    @property
    @override
    def site_data_dir(self) -> str:
        """Data directory shared by users."""
        return str(_DEV_SITE_DIR / "data")

    @property
    @override
    def user_config_dir(self) -> str:
        """Config directory tied to the user."""
        return str(_DEV_USER_DIR / "config")

    @property
    @override
    def site_config_dir(self) -> str:
        """Config directory shared by users."""
        return str(_DEV_SITE_DIR / "config")

    @property
    @override
    def user_cache_dir(self) -> str:
        """Cache directory tied to the user."""
        return str(_DEV_USER_DIR / "cache")

    @property
    @override
    def site_cache_dir(self) -> str:
        """Cache directory shared by users."""
        return str(_DEV_SITE_DIR / "cache")

    @property
    @override
    def user_state_dir(self) -> str:
        """State directory tied to the user."""
        return str(_DEV_USER_DIR / "state")

    @property
    @override
    def site_state_dir(self) -> str:
        """State directory shared by users."""
        return str(_DEV_SITE_DIR / "state")

    @property
    @override
    def user_log_dir(self) -> str:
        """Log directory tied to the user."""
        return str(_DEV_USER_DIR / "log")

    @property
    @override
    def site_log_dir(self) -> str:
        """Log directory shared by users."""
        return str(_DEV_SITE_DIR / "log")

    @property
    @override
    def user_documents_dir(self) -> str:
        """Documents directory tied to the user."""
        return str(_DEV_USER_DIR / "documents")

    @property
    @override
    def user_downloads_dir(self) -> str:
        """Downloads directory tied to the user."""
        return str(_DEV_USER_DIR / "downloads")

    @property
    @override
    def user_pictures_dir(self) -> str:
        """Pictures directory tied to the user."""
        return str(_DEV_USER_DIR / "pictures")

    @property
    @override
    def user_videos_dir(self) -> str:
        """Videos directory tied to the user."""
        return str(_DEV_USER_DIR / "videos")

    @property
    @override
    def user_music_dir(self) -> str:
        """Music directory tied to the user."""
        return str(_DEV_USER_DIR / "music")

    @property
    @override
    def user_desktop_dir(self) -> str:
        """Desktop directory tied to the user."""
        return str(_DEV_USER_DIR / "desktop")

    @property
    @override
    def user_projects_dir(self) -> str:
        """Projects directory tied to the user."""
        return str(_DEV_USER_DIR / "projects")

    @property
    @override
    def user_publicshare_dir(self) -> str:
        """Public share directory tied to the user."""
        return str(_DEV_USER_DIR / "publicshare")

    @property
    @override
    def user_templates_dir(self) -> str:
        """Templates directory tied to the user."""
        return str(_DEV_USER_DIR / "templates")

    @property
    @override
    def user_fonts_dir(self) -> str:
        """Fonts directory tied to the user."""
        return str(_DEV_USER_DIR / "fonts")

    @property
    @override
    def user_preference_dir(self) -> str:
        """Preference directory tied to the user."""
        return str(_DEV_USER_DIR / "preference")

    @property
    @override
    def user_bin_dir(self) -> str:
        """Bin directory tied to the user."""
        return str(_DEV_USER_DIR / "downloads")

    @property
    @override
    def site_bin_dir(self) -> str:
        """Bin directory shared by users."""
        return str(_DEV_SITE_DIR / "bin")

    @property
    @override
    def user_applications_dir(self) -> str:
        """Applications directory tied to the user."""
        return str(_DEV_USER_DIR / "applications")

    @property
    @override
    def site_applications_dir(self) -> str:
        """Applications directory shared by users."""
        return str(_DEV_SITE_DIR / "applications")

    @property
    @override
    def user_runtime_dir(self) -> str:
        """Runtime directory tied to the user."""
        return str(_DEV_USER_DIR / "runtime")

    @property
    @override
    def site_runtime_dir(self) -> str:
        """Runtime directory shared by users."""
        return str(_DEV_SITE_DIR / "runtime")

    # Iterators are called on self, so no need to override in current version
    # Paths are generated from strings, which are from paths...
    # Of course, this comment will not be rewieved on update


_args = (_package, __author__, __version__, False, False, True, False, False)

_SERVER_PLATFORM_DIRS = DevPlatformDirs(*_args)
_CLIENT_PLATFORM_DIRS = platformdirs.PlatformDirs(*_args)


def is_server() -> bool:
    """Determine whether this is a server.

    Returns:
        bool: -//-

    """
    return os.environ.get(EnvironmentFlag.SERVER, "0") == "1"


def is_developer() -> bool:
    """Determine whether this is a developer.

    Returns:
        bool: -//-

    """
    return os.environ.get(EnvironmentFlag.DEVELOPER, "0") == "1"


def get_platformdirs() -> platformdirs.api.PlatformDirsABC:
    """Get platformdirs. Use it wisely.

    Returns:
        platformdirs.api.PlatformDirs: -//-

    """
    return _SERVER_PLATFORM_DIRS if is_developer() else _CLIENT_PLATFORM_DIRS
