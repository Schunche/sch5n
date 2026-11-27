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
from sch5n.log.logger import default_config, ensure_config
from sch5n.utility import path
from sch5n.world.save import user_worlds_dir

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


def test_logging_config_is_made_once(tmp_path: Path) -> None:
    """The default logging setup is written to the user's config once."""
    config = tmp_path / "config" / "logging.json"
    log_file = tmp_path / "logs" / "sch5n.log.jsonl"
    ensure_config(config, log_file)
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["handlers"]["file_jsonl"]["filename"] == str(log_file)
    assert data == json.loads(json.dumps(default_config(log_file)))

    # The user's own changes are kept.
    config.write_text('{"version": 1}', encoding="utf-8")
    ensure_config(config, log_file)
    assert json.loads(config.read_text(encoding="utf-8")) == {"version": 1}


def test_data_lives_next_to_assets() -> None:
    """Game data and maps are outside the assets, which draw the game."""
    assert path.DATA_DIR.parent == path.ASSETS_DIR.parent
    assert (path.DATA_DIR / "game.json").is_file()
    assert (path.MAPS_DIR / "map1.json").is_file()
    assert (path.SHADER_DIR / "sky.frag").is_file()
    assert path.user_logging_file().parent == path.user_settings_file().parent


def test_developing_keeps_everything_in_the_game_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """While developing, settings, worlds and logs stay in `dev/user`."""
    monkeypatch.setenv(path.DEV_ENV_VAR, "1")
    assert path.is_developing()
    written = [
        path.user_settings_file(),
        path.user_logging_file(),
        path.user_log_file(),
        user_worlds_dir(),
    ]
    for file in written:
        assert file.is_relative_to(path.DEV_USER_DIR)
        assert file.is_relative_to(path.GAME_DIR)

    monkeypatch.setenv(path.DEV_ENV_VAR, "0")
    assert not path.is_developing()
    assert not path.user_settings_file().is_relative_to(path.GAME_DIR)

    # Without the variable, a git checkout counts as developing.
    monkeypatch.delenv(path.DEV_ENV_VAR)
    assert path.is_developing() == (path.GAME_DIR / ".git").exists()
