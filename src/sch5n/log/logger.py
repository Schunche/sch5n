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

from sch5n import __package__ as _package

if TYPE_CHECKING:
    from logging.config import _DictConfigArgs  # pyright: ignore[reportPrivateUsage]

LOGGER = logging.getLogger(_package)

_is_initialized = False


def init(
    config_path: Path | None = None, overriide: _DictConfigArgs | None = None
) -> None:
    global _is_initialized  # ruff: ignore[global-statement]

    if _is_initialized:
        LOGGER.warning("Logging already initialized.")
    _is_initialized = True
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

    if config_path is None:
        config_path = Path("assets") / "base" / "config" / "logging.json"
    if overriide is None:
        overriide = {"version": 1}

    with config_path.open(encoding="utf-8") as f:
        config: _DictConfigArgs = json.load(f)

    config.update(deepcopy(overriide))

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

    raise RuntimeError
