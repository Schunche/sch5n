# Copyright (c) 2026 Schunche
"""Experimental software."""

import logging
from typing import TYPE_CHECKING
lazy import atexit
lazy import json
lazy import logging.config as logging_config
lazy import logging.handlers as logging_handlers
lazy import os
lazy from copy import deepcopy
lazy from pathlib import Path

from sch5n.about import NAME

if TYPE_CHECKING:
    from logging.config import (
        _DictConfigArgs,  # pyright: ignore[reportPrivateUsage]
    )

LOGGER = logging.getLogger(NAME)


class _State:
    """Module state, kept on an object instead of a global variable."""

    initialized = False


_STATE = _State()


def init(config_path: Path, override: _DictConfigArgs | None = None) -> None:
    """Initialize logging.

    Calling this function several times is safe.

    Args:
        config_path: Path to configuration.
        override: Override options from file.

    Raises:
        RuntimeError: The `logging` builtin module messed up.

    """
    if _STATE.initialized:
        LOGGER.warning("Logging already initialized. Not doing that again.")
        return
    _STATE.initialized = True
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

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
