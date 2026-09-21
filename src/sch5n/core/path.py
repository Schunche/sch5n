# Copyright (c) 2026 Schunche
"""Experimental software."""

from pathlib import Path
from typing import ClassVar

import platformdirs as _pd

from sch5n import __author__, __version__
from sch5n import __package__ as _package


class Directories:
    """Platform specific directories."""

    _is_developer: ClassVar[bool | None] = None

    _PLATFORM_DIRS = _pd.PlatformDirs(_package, __author__, __version__)

    _CWD: ClassVar[Path] = Path.cwd()
    _DEV: ClassVar[Path] = _CWD / "dev"

    _DEV_USER_LOG: ClassVar[Path] = _DEV / "logs"

    @classmethod
    def make(cls, *, is_developer: bool | None = None) -> None:
        if is_developer is not None:
            cls.set_developer(is_developer=is_developer)

        for get_directory in [
            cls.user_log,
        ]:
            get_directory().mkdir(parents=True, exist_ok=True)

    @classmethod
    def set_developer(cls, *, is_developer: bool) -> None:
        cls._is_developer = is_developer

    @classmethod
    def user_log(cls) -> Path:
        if cls._is_developer:
            return cls._DEV_USER_LOG
        return cls._PLATFORM_DIRS.user_log_path
