# Copyright (c) 2026 Schunche
"""Experimental software."""

import os
from pathlib import Path

import platformdirs as _pd

from sch5n import __author__, __version__
from sch5n import __package__ as _package
from sch5n.core.environment import EnvironmentFlag


def is_server() -> bool:
    result = os.environ.get(EnvironmentFlag.SERVER, None)

    if result is None:
        return False

    if result in {"0", "1"}:
        return result == "1"

    print(f"Environment flag unknown: {EnvironmentFlag.SERVER} - {result}")
    return False


_PLATFORM_DIRS = _pd.PlatformDirs(_package, __author__, __version__)

_CWD: Path = Path.cwd()
_DEV: Path = _CWD / "dev"

_DEV_USER_LOG: Path = _DEV / "logs"


def user_log(cls) -> Path:
    if cls._is_developer:
        return cls._DEV_USER_LOG
    return cls._PLATFORM_DIRS.user_log_path
