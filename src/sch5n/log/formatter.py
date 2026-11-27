# Copyright (c) 2026 Schunche
"""Log formatting."""

import logging
from datetime import UTC, datetime
from typing import override
lazy import json

_RESERVED = frozenset(vars(logging.makeLogRecord({})))
"""Attributes every log record has; anything else came from `extra=`."""


def _value(record: logging.LogRecord, attribute: str) -> object:
    """Read an attribute of a record, or one of the computed ones.

    Returns:
        object: The value, `None` if the record does not have it.

    """
    match attribute:
        case "message":
            return record.getMessage()
        case "timestamp":
            created = datetime.fromtimestamp(record.created, tz=UTC)
            return created.isoformat()
        case _:
            return getattr(record, attribute, None)


class JsonFormatter(logging.Formatter):
    """Formats each record as one JSON object, for JSON lines log files.

    `fmt_keys` maps output keys to record attributes, e.g.
    `{"level": "levelname"}`. Two attributes are computed: `message` (the
    formatted message) and `timestamp` (ISO 8601, UTC). Exception info and
    values passed with `extra=` are always included.
    """

    def __init__(self, fmt_keys: dict[str, str] | None = None) -> None:
        """Create a formatter with an output key to attribute mapping."""
        super().__init__()
        self.fmt_keys = fmt_keys or {"message": "message"}

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Encode a record as a single line of JSON.

        Returns:
            str: The JSON text.

        """
        data = {
            key: _value(record, attribute)
            for key, attribute in self.fmt_keys.items()
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            data["stack_info"] = self.formatStack(record.stack_info)
        for key, value in vars(record).items():
            if key not in _RESERVED and key not in data:
                data[key] = value
        return json.dumps(data, default=str)
