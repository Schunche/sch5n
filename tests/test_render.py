# Copyright (c) 2026 Schunche
"""Rendering through a real (hidden) window. Skipped without a display."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sch5n.client.app import App
    from sch5n.client.scenes.menu import SettingsScene
    from sch5n.client.window import KeyEvent, MouseButtonEvent

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="needs a display (run under xvfb-run)",
)


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[App]:
    from sch5n.client.app import App, Options
    from sch5n.client.window import WindowError

    settings = tmp_path_factory.mktemp("user") / "settings.json"
    try:
        application = App(Options(hidden=True, seed=0, settings_file=settings))
    except WindowError as e:
        pytest.skip(str(e))
    yield application
    application.release()


def read_pixels(app: App) -> np.ndarray:
    w, h = app.window.framebuffer_size
    data = app.ctx.screen.read(components=3)
    return np.frombuffer(data, np.uint8).reshape(h, w, 3)[::-1]


def draw(app: App, scene: object) -> np.ndarray:
    app.batch.draw_calls = 0
    scene.render()  # type: ignore[attr-defined]
    app.batch.flush()
    return read_pixels(app)


def test_shapes_and_sprites(app: App) -> None:
    app.clear((0, 0, 0))
    app.batch.begin(app.screen)
    app.batch.shape((10, 10, 20, 20), (1.0, 0.0, 0.0, 1.0))
    app.batch.sprite(
        app.assets.atlas, (40, 10, 32, 32), app.assets.blocks[1][0]
    )
    app.batch.flush()
    pixels = read_pixels(app)
    assert tuple(pixels[20, 20]) == (255, 0, 0)
    assert pixels[20, 56].any()
    assert not pixels[100, 100].any()


def test_scenes_render(app: App) -> None:
    from sch5n.client.scenes.menu import MainMenu
    from sch5n.client.scenes.play import PlayScene

    menu_pixels = draw(app, MainMenu(app))
    assert menu_pixels.std() > 10  # Background image drawn.

    play = PlayScene(app)
    for _ in range(30):
        play.tick()
    pixels = draw(app, play)
    sky = tuple(app.content.game.sky_color)
    assert (pixels.reshape(-1, 3) == sky).all(axis=1).mean() > 0.3
    # The whole world is a handful of batched draw calls.
    assert app.batch.draw_calls <= 8


def test_text_cache_reuses_textures(app: App) -> None:
    app.batch.begin(app.screen)
    app.text.draw(app.batch, "hello", (0, 0))
    cached = len(app.text._cache)
    app.text.draw(app.batch, "hello", (0, 20))
    assert len(app.text._cache) == cached
    app.batch.flush()


def test_play_scene_input(app: App) -> None:
    import glfw

    from sch5n.client.scenes.play import PlayScene
    from sch5n.client.window import KeyEvent, MouseButtonEvent, ScrollEvent

    play = PlayScene(app)
    inventory = play.game.inventory

    play.on_event(ScrollEvent(0, -1))
    assert inventory.selected == 1
    play.on_event(KeyEvent(glfw.KEY_3, glfw.PRESS, 0))
    assert inventory.selected == 2

    play.on_event(KeyEvent(glfw.KEY_TAB, glfw.PRESS, 0))
    assert play.inventory_open
    slot = play.layout.slot_rect(0).center
    play.on_event(
        MouseButtonEvent(glfw.MOUSE_BUTTON_LEFT, glfw.PRESS, 0, slot)
    )
    assert inventory.cursor is not None
    assert inventory[0] is None

    # Closing the inventory puts the held stack back.
    play.on_event(KeyEvent(glfw.KEY_TAB, glfw.PRESS, 0))
    assert not play.inventory_open
    assert inventory.cursor is None
    assert inventory[0] is not None


def _press(key: int, mods: int = 0) -> KeyEvent:
    import glfw

    from sch5n.client.window import KeyEvent

    return KeyEvent(key, glfw.PRESS, mods)


def _click(
    pos: tuple[float, float], *, right: bool = False
) -> MouseButtonEvent:
    import glfw

    from sch5n.client.window import MouseButtonEvent

    button = glfw.MOUSE_BUTTON_RIGHT if right else glfw.MOUSE_BUTTON_LEFT
    return MouseButtonEvent(button, glfw.PRESS, 0, pos)


def _show_row(settings: SettingsScene, row: object) -> int:
    """Scroll so `row` is visible; return its index."""
    index = settings.row_index(row)  # type: ignore[arg-type]
    settings.scroll = settings.table.clamp_scroll(
        index * settings.ROW_HEIGHT - settings.table.area.h / 2
    )
    assert settings.table.is_visible(index, settings.scroll)
    return index


def test_rebind_in_settings_and_play(app: App) -> None:
    import json

    import glfw

    from sch5n.client.keybinds import Action, Binding, Context
    from sch5n.client.scenes.menu import BindRow, SettingsScene
    from sch5n.client.scenes.play import PlayScene

    play = PlayScene(app)
    settings = SettingsScene(app, back=play, in_game=True)
    jump = BindRow(Context.GAME, Action.JUMP)
    index = _show_row(settings, jump)
    cell = settings.table.cell_rect(index, 0, settings.scroll).center
    binds = app.keybinds[Context.GAME]

    # Escape cancels without changing anything.
    settings.on_event(_click(cell))
    assert settings.capturing == jump
    settings.on_event(_press(glfw.KEY_ESCAPE))
    assert settings.capturing is None
    assert binds.slots(Action.JUMP)[0] == Binding.key(glfw.KEY_SPACE)

    # Rebind jump to K.
    settings.on_event(_click(cell))
    settings.on_event(_press(glfw.KEY_K))
    assert binds.action_for(Binding.key(glfw.KEY_K)) is Action.JUMP
    saved = json.loads(app.settings_file.read_text(encoding="utf-8"))
    assert saved["keybinds"]["game"]["jump"] == ["key:K"]
    assert draw(app, settings).any()

    # The game uses the new binding right away.
    play.on_event(_press(glfw.KEY_SPACE))
    assert not play._jump_requested
    play.on_event(_press(glfw.KEY_K))
    assert play._jump_requested

    # Right click clears a slot.
    settings.on_event(_click(cell, right=True))
    assert binds.slots(Action.JUMP)[0] is None

    # Reset restores the defaults.
    reset = next(b for b in settings.buttons if b.id == "reset")
    settings.on_event(_click(reset.rect.center))
    assert binds.action_for(Binding.key(glfw.KEY_SPACE)) is Action.JUMP


def test_capture_modifier_combinations(app: App) -> None:
    import glfw

    from sch5n.client.keybinds import Action, Binding, Context, Mod
    from sch5n.client.scenes.menu import BindRow, MainMenu, SettingsScene
    from sch5n.client.window import KeyEvent, ScrollEvent

    settings = SettingsScene(app, back=MainMenu(app))
    binds = app.keybinds[Context.EDITOR]
    reset = BindRow(Context.EDITOR, Action.RESET_CAMERA)
    index = _show_row(settings, reset)

    def capture(slot: int) -> None:
        cell = settings.table.cell_rect(index, slot, settings.scroll).center
        settings.on_event(_click(cell))

    # Ctrl, then Shift+R: modifiers held during the press become part of it.
    capture(0)
    settings.on_event(_press(glfw.KEY_LEFT_CONTROL, glfw.MOD_CONTROL))
    assert settings.capturing == reset
    settings.on_event(_press(glfw.KEY_R, glfw.MOD_CONTROL | glfw.MOD_SHIFT))
    assert binds.slots(Action.RESET_CAMERA)[0] == Binding.key(
        glfw.KEY_R, Mod.CTRL | Mod.SHIFT
    )

    # A modifier pressed and released alone binds the modifier key.
    capture(1)
    settings.on_event(_press(glfw.KEY_LEFT_ALT, glfw.MOD_ALT))
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
    import json

    from sch5n.client.scenes.menu import (
        MainMenu,
        OptionRow,
        SettingsScene,
        VideoOption,
    )

    settings = SettingsScene(app, back=MainMenu(app))

    def click_option(option: VideoOption, *, right: bool = False) -> None:
        row = OptionRow(option)
        index = _show_row(settings, row)
        span = settings.table.span_rect(index, settings.scroll)
        settings.on_event(_click(span.center, right=right))

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
    import glfw

    from sch5n.client.scenes.map_tools import EditorScene, ViewerScene
    from sch5n.client.scenes.menu import SettingsScene
    from sch5n.client.window import ScrollEvent

    target = tmp_path_factory.mktemp("maps") / "new.json"
    editor = EditorScene(app, target)
    editor.on_event(ScrollEvent(0, 1))
    assert editor.selected == 1
    zoom = editor.camera.zoom
    editor.on_event(ScrollEvent(0, 1, glfw.MOD_CONTROL))
    assert editor.camera.zoom > zoom
    assert editor.selected == 1
    editor.on_event(_press(glfw.KEY_S, glfw.MOD_CONTROL))
    assert target.exists()

    viewer = ViewerScene(app, target)
    viewer.on_event(ScrollEvent(0, 1))
    assert viewer.camera.zoom > 1

    viewer.on_event(_press(glfw.KEY_F1))
    app._apply_scene_switch()
    assert isinstance(app.scene, SettingsScene)
