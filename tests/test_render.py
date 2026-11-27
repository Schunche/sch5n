# Copyright (c) 2026 Schunche
"""Rendering through a real (hidden) window. Skipped without a display."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import glfw
import numpy as np
import pytest

from sch5n.client.app import App, Options
from sch5n.client.keybinds import Action, Binding, Context, Mod
from sch5n.client.scenes.map_tools import EditorScene, ViewerScene
from sch5n.client.scenes.menu import (
    BindRow,
    MainMenu,
    OptionRow,
    SettingsScene,
    VideoOption,
)
from sch5n.client.scenes.play import PlayScene
from sch5n.client.window import (
    KeyEvent,
    MouseButtonEvent,
    ScrollEvent,
    WindowError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sch5n.client.scenes.base import Scene
    from sch5n.client.scenes.menu import Row

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="needs a display (run under xvfb-run)",
)

RED = (255, 0, 0)
MIN_BACKGROUND_STD = 10
"""A drawn background image is far from a flat color."""
MIN_SKY_SHARE = 0.3
"""At least this much of the game screen is open sky."""
MAX_GAME_DRAW_CALLS = 8
WARMUP_TICKS = 30


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[App]:
    """Open a hidden window with its own settings file.

    Yields:
        App: The application.

    """
    settings = tmp_path_factory.mktemp("user") / "settings.json"
    try:
        application = App(Options(hidden=True, seed=0, settings_file=settings))
    except WindowError as e:
        pytest.skip(str(e))
    yield application
    application.release()


def read_pixels(app: App) -> np.ndarray:
    """Read back the screen.

    Returns:
        np.ndarray: RGB pixels, top row first.

    """
    w, h = app.window.framebuffer_size
    data = app.ctx.screen.read(components=3)
    return np.frombuffer(data, np.uint8).reshape(h, w, 3)[::-1]


def draw(app: App, scene: Scene) -> np.ndarray:
    """Render one frame of a scene.

    Returns:
        np.ndarray: The rendered pixels.

    """
    app.batch.draw_calls = 0
    scene.render()
    app.batch.flush()
    return read_pixels(app)


def press(key: int, mods: int = 0) -> KeyEvent:
    """Create a key press event.

    Returns:
        KeyEvent: The event.

    """
    return KeyEvent(key, glfw.PRESS, mods)


def click(
    pos: tuple[float, float], *, right: bool = False
) -> MouseButtonEvent:
    """Create a mouse click event.

    Returns:
        MouseButtonEvent: The event.

    """
    button = glfw.MOUSE_BUTTON_RIGHT if right else glfw.MOUSE_BUTTON_LEFT
    return MouseButtonEvent(button, glfw.PRESS, 0, pos)


def show_row(settings: SettingsScene, row: Row) -> int:
    """Scroll the settings so that `row` is visible.

    Returns:
        int: The row's index.

    """
    index = settings.row_index(row)
    settings.scroll = settings.table.clamp_scroll(
        index * settings.ROW_HEIGHT - settings.table.area.h / 2
    )
    assert settings.table.is_visible(index, settings.scroll)
    return index


def test_shapes_and_sprites(app: App) -> None:
    """Shapes and sprites land on the expected pixels."""
    app.clear((0, 0, 0))
    app.batch.begin(app.screen)
    app.batch.shape((10, 10, 20, 20), (1.0, 0.0, 0.0, 1.0))
    app.batch.sprite(
        app.assets.atlas, (40, 10, 32, 32), app.assets.blocks[1][0]
    )
    app.batch.flush()
    pixels = read_pixels(app)
    assert tuple(pixels[20, 20]) == RED
    assert pixels[20, 56].any()
    assert not pixels[100, 100].any()


def test_scenes_render(app: App) -> None:
    """The menu and the game draw, the game in a few draw calls."""
    menu_pixels = draw(app, MainMenu(app))
    assert menu_pixels.std() > MIN_BACKGROUND_STD

    play = PlayScene(app)
    for _ in range(WARMUP_TICKS):
        play.tick()
    pixels = draw(app, play)
    sky = tuple(app.content.game.sky_color)
    sky_share = (pixels.reshape(-1, 3) == sky).all(axis=1).mean()
    assert sky_share > MIN_SKY_SHARE
    # The whole world is a handful of batched draw calls.
    assert app.batch.draw_calls <= MAX_GAME_DRAW_CALLS


def test_text_cache_reuses_textures(app: App) -> None:
    """Drawing the same text again reuses its texture."""
    app.batch.begin(app.screen)
    app.text.draw(app.batch, "hello", (0, 0))
    cached = app.text.cached_count
    app.text.draw(app.batch, "hello", (0, 20))
    assert app.text.cached_count == cached
    app.batch.flush()


def test_play_scene_input(app: App) -> None:
    """Hotbar and inventory react to input in the game."""
    play = PlayScene(app)
    inventory = play.game.inventory

    play.on_event(ScrollEvent(0, -1))
    assert inventory.selected == 1
    play.on_event(press(glfw.KEY_3))
    assert inventory.selected == Action.HOTBAR_3.hotbar_slot

    play.on_event(press(glfw.KEY_TAB))
    assert play.inventory_open
    play.on_event(click(play.layout.slot_rect(0).center))
    assert inventory.cursor is not None
    assert inventory[0] is None

    # Closing the inventory puts the held stack back.
    play.on_event(press(glfw.KEY_TAB))
    assert not play.inventory_open
    assert inventory.cursor is None
    assert inventory[0] is not None


def test_rebind_in_settings_and_play(app: App) -> None:
    """Rebinding in the settings changes the game's controls and is saved."""
    play = PlayScene(app)
    settings = SettingsScene(app, back=play, in_game=True)
    jump = BindRow(Context.GAME, Action.JUMP)
    index = show_row(settings, jump)
    cell = settings.table.cell_rect(index, 0, settings.scroll).center
    binds = app.keybinds[Context.GAME]

    # Escape cancels without changing anything.
    settings.on_event(click(cell))
    assert settings.capturing == jump
    settings.on_event(press(glfw.KEY_ESCAPE))
    assert settings.capturing is None
    assert binds.slots(Action.JUMP)[0] == Binding.key(glfw.KEY_SPACE)

    # Rebind jump to K.
    settings.on_event(click(cell))
    settings.on_event(press(glfw.KEY_K))
    assert binds.action_for(Binding.key(glfw.KEY_K)) is Action.JUMP
    saved = json.loads(app.settings_file.read_text(encoding="utf-8"))
    assert saved["keybinds"]["game"]["jump"] == ["key:K"]
    assert draw(app, settings).any()

    # The game uses the new binding right away.
    play.on_event(press(glfw.KEY_SPACE))
    assert not play.jump_requested
    play.on_event(press(glfw.KEY_K))
    assert play.jump_requested

    # Right click clears a slot.
    settings.on_event(click(cell, right=True))
    assert binds.slots(Action.JUMP)[0] is None

    # Reset restores the defaults.
    reset = next(b for b in settings.buttons if b.id == "reset")
    settings.on_event(click(reset.rect.center))
    assert binds.action_for(Binding.key(glfw.KEY_SPACE)) is Action.JUMP


