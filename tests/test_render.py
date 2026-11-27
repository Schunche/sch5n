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

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="needs a display (run under xvfb-run)",
)


@pytest.fixture(scope="module")
def app() -> Iterator[App]:
    from sch5n.client.app import App, Options
    from sch5n.client.window import WindowError

    try:
        application = App(Options(hidden=True, seed=0))
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
