# Copyright (c) 2026 Schunche
"""Experimental software."""

import logging
from typing import override
lazy import json


class JsonFormatter(logging.Formatter):
    def __init__(self, fmt_keys: dict[str, str] | None = None) -> None:
        if fmt_keys is None:
            fmt_keys = {}

        super().__init__()
        self.fmt_keys = fmt_keys

    @override
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            name: getattr(record, name)
            for name in dir(record)
            if not name.startswith("_") and name != "getMessage"
        })