def test_capture_modifier_combinations(app: App) -> None:
    """Modifier combinations, lone modifiers and the wheel can be bound."""
    settings = SettingsScene(app, back=MainMenu(app))
    binds = app.keybinds[Context.EDITOR]
    reset = BindRow(Context.EDITOR, Action.RESET_CAMERA)
    index = show_row(settings, reset)

    def capture(slot: int) -> None:
        """Start capturing a binding for a slot of the row."""
        cell = settings.table.cell_rect(index, slot, settings.scroll).center
        settings.on_event(click(cell))

    # Ctrl, then Shift+R: modifiers held during the press become part of it.
    capture(0)
    settings.on_event(press(glfw.KEY_LEFT_CONTROL, glfw.MOD_CONTROL))
    assert settings.capturing == reset
    settings.on_event(press(glfw.KEY_R, glfw.MOD_CONTROL | glfw.MOD_SHIFT))
    assert binds.slots(Action.RESET_CAMERA)[0] == Binding.key(
        glfw.KEY_R, Mod.CTRL | Mod.SHIFT
    )

    # A modifier pressed and released alone binds the modifier key.
    capture(1)
    settings.on_event(press(glfw.KEY_LEFT_ALT, glfw.MOD_ALT))
    settings.on_event(KeyEvent(glfw.KEY_LEFT_ALT, glfw.RELEASE, 0))
    assert binds.slots(Action.RESET_CAMERA)[1] == Binding.key(
        glfw.KEY_LEFT_ALT
    )

    # Wheel directions can be bound too.
    capture(1)
    settings.on_event(ScrollEvent(0, 1, glfw.MOD_SHIFT))
    assert binds.slots(Action.RESET_CAMERA)[1] == Binding.wheel(1, Mod.SHIFT)
    app.keybinds.reset()
    app.update_settings()


def test_video_options_apply_and_save(app: App) -> None:
    """Video options change the window and are saved."""
    settings = SettingsScene(app, back=MainMenu(app))

    def click_option(option: VideoOption, *, right: bool = False) -> None:
        """Click the value of a video option."""
        index = show_row(settings, OptionRow(option))
        span = settings.table.span_rect(index, settings.scroll)
        settings.on_event(click(span.center, right=right))

    before = (app.settings.window_width, app.settings.window_height)
    click_option(VideoOption.WINDOW_SIZE)
    after = (app.settings.window_width, app.settings.window_height)
    assert after != before
    app.window.poll()
    assert tuple(app.window.size) == after

    vsync = app.settings.vsync
    click_option(VideoOption.VSYNC)
    assert app.settings.vsync is not vsync

    click_option(VideoOption.FPS_LIMIT)
    limit = app.settings.fps_limit
    click_option(VideoOption.FPS_LIMIT, right=True)
    click_option(VideoOption.FPS_LIMIT)
    assert app.settings.fps_limit == limit

    saved = json.loads(app.settings_file.read_text(encoding="utf-8"))
    assert (saved["window_width"], saved["window_height"]) == after
    assert saved["vsync"] is not vsync
    assert saved["fps_limit"] == limit

    click_option(VideoOption.WINDOW_SIZE, right=True)
    app.window.poll()
    assert (app.settings.window_width, app.settings.window_height) == before


def test_editor_uses_its_own_binds(
    app: App, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The map editor and viewer use their own controls."""
    target = tmp_path_factory.mktemp("maps") / "new.json"
    editor = EditorScene(app, target)
    editor.on_event(ScrollEvent(0, 1))
    assert editor.selected == 1
    zoom = editor.camera.zoom
    editor.on_event(ScrollEvent(0, 1, glfw.MOD_CONTROL))
    assert editor.camera.zoom > zoom
    assert editor.selected == 1
    editor.on_event(press(glfw.KEY_S, glfw.MOD_CONTROL))
    assert target.exists()

    viewer = ViewerScene(app, target)
    viewer.on_event(ScrollEvent(0, 1))
    assert viewer.camera.zoom > 1

    viewer.on_event(press(glfw.KEY_F1))
    assert isinstance(app.pending_scene, SettingsScene)
