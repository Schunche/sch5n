# Copyright (c) 2026 Schunche
"""Experimental software."""

import logging
from typing import TYPE_CHECKING, Any
lazy import atexit
lazy import json
lazy import logging.config as logging_config
lazy import logging.handlers as logging_handlers
lazy import os
lazy from copy import deepcopy
lazy from datetime import UTC, datetime
lazy from pathlib import Path

from sch5n.about import NAME
lazy from sch5n.utility import path

if TYPE_CHECKING:
    from logging.config import (
        _DictConfigArgs,  # pyright: ignore[reportPrivateUsage]
    )

LOGGER = logging.getLogger(NAME)
KEPT_LOGS = 10
"""Logs of earlier starts kept next to the latest one."""
OLD_LOG_NAME = "sch5n.log.jsonl"
"""The single log file of earlier versions."""


class _State:
    """Module state, kept on an object instead of a global variable."""

    initialized = False


_STATE = _State()


def default_config(log_file: Path) -> dict[str, Any]:
    """Build the logging setup written to the user's config on first start.

    Warnings go to the console; everything goes to `log_file` as JSON
    lines. Each start writes a fresh `log_file`, see `archive_latest`.

    Returns:
        dict[str, Any]: A `logging.config.dictConfig` configuration.

    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "[%(levelname)s] %(asctime)s: %(message)s",
                "datefmt": "%Y/%m/%d-%H:%M:%S (%z)",
            },
            "json": {
                "()": "sch5n.log.formatter.JsonFormatter",
                "fmt_keys": {
                    "level": "levelname",
                    "message": "message",
                    "timestamp": "timestamp",
                    "logger": "name",
                    "module": "module",
                    "function": "funcName",
                    "line": "lineno",
                    "thread_name": "threadName",
                },
            },
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "level": "WARNING",
                "formatter": "simple",
                "stream": "ext://sys.stderr",
            },
            "file_jsonl": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "json",
                "filename": str(log_file),
                "mode": "w",
                "encoding": "utf-8",
            },
            "queue_handler": {
                "class": "logging.handlers.QueueHandler",
                "handlers": ["stderr", "file_jsonl"],
                "respect_handler_level": True,
            },
        },
        "loggers": {"root": {"level": "DEBUG", "handlers": ["queue_handler"]}},
    }


def ensure_config(config_path: Path, log_file: Path) -> None:
    """Write the default logging configuration if there is none yet.

    A configuration from before `latest.log.jsonl` is replaced too.
    """
    if config_path.exists() and OLD_LOG_NAME not in config_path.read_text(
        encoding="utf-8"
    ):
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(default_config(log_file), indent=2), encoding="utf-8"
    )


def archive_latest(latest: Path, keep: int = KEPT_LOGS) -> bool:
    """Move the last start's log aside, named after when it was written.

    Only the newest `keep` old logs are kept.

    Returns:
        bool: False if the log could not be moved, like while another
        program of the game is still writing it.

    """
    if not latest.exists():
        return True
    written = datetime.fromtimestamp(latest.stat().st_mtime, UTC).astimezone()
    stem = written.strftime("%Y-%m-%d_%H-%M-%S")
    suffix = latest.name.removeprefix("latest")
    target, number = latest.with_name(stem + suffix), 2
    while target.exists():
        target = latest.with_name(f"{stem}-{number}{suffix}")
        number += 1
    try:
        latest.rename(target)
    except OSError:
        return False
    old = sorted(
        (log for log in latest.parent.glob(f"*{suffix}") if log != latest),
        key=lambda log: log.stat().st_mtime,
    )
    for log in old[:-keep] if keep else old:
        log.unlink(missing_ok=True)
    return True


def init(
    config_path: Path | None = None, override: _DictConfigArgs | None = None
) -> None:
    """Initialize logging.

    Calling this function several times is safe.

    Args:
        config_path: Path to configuration. By default the user's own,
            written with the defaults on first start.
        override: Override options from file.

    Raises:
        RuntimeError: The `logging` builtin module messed up.

    """
    if _STATE.initialized:
        LOGGER.warning("Logging already initialized. Not doing that again.")
        return
    _STATE.initialized = True
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

    if config_path is None:
        config_path = path.user_logging_file()
        ensure_config(config_path, path.user_log_file())

    if override is None:
        override = {"version": 1}

    with config_path.open(encoding="utf-8") as f:
        config: _DictConfigArgs = json.load(f)

    config.update(deepcopy(override))

    if "handlers" in config:
        for handler in config["handlers"].values():
            filename = handler.get("filename", None)
            if filename is None:
                continue
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            if Path(filename).name == path.LATEST_LOG and not archive_latest(
                Path(filename)
            ):
                # Another program of the game is writing it: add to it.
                handler["mode"] = "a"

    logging_config.dictConfig(config)

    queue_handler = logging.getHandlerByName("queue_handler")
    if isinstance(queue_handler, logging_handlers.QueueHandler):
        listener = queue_handler.listener
        if listener is not None:
            listener.start()
            atexit.register(listener.stop)
            return

    msg = "The `logging` builtin module messed up."
    raise RuntimeError(msg)
