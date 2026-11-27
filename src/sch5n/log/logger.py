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
lazy from pathlib import Path

from sch5n.about import NAME
lazy from sch5n.utility import path

if TYPE_CHECKING:
    from logging.config import (
        _DictConfigArgs,  # pyright: ignore[reportPrivateUsage]
    )

LOGGER = logging.getLogger(NAME)


class _State:
    """Module state, kept on an object instead of a global variable."""

    initialized = False


_STATE = _State()


def default_config(log_file: Path) -> dict[str, Any]:
    """Build the logging setup written to the user's config on first start.

    Warnings go to the console; everything goes to `log_file` as JSON
    lines, rotated at a megabyte.

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
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "json",
                "filename": str(log_file),
                "maxBytes": 1048576,
                "backupCount": 5,
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
    """Write the default logging configuration if there is none yet."""
    if config_path.exists():
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(default_config(log_file), indent=2), encoding="utf-8"
    )


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
