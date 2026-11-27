# Copyright (c) 2026 Schunche
"""Rebindable controls and the settings file."""

from __future__ import annotations

from typing import TYPE_CHECKING

import glfw
import pytest

from sch5n.client.keybinds import SLOTS, Action, Binding, Device, Keybinds
from sch5n.client.ui import TableLayout
from sch5n.client.window import KeyEvent, MouseButtonEvent, ScrollEvent
from sch5n.game.config import Settings
from sch5n.game.content import load_settings, save_settings
from sch5n.utility import path

if TYPE_CHECKING:
    from pathlib import Path

SPACE = Binding.key(glfw.KEY_SPACE)
K = Binding.key(glfw.KEY_K)


@pytest.mark.parametrize(
    ("text", "binding", "label"),
    [
        ("key:SPACE", SPACE, "Space"),
        ("key:a", Binding.key(glfw.KEY_A), "A"),
        ("key:LEFT_SHIFT", Binding.key(glfw.KEY_LEFT_SHIFT), "Left Shift"),
        ("mouse:LEFT", Binding.mouse(glfw.MOUSE_BUTTON_LEFT), "Mouse Left"),
        ("mouse:4", Binding.mouse(glfw.MOUSE_BUTTON_4), "Mouse 4"),
    ],
)
def test_parse_and_format(text: str, binding: Binding, label: str) -> None:
    assert Binding.parse(text) == binding
    assert Binding.parse(str(binding)) == binding
    assert binding.label == label


@pytest.mark.parametrize("text", ["key:NOPE", "pad:A", "SPACE"])
def test_parse_rejects_garbage(text: str) -> None:
    with pytest.raises(ValueError, match="Unknown binding"):
        Binding.parse(text)


def test_defaults() -> None:
    keys = Keybinds()
    assert keys.action_for(SPACE) is Action.JUMP
    assert (
        keys.action_for(Binding.mouse(glfw.MOUSE_BUTTON_LEFT))
        is Action.USE_ITEM
    )
    assert keys.action_for(Binding.key(glfw.KEY_0)) is Action.HOTBAR_10
    assert Action.HOTBAR_10.hotbar_slot == 9
    assert Action.JUMP.hotbar_slot is None
    assert all(len(slots) == SLOTS for _, slots in keys)


def test_from_event() -> None:
    assert Binding.from_event(KeyEvent(glfw.KEY_K, glfw.PRESS, 0)) == K
    assert Binding.from_event(KeyEvent(glfw.KEY_K, glfw.RELEASE, 0)) is None
    event = MouseButtonEvent(glfw.MOUSE_BUTTON_RIGHT, glfw.PRESS, 0, (0, 0))
    binding = Binding.from_event(event)
    assert binding is not None
    assert binding.device is Device.MOUSE
    assert Binding.from_event(ScrollEvent(0, 1)) is None
    assert (
        Keybinds().pressed(KeyEvent(glfw.KEY_TAB, glfw.PRESS, 0))
        is Action.INVENTORY
    )


def test_bind_moves_binding_from_other_action() -> None:
    keys = Keybinds()
    lost = keys.bind(Action.INVENTORY, 1, SPACE)
    assert lost is Action.JUMP
    assert keys.action_for(SPACE) is Action.INVENTORY
    assert SPACE not in keys.slots(Action.JUMP)


def test_bind_within_same_action_moves_slot() -> None:
    keys = Keybinds()
    assert keys.bind(Action.JUMP, 1, SPACE) is None
    assert keys.slots(Action.JUMP) == (None, SPACE)


def test_clear_and_reset() -> None:
    keys = Keybinds()
    keys.bind(Action.JUMP, 0, None)
    assert keys.action_for(SPACE) is None
    keys.reset()
    assert keys.action_for(SPACE) is Action.JUMP


def test_escape_is_reserved() -> None:
    keys = Keybinds()
    with pytest.raises(ValueError, match="cannot be rebound"):
        keys.bind(Action.JUMP, 0, Binding.key(glfw.KEY_ESCAPE))
    assert Keybinds({"jump": ["key:ESCAPE"]}).slots(Action.JUMP) == (
        None,
        None,
    )


def test_config_roundtrip_keeps_cleared_and_ignores_unknown() -> None:
    keys = Keybinds()
    keys.bind(Action.JUMP, 0, K)
    keys.bind(Action.DEBUG, 0, None)
    config = keys.to_config()
    assert config["jump"] == ["key:K"]
    assert config["debug"] == []

    loaded = Keybinds({**config, "fly": ["key:F"], "inventory": ["key:BAD"]})
    assert loaded.action_for(K) is Action.JUMP
    assert loaded.slots(Action.DEBUG) == (None, None)
    assert loaded.slots(Action.INVENTORY) == (None, None)
    # Actions missing from the file get their defaults.
    partial = Keybinds({"jump": ["key:K"]})
    assert partial.action_for(Binding.key(glfw.KEY_TAB)) is Action.INVENTORY


def test_settings_file(tmp_path: Path) -> None:
    user = tmp_path / "cfg" / "settings.json"
    bundled = load_settings(path.DATA_DIR, user)
    assert bundled.keybinds == {}

    save_settings(
        Settings.model_validate({
            **bundled.model_dump(),
            "keybinds": {"jump": ["key:K"]},
        }),
        user,
    )
    loaded = load_settings(path.DATA_DIR, user)
    assert loaded.keybinds == {"jump": ("key:K",)}
    assert loaded.window_width == bundled.window_width

    user.write_text("{not json", encoding="utf-8")
    assert load_settings(path.DATA_DIR, user) == bundled
    assert load_settings(tmp_path / "nowhere", None) == Settings()


def test_table_layout_scrolling() -> None:
    table = TableLayout.centered(17, (1280, 720), 100, 260, row_height=32)
    assert table.area.h == 160
    assert table.max_scroll == 17 * 32 - 160
    assert table.clamp_scroll(-5) == 0
    assert table.clamp_scroll(10_000) == table.max_scroll

    visible = [r for r in range(17) if table.is_visible(r, 0)]
    assert visible == [0, 1, 2, 3, 4]
    cell = table.cell_rect(2, 1, 0)
    assert table.cell_at(cell.center, 0) == (2, 1)
    assert table.cell_at(table.label_anchor(2, 0), 0) is None

    scroll = 64
    assert table.cell_at(table.cell_rect(2, 0, scroll).center, scroll) == (
        2,
        0,
    )
    # Row 0 scrolled out of view cannot be clicked.
    assert not table.is_visible(0, scroll)
    assert table.cell_at(table.cell_rect(0, 0, scroll).center, scroll) is None
