# Copyright (c) 2026 Schunche
"""Rebindable controls, video options and the settings file."""

from __future__ import annotations

from typing import TYPE_CHECKING

import glfw
import pytest

from sch5n.client.keybinds import (
    DEFAULTS,
    SLOTS,
    Action,
    Binding,
    Context,
    ContextBinds,
    Device,
    Keybinds,
    Mod,
)
from sch5n.client.ui import TableLayout
from sch5n.client.video import FPS_LIMITS, WINDOW_SIZES, cycle, fps_label
from sch5n.client.window import KeyEvent, MouseButtonEvent, ScrollEvent
from sch5n.game.config import Settings
from sch5n.game.content import load_settings, save_settings
from sch5n.utility import path

if TYPE_CHECKING:
    from pathlib import Path

SPACE = Binding.key(glfw.KEY_SPACE)
K = Binding.key(glfw.KEY_K)
S = Binding.key(glfw.KEY_S)
CTRL_S = Binding.key(glfw.KEY_S, Mod.CTRL)


class FakeWindow:
    """Just enough of `Window` to ask what is held."""

    def __init__(self, *keys: int, buttons: tuple[int, ...] = ()) -> None:
        self.keys = set(keys)
        self.buttons = set(buttons)

    def is_key_down(self, key: int) -> bool:
        return key in self.keys

    def is_mouse_down(self, button: int) -> bool:
        return button in self.buttons

    def held_mods(self) -> int:
        mods = 0
        if self.keys & {glfw.KEY_LEFT_CONTROL, glfw.KEY_RIGHT_CONTROL}:
            mods |= glfw.MOD_CONTROL
        if self.keys & {glfw.KEY_LEFT_SHIFT, glfw.KEY_RIGHT_SHIFT}:
            mods |= glfw.MOD_SHIFT
        return mods


def game() -> ContextBinds:
    return ContextBinds(Context.GAME)


def editor() -> ContextBinds:
    return ContextBinds(Context.EDITOR)


# Bindings


@pytest.mark.parametrize(
    ("text", "binding", "label"),
    [
        ("key:SPACE", SPACE, "Space"),
        ("key:a", Binding.key(glfw.KEY_A), "A"),
        ("key:LEFT_SHIFT", Binding.key(glfw.KEY_LEFT_SHIFT), "Left Shift"),
        ("mouse:LEFT", Binding.mouse(glfw.MOUSE_BUTTON_LEFT), "Mouse Left"),
        ("mouse:4", Binding.mouse(glfw.MOUSE_BUTTON_4), "Mouse 4"),
        ("wheel:UP", Binding.wheel(1), "Wheel Up"),
        ("ctrl+key:S", CTRL_S, "Ctrl+S"),
        (
            "shift+ctrl+wheel:DOWN",
            Binding.wheel(-1, Mod.CTRL | Mod.SHIFT),
            "Ctrl+Shift+Wheel Down",
        ),
    ],
)
def test_parse_and_format(text: str, binding: Binding, label: str) -> None:
    assert Binding.parse(text) == binding
    assert Binding.parse(str(binding)) == binding
    assert binding.label == label


@pytest.mark.parametrize(
    "text", ["key:NOPE", "pad:A", "SPACE", "hyper+key:A", "wheel:LEFT"]
)
def test_parse_rejects_garbage(text: str) -> None:
    with pytest.raises(ValueError, match="Unknown"):
        Binding.parse(text)


def test_from_event() -> None:
    assert Binding.from_event(KeyEvent(glfw.KEY_K, glfw.PRESS, 0)) == K
    assert Binding.from_event(KeyEvent(glfw.KEY_K, glfw.RELEASE, 0)) is None
    ctrl_s = KeyEvent(glfw.KEY_S, glfw.PRESS, glfw.MOD_CONTROL)
    assert Binding.from_event(ctrl_s) == CTRL_S
    # Pressing a modifier key binds the key itself.
    shift = KeyEvent(glfw.KEY_LEFT_SHIFT, glfw.PRESS, glfw.MOD_SHIFT)
    assert Binding.from_event(shift) == Binding.key(glfw.KEY_LEFT_SHIFT)
    event = MouseButtonEvent(glfw.MOUSE_BUTTON_RIGHT, glfw.PRESS, 0, (0, 0))
    binding = Binding.from_event(event)
    assert binding is not None
    assert binding.device is Device.MOUSE
    assert Binding.from_event(ScrollEvent(0, 2.0)) == Binding.wheel(1)
    assert Binding.from_event(ScrollEvent(0, -1, glfw.MOD_CONTROL)) == (
        Binding.wheel(-1, Mod.CTRL)
    )
    assert Binding.from_event(ScrollEvent(1, 0)) is None


