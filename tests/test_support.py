# Copyright (c) 2026 Schunche
"""The minimap store, the JSON log formatter and package metadata."""

from __future__ import annotations

import json
import logging
import zlib
from typing import TYPE_CHECKING

import pytest

import sch5n
from sch5n.client.map import Map
from sch5n.log.formatter import JsonFormatter

if TYPE_CHECKING:
    from pathlib import Path

RED = (255, 0, 0)
LIGHT = 7


def test_map_save_load_roundtrip(tmp_path: Path) -> None:
    """A saved minimap loads back with every tile."""
    saved = Map((10, 5))
    saved.set((3, 4), RED, LIGHT, check_bounds=True)
    saved.set((-1, 2), RED, 0, check_bounds=False)
    path = tmp_path / "maps" / "minimap.bin"
    saved.save(path)

    loaded = Map((1, 1))
    loaded.load(path)
    assert loaded.get((3, 4)) == saved.get((3, 4))
    assert loaded.get((-1, 2)) == saved.get((-1, 2))
    assert loaded.is_revealed((3, 4))
    assert not loaded.is_revealed((-1, 2))
    assert loaded.isinbound((9, 4))


def test_map_bounds_check() -> None:
    """With `check_bounds`, only positions on the map are recorded."""
    minimap = Map((4, 4))
    minimap.set((1, 1), RED, LIGHT, check_bounds=True)
    minimap.set((4, 0), RED, LIGHT, check_bounds=True)
    assert minimap.get((1, 1)) is not None
    assert minimap.get((4, 0)) is None


def test_map_rejects_bad_size() -> None:
    """A map needs a positive size."""
    with pytest.raises(ValueError, match="positive"):
        Map((0, 3))


@pytest.mark.parametrize(
    "content",
    [b"not zlib", zlib.compress(b"[]"), zlib.compress(b'{"size": [1]}')],
)
def test_corrupt_map_file_is_removed(tmp_path: Path, content: bytes) -> None:
    """A corrupt file is deleted and the map keeps its tiles."""
    path = tmp_path / "minimap.bin"
    path.write_bytes(content)
    minimap = Map((2, 2))
    minimap.set((0, 0), RED, LIGHT, check_bounds=True)
    minimap.load(path)
    assert not path.exists()
    assert minimap.get((0, 0)) is not None


def test_json_formatter_uses_configured_keys() -> None:
    """Records become JSON with the configured keys and extras."""
    formatter = JsonFormatter({"level": "levelname", "message": "message"})
    record = logging.makeLogRecord({
        "levelname": "INFO",
        "msg": "hello %s",
        "args": ("world",),
        "player": "me",
    })
    data = json.loads(formatter.format(record))
    assert data == {"level": "INFO", "message": "hello world", "player": "me"}


def test_json_formatter_timestamp_and_exception() -> None:
    """Timestamps are ISO 8601 and exceptions are formatted."""
    formatter = JsonFormatter({"timestamp": "timestamp"})
    error = RuntimeError("boom")
    record = logging.makeLogRecord({
        "msg": "failed",
        "exc_info": (RuntimeError, error, None),
    })
    data = json.loads(formatter.format(record))
    assert data["timestamp"].endswith("+00:00")
    assert "RuntimeError: boom" in data["exc_info"]


def test_package_metadata() -> None:
    """The package exposes its version and author."""
    assert sch5n.__version__
    assert sch5n.__author__ in sch5n.__authors__