# Contexts


def test_every_context_has_defaults() -> None:
    keys = Keybinds()
    for binds in keys:
        assert [action for action, _ in binds] == list(DEFAULTS[binds.context])
        assert all(len(slots) == SLOTS for _, slots in binds)


def test_game_defaults() -> None:
    binds = game()
    assert binds.action_for(SPACE) is Action.JUMP
    assert binds.action_for(Binding.mouse(glfw.MOUSE_BUTTON_LEFT)) is (
        Action.USE_ITEM
    )
    assert binds.action_for(Binding.key(glfw.KEY_0)) is Action.HOTBAR_10
    assert binds.pressed(ScrollEvent(0, -1)) is Action.HOTBAR_NEXT
    assert binds.pressed(KeyEvent(glfw.KEY_TAB, glfw.PRESS, 0)) is (
        Action.INVENTORY
    )
    assert Action.HOTBAR_10.hotbar_slot == 9
    assert Action.HOTBAR_NEXT.hotbar_slot is None


def test_contexts_bind_independently() -> None:
    keys = Keybinds()
    # The same physical inputs mean different things per program.
    up = Binding.wheel(1)
    assert keys[Context.EDITOR].action_for(up) is Action.NEXT_TILE
    assert keys[Context.VIEWER].action_for(up) is Action.ZOOM_IN
    assert keys[Context.GAME].action_for(up) is Action.HOTBAR_PREVIOUS
    # Rebinding in one context leaves the others alone.
    keys[Context.EDITOR].bind(Action.SAVE, 0, K)
    assert keys[Context.VIEWER].action_for(K) is None
    assert keys[Context.GAME].action_for(K) is None


def test_most_specific_modifier_wins_on_press() -> None:
    binds = editor()
    assert binds.action_for(CTRL_S) is Action.SAVE
    assert binds.action_for(S) is Action.PAN_DOWN
    # Extra modifiers fall back to the binding that needs fewer of them.
    assert binds.action_for(Binding.key(glfw.KEY_S, Mod.SHIFT)) is (
        Action.PAN_DOWN
    )
    assert binds.action_for(Binding.wheel(1, Mod.CTRL)) is Action.ZOOM_IN
    assert binds.action_for(Binding.wheel(1)) is Action.NEXT_TILE


def test_held_respects_modifiers_and_shadowing() -> None:
    binds = editor()
    assert binds.is_held(Action.PAN_DOWN, FakeWindow(glfw.KEY_S))
    # Ctrl+S is saving, the camera must not move.
    ctrl_s = FakeWindow(glfw.KEY_S, glfw.KEY_LEFT_CONTROL)
    assert not binds.is_held(Action.PAN_DOWN, ctrl_s)
    # Shift is not part of any S binding, so panning still works.
    assert binds.is_held(
        Action.PAN_DOWN, FakeWindow(glfw.KEY_S, glfw.KEY_LEFT_SHIFT)
    )
    assert binds.is_held(
        Action.PLACE_TILE, FakeWindow(buttons=(glfw.MOUSE_BUTTON_LEFT,))
    )
    # A binding that needs a modifier is only held with it.
    binds.bind(Action.ERASE_TILE, 1, Binding.key(glfw.KEY_E, Mod.SHIFT))
    assert not binds.is_held(Action.ERASE_TILE, FakeWindow(glfw.KEY_E))
    assert binds.is_held(
        Action.ERASE_TILE, FakeWindow(glfw.KEY_E, glfw.KEY_RIGHT_SHIFT)
    )


def test_bind_moves_binding_from_other_action() -> None:
    binds = game()
    lost = binds.bind(Action.INVENTORY, 1, SPACE)
    assert lost is Action.JUMP
    assert binds.action_for(SPACE) is Action.INVENTORY
    assert SPACE not in binds.slots(Action.JUMP)


def test_bind_within_same_action_moves_slot() -> None:
    binds = game()
    assert binds.bind(Action.JUMP, 1, SPACE) is None
    assert binds.slots(Action.JUMP) == (None, SPACE)


def test_modifier_variants_are_distinct_bindings() -> None:
    binds = editor()
    assert binds.bind(Action.RESET_CAMERA, 1, S) is Action.PAN_DOWN
    assert binds.action_for(CTRL_S) is Action.SAVE


def test_clear_and_reset() -> None:
    keys = Keybinds()
    keys[Context.GAME].bind(Action.JUMP, 0, None)
    assert keys[Context.GAME].action_for(SPACE) is None
    keys.reset()
    assert keys[Context.GAME].action_for(SPACE) is Action.JUMP


def test_escape_is_reserved() -> None:
    binds = game()
    with pytest.raises(ValueError, match="cannot be rebound"):
        binds.bind(Action.JUMP, 0, Binding.key(glfw.KEY_ESCAPE, Mod.CTRL))
    loaded = ContextBinds(Context.GAME, {"jump": ["key:ESCAPE"]})
    assert loaded.slots(Action.JUMP) == (None, None)


def test_config_roundtrip_keeps_cleared_and_ignores_unknown() -> None:
    keys = Keybinds()
    keys[Context.GAME].bind(Action.JUMP, 0, K)
    keys[Context.GAME].bind(Action.DEBUG, 0, None)
    keys[Context.EDITOR].bind(Action.SAVE, 1, Binding.key(glfw.KEY_F5))
    config = keys.to_config()
    assert config["game"]["jump"] == ["key:K"]
    assert config["game"]["debug"] == []
    assert config["editor"]["save"] == ["ctrl+key:S", "key:F5"]

    config["game"] |= {"fly": ["key:F"], "inventory": ["key:BAD"]}
    loaded = Keybinds({**config, "toaster": {}})
    assert loaded.to_config()["editor"] == config["editor"]
    game_binds = loaded[Context.GAME]
    assert game_binds.action_for(K) is Action.JUMP
    assert game_binds.slots(Action.DEBUG) == (None, None)
    assert game_binds.slots(Action.INVENTORY) == (None, None)
    # Missing contexts and actions get their defaults.
    partial = Keybinds({"game": {"jump": ["key:K"]}})
    assert partial[Context.GAME].action_for(Binding.key(glfw.KEY_TAB)) is (
        Action.INVENTORY
    )
    assert partial[Context.VIEWER].action_for(Binding.key(glfw.KEY_R)) is (
        Action.RESET_CAMERA
    )


# Settings file


def test_settings_file(tmp_path: Path) -> None:
    user = tmp_path / "cfg" / "settings.json"
    bundled = load_settings(path.DATA_DIR, user)
    assert bundled.keybinds == {}
    assert not bundled.fullscreen

    changed = Settings.model_validate({
        **bundled.model_dump(),
        "window_width": 1600,
        "window_height": 900,
        "fps_limit": 144,
        "keybinds": {"editor": {"save": ["key:F5"]}},
    })
    save_settings(changed, user)
    loaded = load_settings(path.DATA_DIR, user)
    assert loaded == changed
    assert loaded.keybinds == {"editor": {"save": ("key:F5",)}}

    user.write_text("{not json", encoding="utf-8")
    assert load_settings(path.DATA_DIR, user) == bundled
    assert load_settings(tmp_path / "nowhere", None) == Settings()


def test_flat_keybinds_from_older_files_are_game_binds() -> None:
    settings = Settings.model_validate({"keybinds": {"jump": ["key:K"]}})
    assert settings.keybinds == {"game": {"jump": ("key:K",)}}


# Video options


def test_cycle_known_values() -> None:
    assert cycle(WINDOW_SIZES, (1280, 720), 1) == (1600, 900)
    assert cycle(WINDOW_SIZES, (1024, 576), -1) == WINDOW_SIZES[-1]
    assert cycle(FPS_LIMITS, 240, 1) == 0
    assert cycle(FPS_LIMITS, 0, 1) == FPS_LIMITS[0]


def test_cycle_custom_values_step_to_neighbours() -> None:
    assert cycle(WINDOW_SIZES, (1300, 700), 1) == (1600, 900)
    assert cycle(WINDOW_SIZES, (1300, 700), -1) == (1280, 720)
    assert cycle(FPS_LIMITS, 50, 1) == 60
    assert cycle(FPS_LIMITS, 50, -1) == 30


def test_fps_label() -> None:
    assert fps_label(0) == "Unlimited"
    assert fps_label(144) == "144 FPS"


# Layout


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
    assert table.row_at(cell.center, 0) == 2
    assert table.cell_at(table.label_anchor(2, 0), 0) is None
    span = table.span_rect(2, 0)
    assert span.x == table.cell_rect(2, 0, 0).x
    assert span.right == cell.right

    scroll = 64
    assert table.cell_at(table.cell_rect(2, 0, scroll).center, scroll) == (
        2,
        0,
    )
    # Row 0 scrolled out of view cannot be clicked.
    assert not table.is_visible(0, scroll)
    assert table.cell_at(table.cell_rect(0, 0, scroll).center, scroll) is None
